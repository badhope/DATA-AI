"""
DATA-AI 主题系统

提供终端界面主题管理功能，支持多种预设主题和自定义主题。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from ..utils.logging import get_logger

logger = get_logger(__name__)


class ColorCode:
    """ANSI 颜色代码"""

    # 基本颜色
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # 亮色系
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    # 背景色
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"

    # 样式
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"
    BLINK = "\033[5m"
    REVERSE = "\033[7m"
    STRIKETHROUGH = "\033[9m"


@dataclass
class Theme:
    """
    主题数据类

    定义终端界面的颜色配置。

    Attributes:
        name: 主题名称
        description: 主题描述
        primary: 主色调
        secondary: 次要色调
        success: 成功颜色
        warning: 警告颜色
        error: 错误颜色
        info: 信息颜色
        text: 文本颜色
        text_muted: 次要文本颜色
        background: 背景色（用于描述）
        border: 边框颜色
        highlight: 高亮颜色
        prompt: 提示符颜色
        user_input: 用户输入颜色
        ai_output: AI输出颜色
        system_msg: 系统消息颜色

    Example:
        >>> theme = Theme(
        ...     name="dark",
        ...     description="暗色主题",
        ...     primary=ColorCode.CYAN,
        ...     text=ColorCode.WHITE,
        ... )
    """

    name: str
    description: str
    primary: str = ColorCode.WHITE
    secondary: str = ColorCode.WHITE
    success: str = ColorCode.GREEN
    warning: str = ColorCode.YELLOW
    error: str = ColorCode.RED
    info: str = ColorCode.BLUE
    text: str = ColorCode.WHITE
    text_muted: str = ColorCode.BRIGHT_BLACK
    background: str = ""
    border: str = ColorCode.WHITE
    highlight: str = ColorCode.BRIGHT_YELLOW
    prompt: str = ColorCode.CYAN
    user_input: str = ColorCode.WHITE
    ai_output: str = ColorCode.GREEN
    system_msg: str = ColorCode.YELLOW

    def apply(self, text: str, color_attr: str) -> str:
        """
        应用主题颜色到文本

        Args:
            text: 原始文本
            color_attr: 颜色属性名

        Returns:
            带颜色的文本
        """
        color = getattr(self, color_attr, self.text)
        return f"{color}{text}{ColorCode.RESET}"

    def style_prompt(self, prompt: str) -> str:
        """样式化提示符"""
        return f"{self.prompt}{prompt}{ColorCode.RESET}"

    def style_user_input(self, text: str) -> str:
        """样式化用户输入"""
        return f"{self.user_input}{text}{ColorCode.RESET}"

    def style_ai_output(self, text: str) -> str:
        """样式化AI输出"""
        return f"{self.ai_output}{text}{ColorCode.RESET}"

    def style_system_msg(self, text: str) -> str:
        """样式化系统消息"""
        return f"{self.system_msg}{text}{ColorCode.RESET}"

    def style_success(self, text: str) -> str:
        """样式化成功消息"""
        return f"{self.success}{text}{ColorCode.RESET}"

    def style_error(self, text: str) -> str:
        """样式化错误消息"""
        return f"{self.error}{text}{ColorCode.RESET}"

    def style_warning(self, text: str) -> str:
        """样式化警告消息"""
        return f"{self.warning}{text}{ColorCode.RESET}"

    def style_info(self, text: str) -> str:
        """样式化信息消息"""
        return f"{self.info}{text}{ColorCode.RESET}"

    def style_primary(self, text: str) -> str:
        """样式化主色调文本"""
        return f"{self.primary}{ColorCode.BOLD}{text}{ColorCode.RESET}"

    def style_secondary(self, text: str) -> str:
        """样式化次要色调文本"""
        return f"{self.secondary}{text}{ColorCode.RESET}"

    def style_muted(self, text: str) -> str:
        """样式化次要文本"""
        return f"{self.text_muted}{text}{ColorCode.RESET}"

    def style_border(self, text: str) -> str:
        """样式化边框"""
        return f"{self.border}{text}{ColorCode.RESET}"

    def style_highlight(self, text: str) -> str:
        """样式化高亮文本"""
        return f"{self.highlight}{ColorCode.BOLD}{text}{ColorCode.RESET}"


class ThemeManager:
    """
    主题管理器

    管理所有可用主题，支持主题切换和自定义主题。

    Attributes:
        _themes: 主题字典
        _current_theme: 当前主题名称

    Example:
        >>> manager = ThemeManager()
        >>> manager.list_themes()
        >>> manager.set_theme("dark")
    """

    def __init__(self):
        """初始化主题管理器"""
        self._themes: dict[str, Theme] = {}
        self._current_theme: str = "default"
        self._init_builtin_themes()
        logger.info("主题管理器已初始化")

    def _init_builtin_themes(self) -> None:
        """初始化内置主题"""
        builtin_themes = [
            # 1. 默认主题
            Theme(
                name="default",
                description="默认主题，使用系统默认颜色",
                primary=ColorCode.CYAN,
                secondary=ColorCode.BLUE,
                success=ColorCode.GREEN,
                warning=ColorCode.YELLOW,
                error=ColorCode.RED,
                info=ColorCode.BLUE,
                text=ColorCode.RESET,
                text_muted=ColorCode.BRIGHT_BLACK,
                border=ColorCode.WHITE,
                highlight=ColorCode.BRIGHT_CYAN,
                prompt=ColorCode.CYAN,
                user_input=ColorCode.RESET,
                ai_output=ColorCode.GREEN,
                system_msg=ColorCode.YELLOW,
            ),
            # 2. 暗色主题
            Theme(
                name="dark",
                description="暗色主题，适合深色终端背景",
                primary=ColorCode.BRIGHT_CYAN,
                secondary=ColorCode.BRIGHT_BLUE,
                success=ColorCode.BRIGHT_GREEN,
                warning=ColorCode.BRIGHT_YELLOW,
                error=ColorCode.BRIGHT_RED,
                info=ColorCode.BRIGHT_BLUE,
                text=ColorCode.WHITE,
                text_muted=ColorCode.BRIGHT_BLACK,
                border=ColorCode.BRIGHT_BLACK,
                highlight=ColorCode.BRIGHT_MAGENTA,
                prompt=ColorCode.BRIGHT_CYAN,
                user_input=ColorCode.WHITE,
                ai_output=ColorCode.BRIGHT_GREEN,
                system_msg=ColorCode.BRIGHT_YELLOW,
            ),
            # 3. 亮色主题
            Theme(
                name="light",
                description="亮色主题，适合浅色终端背景",
                primary=ColorCode.BLUE,
                secondary=ColorCode.CYAN,
                success=ColorCode.GREEN,
                warning=ColorCode.YELLOW,
                error=ColorCode.RED,
                info=ColorCode.BLUE,
                text=ColorCode.BLACK,
                text_muted=ColorCode.BRIGHT_BLACK,
                border=ColorCode.BLACK,
                highlight=ColorCode.MAGENTA,
                prompt=ColorCode.BLUE,
                user_input=ColorCode.BLACK,
                ai_output=ColorCode.GREEN,
                system_msg=ColorCode.YELLOW,
            ),
            # 4. Monokai 主题
            Theme(
                name="monokai",
                description="Monokai 配色方案，经典的代码编辑器主题",
                primary="\033[38;5;81m",  # 青色
                secondary="\033[38;5;208m",  # 橙色
                success="\033[38;5;118m",  # 绿色
                warning="\033[38;5;220m",  # 黄色
                error="\033[38;5;196m",  # 红色
                info="\033[38;5;81m",  # 青色
                text="\033[38;5;252m",  # 浅灰
                text_muted="\033[38;5;245m",  # 灰色
                border="\033[38;5;240m",  # 深灰
                highlight="\033[38;5;141m",  # 紫色
                prompt="\033[38;5;81m",  # 青色
                user_input="\033[38;5;252m",  # 浅灰
                ai_output="\033[38;5;118m",  # 绿色
                system_msg="\033[38;5;220m",  # 黄色
            ),
        ]

        for theme in builtin_themes:
            self._themes[theme.name] = theme

        logger.debug(f"已初始化 {len(builtin_themes)} 个内置主题")

    def get_theme(self, name: str | None = None) -> Theme:
        """
        获取主题

        Args:
            name: 主题名称，None 表示获取当前主题

        Returns:
            Theme 对象

        Raises:
            ValueError: 主题不存在
        """
        theme_name = name or self._current_theme

        if theme_name not in self._themes:
            logger.warning(f"主题不存在: {theme_name}，使用默认主题")
            return self._themes.get("default", Theme(name="default", description=""))

        return self._themes[theme_name]

    def get_current_theme(self) -> Theme:
        """
        获取当前主题

        Returns:
            当前 Theme 对象
        """
        return self.get_theme(self._current_theme)

    def set_theme(self, name: str) -> bool:
        """
        设置当前主题

        Args:
            name: 主题名称

        Returns:
            是否设置成功
        """
        if name not in self._themes:
            logger.error(f"无法设置主题: {name} 不存在")
            return False

        self._current_theme = name
        logger.info(f"主题已切换为: {name}")
        return True

    def list_themes(self) -> list[str]:
        """
        列出所有可用主题

        Returns:
            主题名称列表
        """
        return list(self._themes.keys())

    def show_theme_list(self) -> str:
        """
        显示主题列表

        Returns:
            格式化的主题列表文本
        """
        lines = [
            "\n【可用主题】\n",
            f"{'名称':<12} {'当前':<6} {'描述'}",
            "-" * 50,
        ]

        for name in sorted(self._themes.keys()):
            theme = self._themes[name]
            current = "*" if name == self._current_theme else ""
            lines.append(f"{name:<12} {current:<6} {theme.description}")

        lines.extend(
            [
                "",
                f"当前主题: {self._current_theme}",
                "提示: 使用 :theme <name> 切换主题",
            ]
        )

        return "\n".join(lines)

    def show_theme_preview(self, name: str) -> str:
        """
        显示主题预览

        Args:
            name: 主题名称

        Returns:
            主题预览文本
        """
        theme = self.get_theme(name)

        lines = [
            f"\n【主题预览】{theme.name}",
            f"描述: {theme.description}",
            "",
            "颜色示例:",
        ]

        # 显示各种颜色示例
        samples = [
            ("主色调", lambda t: t.style_primary("Primary")),
            ("次要色调", lambda t: t.style_secondary("Secondary")),
            ("成功", lambda t: t.style_success("Success")),
            ("警告", lambda t: t.style_warning("Warning")),
            ("错误", lambda t: t.style_error("Error")),
            ("信息", lambda t: t.style_info("Info")),
            ("提示符", lambda t: t.style_prompt("prompt>")),
            ("用户输入", lambda t: t.style_user_input("user input")),
            ("AI输出", lambda t: t.style_ai_output("AI output")),
            ("系统消息", lambda t: t.style_system_msg("System message")),
            ("高亮", lambda t: t.style_highlight("Highlight")),
            ("次要文本", lambda t: t.style_muted("Muted text")),
        ]

        for label, style_fn in samples:
            try:
                sample = style_fn(theme)
                lines.append(f"  {label:<12} {sample}")
            except Exception:
                lines.append(f"  {label:<12} (无法显示)")

        lines.append("")
        return "\n".join(lines)

    def register_theme(self, theme: Theme) -> None:
        """
        注册自定义主题

        Args:
            theme: 主题对象
        """
        self._themes[theme.name] = theme
        logger.info(f"已注册主题: {theme.name}")

    def unregister_theme(self, name: str) -> bool:
        """
        注销主题

        Args:
            name: 主题名称

        Returns:
            是否成功注销

        Note:
            不能注销当前正在使用的主题
        """
        if name == self._current_theme:
            logger.error(f"无法注销当前正在使用的主题: {name}")
            return False

        if name in self._themes:
            del self._themes[name]
            logger.info(f"已注销主题: {name}")
            return True

        return False

    def has_theme(self, name: str) -> bool:
        """
        检查主题是否存在

        Args:
            name: 主题名称

        Returns:
            是否存在
        """
        return name in self._themes

    def get_current_theme_name(self) -> str:
        """
        获取当前主题名称

        Returns:
            主题名称
        """
        return self._current_theme

    def create_custom_theme(
        self, name: str, description: str, base_theme: str | None = None, **color_overrides
    ) -> Theme:
        """
        创建自定义主题

        Args:
            name: 主题名称
            description: 主题描述
            base_theme: 基础主题名称，None 表示从默认开始
            **color_overrides: 颜色覆盖值

        Returns:
            新创建的 Theme 对象
        """
        # 获取基础主题
        if base_theme and base_theme in self._themes:
            base = self._themes[base_theme]
            theme = Theme(
                name=name,
                description=description,
                primary=color_overrides.get("primary", base.primary),
                secondary=color_overrides.get("secondary", base.secondary),
                success=color_overrides.get("success", base.success),
                warning=color_overrides.get("warning", base.warning),
                error=color_overrides.get("error", base.error),
                info=color_overrides.get("info", base.info),
                text=color_overrides.get("text", base.text),
                text_muted=color_overrides.get("text_muted", base.text_muted),
                border=color_overrides.get("border", base.border),
                highlight=color_overrides.get("highlight", base.highlight),
                prompt=color_overrides.get("prompt", base.prompt),
                user_input=color_overrides.get("user_input", base.user_input),
                ai_output=color_overrides.get("ai_output", base.ai_output),
                system_msg=color_overrides.get("system_msg", base.system_msg),
            )
        else:
            theme = Theme(name=name, description=description, **color_overrides)

        self.register_theme(theme)
        return theme

    @staticmethod
    def disable_colors() -> None:
        """
        禁用所有颜色输出

        用于不支持ANSI颜色的终端
        """
        # 将所有颜色代码设为空字符串
        for attr in dir(ColorCode):
            if not attr.startswith("_"):
                setattr(ColorCode, attr, "")
        logger.info("颜色输出已禁用")

    @staticmethod
    def is_color_supported() -> bool:
        """
        检查终端是否支持颜色

        Returns:
            是否支持颜色
        """
        # 检查环境变量
        if os.getenv("NO_COLOR"):
            return False
        if os.getenv("FORCE_COLOR"):
            return True

        # 检查终端类型
        term = os.getenv("TERM", "")
        if "color" in term.lower():
            return True
        if term in ("xterm", "screen", "tmux"):
            return True

        # Windows 10+ 支持ANSI颜色
        if os.name == "nt":
            return True

        return False


# 全局主题管理器实例
_theme_manager: ThemeManager | None = None


def get_theme_manager() -> ThemeManager:
    """
    获取全局主题管理器实例

    Returns:
        ThemeManager 单例实例
    """
    global _theme_manager
    if _theme_manager is None:
        _theme_manager = ThemeManager()
    return _theme_manager


def get_current_theme() -> Theme:
    """
    便捷函数：获取当前主题

    Returns:
        当前 Theme 对象
    """
    return get_theme_manager().get_current_theme()


def set_theme(name: str) -> bool:
    """
    便捷函数：设置主题

    Args:
        name: 主题名称

    Returns:
        是否设置成功
    """
    return get_theme_manager().set_theme(name)


def list_themes() -> list[str]:
    """
    便捷函数：列出主题

    Returns:
        主题名称列表
    """
    return get_theme_manager().list_themes()


def show_themes() -> str:
    """
    便捷函数：显示主题列表

    Returns:
        主题列表文本
    """
    return get_theme_manager().show_theme_list()
