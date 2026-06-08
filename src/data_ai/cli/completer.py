"""
DATA-AI CLI 智能补全系统

提供 Tab 补全功能，支持命令、工具、模型、文件路径补全
"""

import os

from data_ai.core.tool import get_tool_registry
from data_ai.utils.logging import get_logger

logger = get_logger("cli.completer")


class Completer:
    """补全器基类"""

    def complete(self, text: str, state: int) -> str | None:
        """
        补全接口（readline 兼容）

        Args:
            text: 当前输入文本
            state: 补全状态（0=第一个匹配，1=第二个...）

        Returns:
            匹配项或 None
        """
        matches = self.get_completions(text)
        if state < len(matches):
            return matches[state]
        return None

    def get_completions(self, text: str) -> list[str]:
        """
        获取所有补全建议

        Args:
            text: 当前输入文本

        Returns:
            补全建议列表
        """
        return []


class CommandCompleter(Completer):
    """命令补全器"""

    COMMANDS = [
        ":help",
        ":h",
        ":quit",
        ":q",
        ":exit",
        ":menu",
        ":m",
        ":mode",
        ":tool",
        ":clear",
        ":c",
        ":config",
        ":history",
        ":session",
        ":examples",
        ":alias",
        ":theme",
    ]

    def get_completions(self, text: str) -> list[str]:
        """获取命令补全"""
        if not text.startswith(":"):
            return []

        return [cmd for cmd in self.COMMANDS if cmd.startswith(text.lower())]


class ToolCompleter(Completer):
    """工具名补全器"""

    def __init__(self):
        self.registry = get_tool_registry()

    def get_completions(self, text: str, prefix: str = ":tool ") -> list[str]:
        """获取工具名补全"""
        if not text.startswith(prefix):
            return []

        tool_name = text[len(prefix) :].strip()
        tools = self.registry.list_tools()

        return [f"{prefix}{t}" for t in tools if t.startswith(tool_name)]


class ModeCompleter(Completer):
    """模式补全器"""

    MODES = ["chat", "agent", "data", "swe"]

    def get_completions(self, text: str, prefix: str = ":mode ") -> list[str]:
        """获取模式补全"""
        if not text.startswith(prefix):
            return []

        mode_name = text[len(prefix) :].strip()

        return [f"{prefix}{m}" for m in self.MODES if m.startswith(mode_name)]


class FileCompleter(Completer):
    """文件路径补全器"""

    def get_completions(self, text: str) -> list[str]:
        """获取文件路径补全"""
        # 查找最后一个空格后的路径
        parts = text.rsplit(" ", 1)
        if len(parts) < 2:
            return []

        path = parts[1]

        # 展开用户目录
        if path.startswith("~"):
            path = os.path.expanduser(path)

        # 获取目录和文件名前缀
        if os.path.isdir(path):
            directory = path
            prefix = ""
        else:
            directory = os.path.dirname(path) or "."
            prefix = os.path.basename(path)

        if not os.path.exists(directory):
            return []

        try:
            matches = []
            for name in os.listdir(directory):
                if name.startswith(prefix):
                    full_path = os.path.join(directory, name)
                    # 添加斜杠表示目录
                    if os.path.isdir(full_path):
                        name += "/"
                    matches.append(name)

            # 构造完整补全
            base = parts[0] + " " if parts[0] else ""
            return [f"{base}{directory}/{m}" if prefix else f"{base}{m}" for m in matches]
        except PermissionError:
            return []


class MultiCompleter(Completer):
    """组合补全器"""

    def __init__(self):
        self.command_completer = CommandCompleter()
        self.tool_completer = ToolCompleter()
        self.mode_completer = ModeCompleter()
        self.file_completer = FileCompleter()

    def complete(self, text: str, state: int) -> str | None:
        """组合补全"""
        matches = self.get_completions(text)
        if state < len(matches):
            return matches[state]
        return None

    def get_completions(self, text: str) -> list[str]:
        """获取所有补全"""
        completions = []

        # 命令补全
        if text.startswith(":"):
            completions.extend(self.command_completer.get_completions(text))

        # 工具补全
        if text.startswith(":tool "):
            completions.extend(self.tool_completer.get_completions(text))

        # 模式补全
        if text.startswith(":mode "):
            completions.extend(self.mode_completer.get_completions(text))

        # 文件补全（某些命令后）
        if any(text.startswith(cmd) for cmd in [":tool file_read ", ":tool file_write "]):
            completions.extend(self.file_completer.get_completions(text))

        return completions


# ============================================================================
# readline 集成
# ============================================================================


def setup_readline(history_file: str | None = None) -> bool:
    """
    设置 readline 补全

    Args:
        history_file: 历史记录文件路径

    Returns:
        是否成功
    """
    try:
        import readline
    except ImportError:
        logger.warning("readline not available (Windows)")
        return False

    completer = MultiCompleter()

    # 设置补全函数
    readline.set_completer(completer.complete)

    # 设置补全模式
    readline.parse_and_bind("tab: complete")

    # 设置历史文件
    if history_file:
        history_path = os.path.expanduser(history_file)
        os.makedirs(os.path.dirname(history_path), exist_ok=True)

        try:
            readline.read_history_file(history_path)
        except FileNotFoundError:
            pass

        # 退出时保存历史
        import atexit

        atexit.register(readline.write_history_file, history_path)

    logger.debug("readline setup complete")
    return True


def setup_prompt_toolkit() -> bool:
    """
    设置 prompt_toolkit 补全（高级补全）

    Returns:
        是否成功
    """
    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.completion import Completer as PTCompleter
        from prompt_toolkit.completion import Completion

        class DataAICompleter(PTCompleter):
            """prompt_toolkit 补全器"""

            def __init__(self):
                self.multi_completer = MultiCompleter()

            def get_completions(self, document, complete_event):
                text = document.text
                completions = self.multi_completer.get_completions(text)

                for completion in completions:
                    yield Completion(
                        completion,
                        start_position=-len(text),
                        display=completion,
                    )

        # 返回补全器实例
        return DataAICompleter()

    except ImportError:
        logger.debug("prompt_toolkit not available")
        return None


# ============================================================================
# 便捷函数
# ============================================================================


def get_input_with_completion(prompt: str, history_file: str | None = None) -> str:
    """
    获取带补全的输入

    Args:
        prompt: 提示符
        history_file: 历史记录文件

    Returns:
        用户输入
    """
    # 尝试使用 prompt_toolkit
    pt_completer = setup_prompt_toolkit()
    if pt_completer:
        try:
            from prompt_toolkit import PromptSession

            session = PromptSession(completer=pt_completer)
            return session.prompt(prompt)
        except Exception as e:
            logger.debug(f"prompt_toolkit error: {e}")

    # 回退到 readline
    if setup_readline(history_file):
        try:
            return input(prompt)
        except (EOFError, KeyboardInterrupt):
            raise

    # 最后回退到普通 input
    return input(prompt)


# 默认历史文件路径
DEFAULT_HISTORY_FILE = "~/.data-ai/history"
