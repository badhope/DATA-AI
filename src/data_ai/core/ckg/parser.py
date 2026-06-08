"""
代码解析器（CodeParser）

支持多种语言的代码结构解析（Python 使用 ``ast``，其它使用正则）。
提供：
- :class:`CodeParser`: 顶层解析入口
- :class:`ParsedFile` / :class:`CodeSymbol` / :class:`CodeLocation`: 解析结果
- :class:`Dependency`: 抽取出的外部依赖
- :meth:`CodeParser.parse_file` / :meth:`parse_source`: 解析入口
- :meth:`CodeParser.extract_dependencies`: 依赖抽取

解析失败（语法错误、IO 错误）会返回**空**的 :class:`ParsedFile`，不会抛异常。
"""

from __future__ import annotations

import ast
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from ...utils.logging import get_logger

logger = get_logger(__name__)


# ─── 公共数据类 ────────────────────────────────────────────────────────────


class Language(Enum):
    """支持的编程语言枚举。"""

    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JAVA = "java"
    GO = "go"
    RUST = "rust"
    UNKNOWN = "unknown"


@dataclass
class CodeLocation:
    """代码中的位置信息。"""

    file_path: str
    line_start: int
    line_end: int
    column_start: int = 0
    column_end: int = 0


@dataclass
class CodeSymbol:
    """代码中的符号（类、函数、变量等）。"""

    name: str
    symbol_type: str
    location: CodeLocation
    signature: str = ""
    docstring: str = ""
    modifiers: list[str] = field(default_factory=list)
    parameters: list[dict[str, str]] = field(default_factory=list)
    return_type: str = ""
    dependencies: list[str] = field(default_factory=list)


@dataclass
class Dependency:
    """从 :class:`ParsedFile` 抽取出的外部依赖。"""

    name: str
    kind: str  # module / class / function / variable
    source: str = ""  # 原始导入语句
    alias: str | None = None
    line: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "source": self.source,
            "alias": self.alias,
            "line": self.line,
            "metadata": self.metadata,
        }


@dataclass
class ParsedFile:
    """一个文件解析后的结果。"""

    file_path: str
    language: Language
    symbols: list[CodeSymbol]
    imports: list[str]
    exports: list[str]
    dependencies: list[str]
    lines_of_code: int
    metadata: dict[str, Any] = field(default_factory=dict)


# ─── 工具方法 ──────────────────────────────────────────────────────────────


def _empty_parsed_file(file_path: str, language: Language = Language.UNKNOWN) -> ParsedFile:
    """构造一个空的 ParsedFile，用于解析失败时的回退。"""
    return ParsedFile(
        file_path=file_path,
        language=language,
        symbols=[],
        imports=[],
        exports=[],
        dependencies=[],
        lines_of_code=0,
        metadata={"error": True},
    )


def _safe_unparse(node: ast.AST | None) -> str:
    """安全地 unparse AST 节点，失败时回退到空字符串。"""
    if node is None:
        return ""
    try:
        return ast.unparse(node)
    except Exception:
        return ""


# ─── 主类 ──────────────────────────────────────────────────────────────────


class CodeParser:
    """
    代码解析器。

    Example:
        >>> parser = CodeParser()
        >>> result = parser.parse_source("def hello(): return 1")
        >>> len(result.symbols) >= 1
        True
    """

    _EXT_TO_LANG: dict[str, Language] = {
        ".py": Language.PYTHON,
        ".js": Language.JAVASCRIPT,
        ".jsx": Language.JAVASCRIPT,
        ".mjs": Language.JAVASCRIPT,
        ".cjs": Language.JAVASCRIPT,
        ".ts": Language.TYPESCRIPT,
        ".tsx": Language.TYPESCRIPT,
        ".java": Language.JAVA,
        ".go": Language.GO,
        ".rs": Language.RUST,
    }

    def __init__(self) -> None:
        self._parsers: dict[Language, Callable[[Path, str], ParsedFile]] = {
            Language.PYTHON: self._parse_python,
            Language.JAVASCRIPT: self._parse_javascript,
            Language.TYPESCRIPT: self._parse_typescript,
            Language.JAVA: self._parse_java,
            Language.GO: self._parse_go,
        }

    # ─── 公共入口 ─────────────────────────────────────────────────────

    def parse_file(self, file_path: str) -> ParsedFile:
        """
        解析单个文件。

        不会因为语法错误或文件不存在而抛出异常；遇到错误时返回空
        :class:`ParsedFile`，并通过 ``metadata.error`` 标记。
        """
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"parse_file: 文件不存在 {file_path}")
            return _empty_parsed_file(str(path), Language.UNKNOWN)

        language = self._detect_language(path)
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            logger.warning(f"读取文件失败 {file_path}: {exc}")
            return _empty_parsed_file(str(path), language)

        return self.parse_source(content, str(path))

    def parse_source(self, source: str, file_path: str = "<string>") -> ParsedFile:
        """解析源代码字符串。"""
        if source is None:
            return _empty_parsed_file(file_path)

        lines = source.count("\n") + (0 if source.endswith("\n") else 1)
        path = Path(file_path)
        language = self._detect_language(path)
        parser = self._parsers.get(language, self._parse_generic)
        try:
            result = parser(path, source)
        except Exception as exc:
            logger.warning(f"解析失败 {file_path}: {exc}")
            return _empty_parsed_file(file_path, language)

        # 始终确保 lines_of_code 准确
        if not result.lines_of_code:
            result.lines_of_code = max(lines, 0)
        return result

    def parse_directory(
        self,
        directory: str,
        recursive: bool = True,
        exclude: set[str] | None = None,
    ) -> list[ParsedFile]:
        """解析目录下所有支持的代码文件。"""
        dir_path = Path(directory)
        exclude = exclude or {"node_modules", ".git", "__pycache__", "venv", ".venv", "dist", "build"}
        if not dir_path.exists():
            logger.warning(f"parse_directory: 目录不存在 {directory}")
            return []
        extensions = set(self._EXT_TO_LANG.keys())
        pattern = "**/*" if recursive else "*"
        results: list[ParsedFile] = []
        for file_path in dir_path.glob(pattern):
            if not file_path.is_file():
                continue
            if any(part in exclude for part in file_path.parts):
                continue
            if file_path.suffix.lower() not in extensions:
                continue
            try:
                results.append(self.parse_file(str(file_path)))
            except Exception as exc:
                logger.warning(f"解析失败 {file_path}: {exc}")
        return results

    # ─── 依赖抽取 ─────────────────────────────────────────────────────

    def extract_dependencies(self, parsed: ParsedFile) -> list[Dependency]:
        """
        从 :class:`ParsedFile` 中抽取依赖。

        Returns:
            :class:`Dependency` 列表。
        """
        deps: list[Dependency] = []
        seen: set[tuple[str, str, int]] = set()

        # 1) 顶层 imports
        for imp in parsed.imports:
            key = (imp, "module", 0)
            if key in seen:
                continue
            seen.add(key)
            deps.append(Dependency(name=imp, kind="module", source=imp, line=0))

        # 2) 符号级依赖
        for symbol in parsed.symbols:
            for dep_name in symbol.dependencies or []:
                if not dep_name:
                    continue
                line = symbol.location.line_start if symbol.location else 0
                kind = "class" if dep_name[:1].isupper() else "function"
                key = (dep_name, kind, line)
                if key in seen:
                    continue
                seen.add(key)
                deps.append(Dependency(name=dep_name, kind=kind, line=line))

        return deps

    # ─── 内部：语言检测 ──────────────────────────────────────────────

    def _detect_language(self, path: Path) -> Language:
        if path.suffix:
            lang = self._EXT_TO_LANG.get(path.suffix.lower(), Language.UNKNOWN)
            if lang is not Language.UNKNOWN:
                return lang
        # 虚拟路径（<string> / <stdin> 等）默认按 Python 处理，
        # 以便交互式调用时也能得到合理的解析结果
        if str(path) in {"<string>", "<stdin>", "-"}:
            return Language.PYTHON
        return Language.UNKNOWN

    # ─── Python 解析 ──────────────────────────────────────────────────

    def _parse_python(self, path: Path, content: str) -> ParsedFile:
        symbols: list[CodeSymbol] = []
        imports: list[str] = []
        variables: list[dict[str, Any]] = []
        exported_names: list[str] = []
        symbol_deps: list[str] = []

        try:
            tree = ast.parse(content, filename=str(path))
        except SyntaxError as exc:
            logger.warning(f"Python 语法错误 {path}: {exc.msg} (line {exc.lineno})")
            return ParsedFile(
                file_path=str(path),
                language=Language.PYTHON,
                symbols=[],
                imports=[],
                exports=[],
                dependencies=[],
                lines_of_code=content.count("\n") + 1,
                metadata={"error": True, "error_message": exc.msg, "error_line": exc.lineno},
            )

        # 第一遍：处理 module-level 节点
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                imp_name = self._extract_import_name(node)
                if imp_name:
                    imports.append(imp_name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    name = self._extract_assign_name(target)
                    if name:
                        variables.append(
                            {
                                "name": name,
                                "line": getattr(node, "lineno", 0),
                                "value": _safe_unparse(node.value)[:200],
                            }
                        )
                        if not name.startswith("_"):
                            exported_names.append(name)
            elif isinstance(node, ast.AnnAssign) and node.target:
                name = self._extract_assign_name(node.target)
                if name:
                    variables.append(
                        {
                            "name": name,
                            "line": getattr(node, "lineno", 0),
                            "value": _safe_unparse(node.annotation),
                            "annotated": True,
                        }
                    )
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbols.append(self._parse_function(node, str(path)))
            elif isinstance(node, ast.ClassDef):
                symbols.append(self._parse_class(node, str(path)))

        # 第二遍：解析所有函数 / 类的依赖（包括嵌套）
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not self._is_module_level(tree, node):
                # 嵌套函数 / 方法在 _parse_class 中已经处理
                if not any(s.location.line_start == node.lineno for s in symbols):
                    symbols.append(self._parse_function(node, str(path)))
            # 收集调用依赖
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    called = self._extract_call_name(child.func)
                    if called and not called.startswith("_"):
                        symbol_deps.append(called)
                elif isinstance(child, ast.Name):
                    if not self._is_builtin(child.id):
                        symbol_deps.append(child.id)
                elif isinstance(child, ast.Attribute):
                    # obj.method
                    symbol_deps.append(_safe_unparse(child))

        # 去重依赖
        unique_deps = list(dict.fromkeys(symbol_deps))

        # 将顶层 dependencies 字段填上
        for sym in symbols:
            sym.dependencies = list(dict.fromkeys(sym.dependencies))

        # 导出
        for sym in symbols:
            if not sym.name.startswith("_") and sym.name not in exported_names:
                exported_names.append(sym.name)

        lines = content.count("\n") + 1

        return ParsedFile(
            file_path=str(path),
            language=Language.PYTHON,
            symbols=symbols,
            imports=imports,
            exports=exported_names,
            dependencies=list(dict.fromkeys(imports + unique_deps)),
            lines_of_code=lines,
            metadata={"variables": variables},
        )

    def _parse_function(self, node: ast.AST, file_path: str) -> CodeSymbol:
        """解析 Python 函数 / 异步函数定义。"""
        assert isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        parameters: list[dict[str, str]] = []
        args = node.args
        # 位置参数
        for arg in args.args:
            param: dict[str, str] = {"name": arg.arg}
            if arg.annotation:
                param["type"] = _safe_unparse(arg.annotation)
            parameters.append(param)
        # 位置可选参数
        defaults_offset = max(len(args.args) - len(args.defaults), 0)
        for idx, arg in enumerate(args.args):
            default_idx = idx - defaults_offset
            if default_idx >= 0 and default_idx < len(args.defaults):
                param.setdefault("default", _safe_unparse(args.defaults[default_idx]))
        # *args
        if args.vararg:
            parameters.append(
                {
                    "name": f"*{args.vararg.arg}",
                    "type": _safe_unparse(args.vararg.annotation) if args.vararg.annotation else "",
                }
            )
        # 关键字参数
        for arg in args.kwonlyargs:
            parameters.append({"name": arg.arg, "type": _safe_unparse(arg.annotation) if arg.annotation else ""})
        # **kwargs
        if args.kwarg:
            parameters.append(
                {
                    "name": f"**{args.kwarg.arg}",
                    "type": _safe_unparse(args.kwarg.annotation) if args.kwarg.annotation else "",
                }
            )

        return_type = _safe_unparse(node.returns) if node.returns else ""
        docstring = ast.get_docstring(node) or ""

        # 修饰符
        modifiers: list[str] = []
        if isinstance(node, ast.AsyncFunctionDef):
            modifiers.append("async")
        for dec in node.decorator_list:
            dec_name = _safe_unparse(dec)
            if dec_name:
                modifiers.append(f"@{dec_name}")

        # 依赖：调用 / 引用
        deps: list[str] = []
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                called = self._extract_call_name(child.func)
                if called:
                    deps.append(called)
            elif isinstance(child, ast.Name) and not self._is_builtin(child.id):
                deps.append(child.id)

        signature = self._build_signature(node.name, parameters, is_method=False)

        return CodeSymbol(
            name=node.name,
            symbol_type="function" if not self._is_method(node) else "method",
            location=CodeLocation(
                file_path=file_path,
                line_start=node.lineno,
                line_end=getattr(node, "end_lineno", None) or node.lineno,
            ),
            signature=signature,
            docstring=docstring,
            modifiers=modifiers,
            parameters=parameters,
            return_type=return_type,
            dependencies=list(dict.fromkeys(deps)),
        )

    def _parse_class(self, node: ast.ClassDef, file_path: str) -> CodeSymbol:
        """解析 Python 类定义。"""
        docstring = ast.get_docstring(node) or ""
        bases = [_safe_unparse(b) for b in node.bases]
        keywords = {kw.arg: _safe_unparse(kw.value) for kw in node.keywords if kw.arg}

        modifiers: list[str] = ["public"] if not node.name.startswith("_") else ["private"]
        for dec in node.decorator_list:
            dec_name = _safe_unparse(dec)
            if dec_name:
                modifiers.append(f"@{dec_name}")

        # 类内依赖
        deps: list[str] = []
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                called = self._extract_call_name(child.func)
                if called:
                    deps.append(called)
            elif isinstance(child, ast.Name) and not self._is_builtin(child.id):
                deps.append(child.id)

        return CodeSymbol(
            name=node.name,
            symbol_type="class",
            location=CodeLocation(
                file_path=file_path,
                line_start=node.lineno,
                line_end=getattr(node, "end_lineno", None) or node.lineno,
            ),
            signature=f"class {node.name}({', '.join(bases)})" if bases else f"class {node.name}",
            docstring=docstring,
            modifiers=modifiers,
            parameters=[{"name": b} for b in bases],
            return_type="",
            dependencies=list(dict.fromkeys(bases + deps + list(keywords.keys()))),
        )

    # ─── JavaScript / TypeScript 解析 ─────────────────────────────────

    _JS_FUNC_PATTERNS: list[re.Pattern[str]] = [
        re.compile(r"function\s+(?P<name>\w+)\s*\((?P<params>[^)]*)\)"),
        re.compile(r"(?:const|let|var)\s+(?P<name>\w+)\s*=\s*(?:async\s*)?\((?P<params>[^)]*)\)\s*=>"),
        re.compile(r"(?:const|let|var)\s+(?P<name>\w+)\s*=\s*(?:async\s*)?function\s*\((?P<params>[^)]*)\)"),
    ]

    def _parse_javascript(self, path: Path, content: str) -> ParsedFile:
        return self._parse_js_like(path, content, Language.JAVASCRIPT)

    def _parse_typescript(self, path: Path, content: str) -> ParsedFile:
        return self._parse_js_like(path, content, Language.TYPESCRIPT)

    def _parse_js_like(self, path: Path, content: str, language: Language) -> ParsedFile:
        symbols: list[CodeSymbol] = []
        imports: list[str] = []

        for match in re.finditer(r'import\s+.*?from\s+[\'"]([^\'"]+)[\'"]', content):
            imports.append(match.group(1))

        for match in re.finditer(r"class\s+(?P<name>\w+)(?:\s+extends\s+(?P<parent>\w+))?", content):
            line = content[: match.start()].count("\n") + 1
            parent = match.group("parent")
            symbols.append(
                CodeSymbol(
                    name=match.group("name"),
                    symbol_type="class",
                    location=CodeLocation(file_path=str(path), line_start=line, line_end=line),
                    signature=match.group(0),
                    dependencies=[parent] if parent else [],
                )
            )

        for pattern in self._JS_FUNC_PATTERNS:
            for match in pattern.finditer(content):
                line = content[: match.start()].count("\n") + 1
                symbols.append(
                    CodeSymbol(
                        name=match.group("name"),
                        symbol_type="function",
                        location=CodeLocation(file_path=str(path), line_start=line, line_end=line),
                        signature=match.group(0).strip(),
                    )
                )

        if language == Language.TYPESCRIPT:
            for match in re.finditer(r"interface\s+(\w+)", content):
                line = content[: match.start()].count("\n") + 1
                symbols.append(
                    CodeSymbol(
                        name=match.group(1),
                        symbol_type="interface",
                        location=CodeLocation(file_path=str(path), line_start=line, line_end=line),
                        signature=match.group(0),
                    )
                )
            for match in re.finditer(r"type\s+(\w+)\s*=", content):
                line = content[: match.start()].count("\n") + 1
                symbols.append(
                    CodeSymbol(
                        name=match.group(1),
                        symbol_type="type",
                        location=CodeLocation(file_path=str(path), line_start=line, line_end=line),
                    )
                )

        return ParsedFile(
            file_path=str(path),
            language=language,
            symbols=symbols,
            imports=list(dict.fromkeys(imports)),
            exports=[],
            dependencies=list(dict.fromkeys(imports)),
            lines_of_code=content.count("\n") + 1,
        )

    # ─── Java 解析 ────────────────────────────────────────────────────

    def _parse_java(self, path: Path, content: str) -> ParsedFile:
        symbols: list[CodeSymbol] = []
        imports: list[str] = []

        for match in re.finditer(r"import\s+([\w\.]+);", content):
            imports.append(match.group(1))

        for match in re.finditer(
            r"(?:public|private|protected)?\s*(?:abstract|final)?\s*class\s+(\w+)"
            r"(?:\s+extends\s+(\w+))?(?:\s+implements\s+([\w,\s]+))?",
            content,
        ):
            line = content[: match.start()].count("\n") + 1
            parent = match.group(2)
            impls = [i.strip() for i in (match.group(3) or "").split(",") if i.strip()]
            symbols.append(
                CodeSymbol(
                    name=match.group(1),
                    symbol_type="class",
                    location=CodeLocation(file_path=str(path), line_start=line, line_end=line),
                    dependencies=[d for d in [parent] + impls if d],
                )
            )

        for match in re.finditer(
            r"(?:public|private|protected)?\s*(?:static)?\s*(?:\w+(?:<[\w\s,<>]+>)?)\s+(\w+)\s*\(([^)]*)\)",
            content,
        ):
            name = match.group(1)
            if name in {"if", "for", "while", "switch", "catch", "return"}:
                continue
            line = content[: match.start()].count("\n") + 1
            symbols.append(
                CodeSymbol(
                    name=name,
                    symbol_type="method",
                    location=CodeLocation(file_path=str(path), line_start=line, line_end=line),
                    signature=f"{name}({match.group(2).strip()})",
                )
            )

        return ParsedFile(
            file_path=str(path),
            language=Language.JAVA,
            symbols=symbols,
            imports=list(dict.fromkeys(imports)),
            exports=[],
            dependencies=list(dict.fromkeys(imports)),
            lines_of_code=content.count("\n") + 1,
        )

    # ─── Go 解析 ──────────────────────────────────────────────────────

    def _parse_go(self, path: Path, content: str) -> ParsedFile:
        symbols: list[CodeSymbol] = []
        imports: list[str] = []

        for match in re.finditer(r'import\s+(?:\(([\s\S]*?)\)|"([^"]+)")', content):
            if match.group(2):
                imports.append(match.group(2))
            elif match.group(1):
                for imp in re.findall(r'"([^"]+)"', match.group(1)):
                    imports.append(imp)

        for match in re.finditer(r"func\s+(?:\([^)]+\)\s+)?(\w+)\s*\(([^)]*)\)", content):
            name = match.group(1)
            if name == "init":
                continue
            line = content[: match.start()].count("\n") + 1
            symbols.append(
                CodeSymbol(
                    name=name,
                    symbol_type="function",
                    location=CodeLocation(file_path=str(path), line_start=line, line_end=line),
                    signature=f"func {name}({match.group(2).strip()})",
                )
            )

        for match in re.finditer(r"type\s+(\w+)\s+struct", content):
            line = content[: match.start()].count("\n") + 1
            symbols.append(
                CodeSymbol(
                    name=match.group(1),
                    symbol_type="struct",
                    location=CodeLocation(file_path=str(path), line_start=line, line_end=line),
                )
            )

        for match in re.finditer(r"type\s+(\w+)\s+interface", content):
            line = content[: match.start()].count("\n") + 1
            symbols.append(
                CodeSymbol(
                    name=match.group(1),
                    symbol_type="interface",
                    location=CodeLocation(file_path=str(path), line_start=line, line_end=line),
                )
            )

        return ParsedFile(
            file_path=str(path),
            language=Language.GO,
            symbols=symbols,
            imports=list(dict.fromkeys(imports)),
            exports=[],
            dependencies=list(dict.fromkeys(imports)),
            lines_of_code=content.count("\n") + 1,
        )

    # ─── 通用回退 ────────────────────────────────────────────────────

    def _parse_generic(self, path: Path, content: str) -> ParsedFile:
        return ParsedFile(
            file_path=str(path),
            language=Language.UNKNOWN,
            symbols=[],
            imports=[],
            exports=[],
            dependencies=[],
            lines_of_code=content.count("\n") + 1,
        )

    # ─── Python 辅助 ──────────────────────────────────────────────────

    _BUILTINS: set[str] = {
        "print",
        "len",
        "range",
        "str",
        "int",
        "float",
        "bool",
        "list",
        "dict",
        "set",
        "tuple",
        "isinstance",
        "issubclass",
        "hasattr",
        "getattr",
        "setattr",
        "open",
        "type",
        "super",
        "object",
        "property",
        "staticmethod",
        "classmethod",
        "input",
        "map",
        "filter",
        "zip",
        "enumerate",
        "sorted",
        "min",
        "max",
        "sum",
        "any",
        "all",
        "abs",
        "round",
        "iter",
        "next",
        "reversed",
        "callable",
    }

    def _is_builtin(self, name: str) -> bool:
        return name in self._BUILTINS

    @staticmethod
    def _is_method(node: ast.AST) -> bool:
        return False  # 在更精细的实现中可由父节点判定

    @staticmethod
    def _is_module_level(tree: ast.Module, node: ast.AST) -> bool:
        return any(child is node for child in tree.body)

    @staticmethod
    def _extract_import_name(node: ast.AST) -> str:
        if isinstance(node, ast.Import):
            return ", ".join(alias.name for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = ", ".join(alias.name for alias in node.names)
            return f"{module}.{names}" if module else names
        return ""

    @staticmethod
    def _extract_call_name(func: ast.AST) -> str:
        if isinstance(func, ast.Name):
            return func.id
        if isinstance(func, ast.Attribute):
            return _safe_unparse(func)
        return ""

    @staticmethod
    def _extract_assign_name(target: ast.AST) -> str | None:
        if isinstance(target, ast.Name):
            return target.id
        if isinstance(target, ast.Tuple):
            for elt in target.elts:
                name = CodeParser._extract_assign_name(elt)
                if name:
                    return name
        return None

    @staticmethod
    def _build_signature(name: str, parameters: list[dict[str, str]], is_method: bool) -> str:
        parts = []
        for param in parameters:
            if param["name"].startswith("*"):
                parts.append(param["name"])
            else:
                ptype = param.get("type", "")
                parts.append(f"{param['name']}: {ptype}" if ptype else param["name"])
        prefix = ""
        if is_method:
            prefix = "self, "
        return f"def {name}({prefix}{', '.join(parts)})"


__all__ = [
    "CodeParser",
    "ParsedFile",
    "CodeSymbol",
    "CodeLocation",
    "Dependency",
    "Language",
]
