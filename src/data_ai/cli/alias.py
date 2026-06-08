"""
DATA-AI 快捷命令/别名系统

提供命令别名和宏功能，支持用户自定义快捷命令。
别名持久化存储在 ~/.data-ai/aliases.toml
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:
    import tomli as tomllib

try:
    import tomli_w
except ImportError:
    tomli_w = None

from ..utils.logging import get_logger

logger = get_logger(__name__)


# 默认配置文件路径
DEFAULT_ALIASES_FILE = Path.home() / ".data-ai" / "aliases.toml"


@dataclass
class Alias:
    """
    别名数据类

    表示一个命令别名，将短命令映射到完整命令。

    Attributes:
        name: 别名名称
        command: 映射的完整命令
        description: 别名描述
        created_at: 创建时间戳

    Example:
        >>> alias = Alias(name="h", command=":help", description="帮助命令别名")
    """

    name: str
    command: str
    description: str = ""
    created_at: str | None = None

    def __post_init__(self):
        """初始化后处理"""
        if self.created_at is None:
            from datetime import datetime

            self.created_at = datetime.now().isoformat()

    def expand(self, args: str | None = None) -> str:
        """
        展开别名为完整命令

        Args:
            args: 额外参数

        Returns:
            完整的命令字符串
        """
        if args:
            return f"{self.command} {args}"
        return self.command

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Alias:
        """从字典创建"""
        return cls(**data)


@dataclass
class Macro:
    """
    宏数据类

    表示一个命令宏，可以执行一系列命令。

    Attributes:
        name: 宏名称
        commands: 命令列表
        description: 宏描述
        created_at: 创建时间戳

    Example:
        >>> macro = Macro(
        ...     name="setup",
        ...     commands=[":mode agent", ":tools enable all"],
        ...     description="快速设置工作环境"
        ... )
    """

    name: str
    commands: list[str] = field(default_factory=list)
    description: str = ""
    created_at: str | None = None

    def __post_init__(self):
        """初始化后处理"""
        if self.created_at is None:
            from datetime import datetime

            self.created_at = datetime.now().isoformat()

    def execute(self) -> list[str]:
        """
        获取要执行的命令列表

        Returns:
            命令列表
        """
        return self.commands.copy()

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Macro:
        """从字典创建"""
        return cls(**data)


class AliasManager:
    """
    别名管理器

    管理命令别名和宏，支持持久化存储。

    Attributes:
        _aliases: 别名字典
        _macros: 宏字典
        _config_file: 配置文件路径

    Example:
        >>> manager = AliasManager()
        >>> manager.add_alias("h", ":help")
        >>> manager.expand_command(":h")
        ':help'
    """

    def __init__(self, config_file: Path | None = None):
        """
        初始化别名管理器

        Args:
            config_file: 配置文件路径，默认使用 ~/.data-ai/aliases.toml
        """
        self._aliases: dict[str, Alias] = {}
        self._macros: dict[str, Macro] = {}
        self._config_file = config_file or DEFAULT_ALIASES_FILE

        # 初始化内置别名
        self._init_builtin_aliases()

        # 加载已保存的别名
        self._load_aliases()

        logger.info(f"别名管理器已初始化，共 {len(self._aliases)} 个别名，{len(self._macros)} 个宏")

    def _init_builtin_aliases(self) -> None:
        """初始化内置别名"""
        builtin_aliases = [
            Alias(name=":h", command=":help", description="帮助命令快捷方式"),
            Alias(name=":q", command=":quit", description="退出快捷方式"),
            Alias(name=":cls", command=":clear", description="清屏快捷方式"),
            Alias(name=":m", command=":mode", description="模式切换快捷方式"),
            Alias(name=":s", command=":session", description="会话管理快捷方式"),
            Alias(name=":sb", command=":sandbox", description="沙箱管理快捷方式"),
            Alias(name=":hist", command=":history", description="历史记录快捷方式"),
        ]

        for alias in builtin_aliases:
            self._aliases[alias.name] = alias

        logger.debug(f"已初始化 {len(builtin_aliases)} 个内置别名")

    def _load_aliases(self) -> None:
        """从文件加载别名"""
        if not self._config_file.exists():
            logger.debug(f"别名配置文件不存在: {self._config_file}")
            return

        try:
            with open(self._config_file, "rb") as f:
                data = tomllib.load(f)

            # 加载别名
            aliases_data = data.get("aliases", {})
            for name, alias_data in aliases_data.items():
                alias_data["name"] = name
                self._aliases[name] = Alias.from_dict(alias_data)

            # 加载宏
            macros_data = data.get("macros", {})
            for name, macro_data in macros_data.items():
                macro_data["name"] = name
                self._macros[name] = Macro.from_dict(macro_data)

            logger.info(f"已从文件加载 {len(aliases_data)} 个别名，{len(macros_data)} 个宏")

        except Exception as e:
            logger.error(f"加载别名文件失败: {e}")

    def _save_aliases(self) -> bool:
        """
        保存别名到文件

        Returns:
            是否保存成功
        """
        if tomli_w is None:
            logger.warning("tomli_w 未安装，无法保存别名")
            return False

        try:
            # 确保目录存在
            self._config_file.parent.mkdir(parents=True, exist_ok=True)

            # 准备数据
            data = {
                "aliases": {
                    name: {
                        "command": alias.command,
                        "description": alias.description,
                        "created_at": alias.created_at,
                    }
                    for name, alias in self._aliases.items()
                    if not self._is_builtin_alias(name)
                },
                "macros": {
                    name: {
                        "commands": macro.commands,
                        "description": macro.description,
                        "created_at": macro.created_at,
                    }
                    for name, macro in self._macros.items()
                },
            }

            # 写入文件
            with open(self._config_file, "wb") as f:
                tomli_w.dump(data, f)

            logger.debug("别名已保存到文件")
            return True

        except Exception as e:
            logger.error(f"保存别名失败: {e}")
            return False

    def _is_builtin_alias(self, name: str) -> bool:
        """检查是否为内置别名"""
        builtin_names = [":h", ":q", ":cls", ":m", ":s", ":sb", ":hist"]
        return name in builtin_names

    def add_alias(self, name: str, command: str, description: str = "") -> bool:
        """
        添加别名

        Args:
            name: 别名名称
            command: 映射的完整命令
            description: 别名描述

        Returns:
            是否添加成功
        """
        # 验证别名名称
        if not name.startswith(":"):
            logger.error("别名必须以 ':' 开头")
            return False

        # 检查是否已存在
        if name in self._aliases:
            logger.warning(f"别名已存在，将被覆盖: {name}")

        # 创建别名
        alias = Alias(name=name, command=command, description=description)
        self._aliases[name] = alias

        # 保存到文件
        self._save_aliases()

        logger.info(f"已添加别名: {name} -> {command}")
        return True

    def remove_alias(self, name: str) -> bool:
        """
        删除别名

        Args:
            name: 别名名称

        Returns:
            是否删除成功
        """
        if name not in self._aliases:
            logger.warning(f"别名不存在: {name}")
            return False

        # 不能删除内置别名
        if self._is_builtin_alias(name):
            logger.error(f"不能删除内置别名: {name}")
            return False

        del self._aliases[name]
        self._save_aliases()

        logger.info(f"已删除别名: {name}")
        return True

    def get_alias(self, name: str) -> Alias | None:
        """
        获取别名

        Args:
            name: 别名名称

        Returns:
            Alias 对象，不存在返回 None
        """
        return self._aliases.get(name)

    def has_alias(self, name: str) -> bool:
        """
        检查别名是否存在

        Args:
            name: 别名名称

        Returns:
            是否存在
        """
        return name in self._aliases

    def list_aliases(self) -> list[str]:
        """
        列出所有别名

        Returns:
            别名名称列表
        """
        return list(self._aliases.keys())

    def show_aliases(self) -> str:
        """
        显示所有别名

        Returns:
            格式化的别名列表文本
        """
        lines = [
            "\n【命令别名】\n",
            f"{'别名':<12} {'命令':<25} {'描述'}",
            "-" * 60,
        ]

        for name in sorted(self._aliases.keys()):
            alias = self._aliases[name]
            cmd = alias.command[:22] + ".." if len(alias.command) > 25 else alias.command
            desc = alias.description[:20] if alias.description else "-"
            builtin_mark = " (内置)" if self._is_builtin_alias(name) else ""
            lines.append(f"{name:<12} {cmd:<25} {desc}{builtin_mark}")

        lines.extend(
            [
                "",
                "提示: 使用 :alias add <name> <command> 添加别名",
                "      使用 :alias remove <name> 删除别名",
            ]
        )

        return "\n".join(lines)

    def expand_command(self, command: str) -> str:
        """
        展开命令中的别名

        Args:
            command: 输入命令

        Returns:
            展开后的命令
        """
        # 分割命令和参数
        parts = command.split(maxsplit=1)
        if not parts:
            return command

        cmd = parts[0]
        args = parts[1] if len(parts) > 1 else ""

        # 查找别名
        if cmd in self._aliases:
            alias = self._aliases[cmd]
            return alias.expand(args)

        return command

    def add_macro(self, name: str, commands: list[str], description: str = "") -> bool:
        """
        添加宏

        Args:
            name: 宏名称
            commands: 命令列表
            description: 宏描述

        Returns:
            是否添加成功
        """
        # 验证宏名称
        if not name.startswith(":"):
            logger.error("宏名称必须以 ':' 开头")
            return False

        # 检查是否已存在
        if name in self._macros:
            logger.warning(f"宏已存在，将被覆盖: {name}")

        # 创建宏
        macro = Macro(name=name, commands=commands, description=description)
        self._macros[name] = macro

        # 保存到文件
        self._save_aliases()

        logger.info(f"已添加宏: {name} ({len(commands)} 个命令)")
        return True

    def remove_macro(self, name: str) -> bool:
        """
        删除宏

        Args:
            name: 宏名称

        Returns:
            是否删除成功
        """
        if name not in self._macros:
            logger.warning(f"宏不存在: {name}")
            return False

        del self._macros[name]
        self._save_aliases()

        logger.info(f"已删除宏: {name}")
        return True

    def get_macro(self, name: str) -> Macro | None:
        """
        获取宏

        Args:
            name: 宏名称

        Returns:
            Macro 对象，不存在返回 None
        """
        return self._macros.get(name)

    def has_macro(self, name: str) -> bool:
        """
        检查宏是否存在

        Args:
            name: 宏名称

        Returns:
            是否存在
        """
        return name in self._macros

    def list_macros(self) -> list[str]:
        """
        列出所有宏

        Returns:
            宏名称列表
        """
        return list(self._macros.keys())

    def show_macros(self) -> str:
        """
        显示所有宏

        Returns:
            格式化的宏列表文本
        """
        lines = [
            "\n【命令宏】\n",
        ]

        if not self._macros:
            lines.append("暂无宏")
        else:
            for name in sorted(self._macros.keys()):
                macro = self._macros[name]
                lines.append(f"\n{name} - {macro.description or '无描述'}")
                lines.append(f"  命令数: {len(macro.commands)}")
                for i, cmd in enumerate(macro.commands, 1):
                    lines.append(f"    {i}. {cmd}")

        lines.extend(
            [
                "",
                "提示: 使用 :macro add <name> '<cmd1>; <cmd2>' 添加宏",
                "      使用 :macro remove <name> 删除宏",
            ]
        )

        return "\n".join(lines)

    def execute_macro(self, name: str) -> list[str]:
        """
        执行宏

        Args:
            name: 宏名称

        Returns:
            要执行的命令列表，宏不存在返回空列表
        """
        macro = self._macros.get(name)
        if macro:
            logger.debug(f"执行宏: {name}")
            return macro.execute()
        return []

    def is_alias(self, name: str) -> bool:
        """
        检查是否为别名

        Args:
            name: 名称

        Returns:
            是否为别名
        """
        return name in self._aliases

    def is_macro(self, name: str) -> bool:
        """
        检查是否为宏

        Args:
            name: 名称

        Returns:
            是否为宏
        """
        return name in self._macros

    def get_all_commands(self) -> list[str]:
        """
        获取所有别名和宏名称

        Returns:
            名称列表
        """
        return list(self._aliases.keys()) + list(self._macros.keys())

    def clear_custom_aliases(self) -> int:
        """
        清除所有自定义别名（保留内置别名）

        Returns:
            清除的别名数量
        """
        custom_aliases = [name for name in self._aliases.keys() if not self._is_builtin_alias(name)]

        for name in custom_aliases:
            del self._aliases[name]

        self._save_aliases()

        logger.info(f"已清除 {len(custom_aliases)} 个自定义别名")
        return len(custom_aliases)

    def clear_macros(self) -> int:
        """
        清除所有宏

        Returns:
            清除的宏数量
        """
        count = len(self._macros)
        self._macros.clear()
        self._save_aliases()

        logger.info(f"已清除 {count} 个宏")
        return count

    def reload(self) -> None:
        """重新加载别名文件"""
        # 清除自定义别名和宏
        self._aliases = {}
        self._macros = {}

        # 重新初始化
        self._init_builtin_aliases()
        self._load_aliases()

        logger.info("别名已重新加载")


# 全局别名管理器实例
_alias_manager: AliasManager | None = None


def get_alias_manager(config_file: Path | None = None) -> AliasManager:
    """
    获取全局别名管理器实例

    Args:
        config_file: 配置文件路径

    Returns:
        AliasManager 单例实例
    """
    global _alias_manager
    if _alias_manager is None:
        _alias_manager = AliasManager(config_file)
    return _alias_manager


def expand_command(command: str) -> str:
    """
    便捷函数：展开命令中的别名

    Args:
        command: 输入命令

    Returns:
        展开后的命令
    """
    return get_alias_manager().expand_command(command)


def add_alias(name: str, command: str, description: str = "") -> bool:
    """
    便捷函数：添加别名

    Args:
        name: 别名名称
        command: 映射的完整命令
        description: 别名描述

    Returns:
        是否添加成功
    """
    return get_alias_manager().add_alias(name, command, description)


def remove_alias(name: str) -> bool:
    """
    便捷函数：删除别名

    Args:
        name: 别名名称

    Returns:
        是否删除成功
    """
    return get_alias_manager().remove_alias(name)


def list_aliases() -> list[str]:
    """
    便捷函数：列出所有别名

    Returns:
        别名名称列表
    """
    return get_alias_manager().list_aliases()


def show_aliases() -> str:
    """
    便捷函数：显示所有别名

    Returns:
        格式化的别名列表文本
    """
    return get_alias_manager().show_aliases()


def add_macro(name: str, commands: list[str], description: str = "") -> bool:
    """
    便捷函数：添加宏

    Args:
        name: 宏名称
        commands: 命令列表
        description: 宏描述

    Returns:
        是否添加成功
    """
    return get_alias_manager().add_macro(name, commands, description)


def remove_macro(name: str) -> bool:
    """
    便捷函数：删除宏

    Args:
        name: 宏名称

    Returns:
        是否删除成功
    """
    return get_alias_manager().remove_macro(name)


def list_macros() -> list[str]:
    """
    便捷函数：列出所有宏

    Returns:
        宏名称列表
    """
    return get_alias_manager().list_macros()


def show_macros() -> str:
    """
    便捷函数：显示所有宏

    Returns:
        格式化的宏列表文本
    """
    return get_alias_manager().show_macros()
