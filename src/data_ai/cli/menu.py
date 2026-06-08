"""
DATA-AI CLI 分级菜单系统

提供清晰的层级导航：
- 主菜单 → 子菜单 → 功能项
- 支持快捷键和命令别名
- 彩色输出和格式化
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ..utils.logging import get_logger

logger = get_logger(__name__)


class MenuItemType(Enum):
    """菜单项类型"""

    COMMAND = "command"  # 执行命令
    SUBMENU = "submenu"  # 子菜单
    SEPARATOR = "separator"  # 分隔线
    BACK = "back"  # 返回上级
    EXIT = "exit"  # 退出


@dataclass
class MenuItem:
    """菜单项"""

    key: str  # 快捷键
    label: str  # 显示标签
    item_type: MenuItemType  # 类型
    description: str = ""  # 描述
    handler: Callable | None = None  # 处理函数
    submenu: Menu | None = None  # 子菜单
    shortcut: str | None = None  # 命令别名
    disabled: bool = False  # 是否禁用


@dataclass
class Menu:
    """菜单定义"""

    title: str
    items: list[MenuItem] = field(default_factory=list)
    parent: Menu | None = None
    prompt: str = "请选择: "

    def add_item(self, item: MenuItem) -> None:
        """添加菜单项"""
        if item.item_type == MenuItemType.SUBMENU and item.submenu:
            item.submenu.parent = self
        self.items.append(item)

    def get_item(self, key: str) -> MenuItem | None:
        """获取菜单项"""
        key = key.lower()
        for item in self.items:
            if item.key.lower() == key:
                return item
            if item.shortcut and item.shortcut.lower() == key:
                return item
        return None

    def display(self) -> str:
        """生成菜单显示文本"""
        lines = []

        # 标题
        lines.append(f"\n{'=' * 50}")
        lines.append(f"  {self.title}")
        lines.append(f"{'=' * 50}")
        lines.append("")

        # 菜单项
        for item in self.items:
            if item.item_type == MenuItemType.SEPARATOR:
                lines.append("-" * 40)
            elif item.disabled:
                lines.append(f"  [{item.key}] {item.label} (不可用)")
            else:
                shortcut = f" ({item.shortcut})" if item.shortcut else ""
                desc = f" - {item.description}" if item.description else ""
                lines.append(f"  [{item.key}]{shortcut} {item.label}{desc}")

        lines.append("")
        lines.append(f"{'=' * 50}")

        return "\n".join(lines)


class MenuSystem:
    """
    菜单系统

    管理所有菜单和导航
    """

    def __init__(self):
        self.menus: dict[str, Menu] = {}
        self.current_menu: Menu | None = None
        self.running = False
        self.logger = get_logger(__name__)
        self._cli_state = None  # 延迟初始化

    def _get_cli_state(self):
        """延迟获取 CLI 状态"""
        if self._cli_state is None:
            from ..__main__ import get_cli_state

            self._cli_state = get_cli_state()
        return self._cli_state

    def register_menu(self, name: str, menu: Menu) -> None:
        """注册菜单"""
        self.menus[name] = menu
        self.logger.debug(f"菜单已注册: {name}")

    def navigate_to(self, menu_name: str) -> bool:
        """导航到指定菜单"""
        if menu_name not in self.menus:
            return False
        self.current_menu = self.menus[menu_name]
        return True

    def go_back(self) -> bool:
        """返回上级菜单"""
        if self.current_menu and self.current_menu.parent:
            self.current_menu = self.current_menu.parent
            return True
        return False

    def display_current(self) -> str:
        """显示当前菜单"""
        if self.current_menu:
            return self.current_menu.display()
        return "没有可用的菜单"

    def handle_input(self, user_input: str) -> tuple[bool, Any]:
        """
        处理用户输入

        Returns:
            (是否继续运行, 处理结果)
        """
        if not self.current_menu:
            return False, None

        user_input = user_input.strip().lower()

        if not user_input:
            return True, None

        # 特殊命令
        if user_input in ["q", "quit", "exit"]:
            return False, None

        if user_input in ["b", "back"]:
            if self.go_back():
                return True, None
            return False, None

        # 查找菜单项
        item = self.current_menu.get_item(user_input)
        if not item:
            return True, {"error": f"未知选项: {user_input}"}

        if item.disabled:
            return True, {"error": f"选项不可用: {item.label}"}

        # 处理菜单项
        if item.item_type == MenuItemType.SUBMENU and item.submenu:
            self.current_menu = item.submenu
            return True, None

        elif item.item_type == MenuItemType.BACK:
            if self.go_back():
                return True, None
            return False, None

        elif item.item_type == MenuItemType.EXIT:
            return False, None

        elif item.item_type == MenuItemType.COMMAND and item.handler:
            try:
                result = item.handler()
                return True, result
            except Exception as e:
                self.logger.error(f"命令执行失败: {e}")
                return True, {"error": str(e)}

        return True, None

    def run(self, start_menu: str) -> None:
        """运行菜单系统"""
        if not self.navigate_to(start_menu):
            print(f"起始菜单不存在: {start_menu}")
            return

        self.running = True

        while self.running:
            # 显示菜单
            print(self.display_current())

            # 获取输入
            try:
                user_input = input(self.current_menu.prompt)
            except (KeyboardInterrupt, EOFError):
                print("\n再见!")
                break

            # 处理输入
            continue_running, result = self.handle_input(user_input)

            if not continue_running:
                print("再见!")
                break

            if result and isinstance(result, dict) and "error" in result:
                print(f"错误: {result['error']}")


# ============================================================================
# Handler 函数定义
# ============================================================================


def handler_start_chat() -> dict[str, Any]:
    """开始对话"""
    print("\n" + "=" * 50)
    print("开始对话模式")
    print("=" * 50)
    print("输入您的问题，或输入 :back 返回菜单\n")

    try:
        from ..__main__ import get_cli_state, handle_chat

        state = get_cli_state()

        while True:
            try:
                user_input = input(f"\033[1;32m[{state.mode.value}]>\033[0m ").strip()

                if user_input in [":back", ":b", ":quit", ":q"]:
                    break

                if not user_input:
                    continue

                # 执行聊天
                asyncio.run(handle_chat(user_input))

            except KeyboardInterrupt:
                print("\n\n已中断，输入 :back 返回菜单")
            except EOFError:
                break

        return {"action": "chat_ended"}

    except Exception as e:
        return {"error": str(e)}


def handler_show_help() -> dict[str, Any]:
    """显示帮助"""
    from .help_system import show_help

    show_help()
    return {"action": "help_shown"}


def handler_general_agent() -> dict[str, Any]:
    """启动通用 Agent"""
    from ..__main__ import CLIMode, get_cli_state, handle_chat

    state = get_cli_state()
    state.set_mode(CLIMode.AGENT)

    print("\n已切换到通用 Agent 模式")
    print("输入任务，或输入 :back 返回菜单\n")

    try:
        while True:
            try:
                user_input = input("\033[1;32m[agent]>\033[0m ").strip()

                if user_input in [":back", ":b", ":quit", ":q"]:
                    break
                if not user_input:
                    continue

                asyncio.run(handle_chat(user_input))

            except KeyboardInterrupt:
                print("\n\n已中断")
    except Exception as e:
        return {"error": str(e)}

    return {"action": "agent_mode"}


def handler_swe_agent() -> dict[str, Any]:
    """启动编程 Agent"""
    from ..__main__ import CLIMode, get_cli_state, handle_chat

    state = get_cli_state()
    state.set_mode(CLIMode.SWE)

    print("\n已切换到编程 Agent 模式")
    print("输入编程任务，或输入 :back 返回菜单\n")

    try:
        while True:
            try:
                user_input = input("\033[1;32m[swe]>\033[0m ").strip()

                if user_input in [":back", ":b", ":quit", ":q"]:
                    break
                if not user_input:
                    continue

                asyncio.run(handle_chat(user_input))

            except KeyboardInterrupt:
                print("\n\n已中断")
    except Exception as e:
        return {"error": str(e)}

    return {"action": "swe_mode"}


def handler_data_agent() -> dict[str, Any]:
    """启动数据分析 Agent"""
    from ..__main__ import CLIMode, get_cli_state, handle_chat

    state = get_cli_state()
    state.set_mode(CLIMode.DATA)

    print("\n已切换到数据分析 Agent 模式")
    print("输入数据分析任务，或输入 :back 返回菜单\n")

    try:
        while True:
            try:
                user_input = input("\033[1;32m[data]>\033[0m ").strip()

                if user_input in [":back", ":b", ":quit", ":q"]:
                    break
                if not user_input:
                    continue

                asyncio.run(handle_chat(user_input))

            except KeyboardInterrupt:
                print("\n\n已中断")
    except Exception as e:
        return {"error": str(e)}

    return {"action": "data_mode"}


def handler_code_execute() -> dict[str, Any]:
    """代码执行"""
    print("\n" + "=" * 50)
    print("代码执行")
    print("=" * 50)
    print("输入 Python 代码，输入 :run 执行，:back 返回\n")

    code_lines = []

    try:
        while True:
            try:
                line = input("... " if code_lines else ">>> ").strip()

                if line == ":back":
                    break
                elif line == ":run" and code_lines:
                    code = "\n".join(code_lines)
                    print(f"\n执行代码:\n{code}\n")

                    # 使用 PythonExecuteTool
                    from ..core.tool.tools import PythonExecuteTool

                    tool = PythonExecuteTool()
                    result = asyncio.run(tool.execute(code=code))

                    if result.success:
                        print(f"输出:\n{result.data}")
                    else:
                        print(f"错误: {result.error}")

                    code_lines = []
                elif line == ":clear":
                    code_lines = []
                    print("已清空")
                else:
                    code_lines.append(line)

            except KeyboardInterrupt:
                print("\n")
                code_lines = []

    except Exception as e:
        return {"error": str(e)}

    return {"action": "code_executed"}


def handler_web_search() -> dict[str, Any]:
    """网络搜索"""
    print("\n" + "=" * 50)
    print("网络搜索")
    print("=" * 50)

    try:
        query = input("输入搜索关键词: ").strip()

        if query:
            from ..core.tool.tools import WebSearchTool

            tool = WebSearchTool()
            result = asyncio.run(tool.execute(query=query))

            if result.success:
                print(f"\n搜索结果:\n{result.data}")
            else:
                print(f"搜索失败: {result.error}")

    except Exception as e:
        return {"error": str(e)}

    return {"action": "search_done"}


def handler_browser() -> dict[str, Any]:
    """浏览器自动化"""
    print("\n" + "=" * 50)
    print("浏览器自动化")
    print("=" * 50)
    print("可用命令: navigate, screenshot, click, fill, :back\n")

    try:
        from ..core.tool.browser_session import BrowserSessionManager

        BrowserSessionManager()

        while True:
            try:
                cmd = input("browser> ").strip()

                if cmd in [":back", ":quit"]:
                    break

                parts = cmd.split(maxsplit=1)
                if not parts:
                    continue

                action = parts[0]
                arg = parts[1] if len(parts) > 1 else ""

                if action == "navigate" and arg:
                    from ..core.tool.browser import browser_navigate

                    result = asyncio.run(browser_navigate(url=arg))
                    print(f"导航结果: {result.get('success')}")
                elif action == "screenshot":
                    from ..core.tool.browser import browser_screenshot

                    result = asyncio.run(browser_screenshot(url=arg))
                    print(f"截图保存: {result.get('data') if result.get('success') else result.get('error')}")
                else:
                    print("未知命令")

            except KeyboardInterrupt:
                print("\n")

    except Exception as e:
        return {"error": str(e)}

    return {"action": "browser_done"}


def handler_new_session() -> dict[str, Any]:
    """新建会话"""
    from ..__main__ import get_cli_state

    name = input("输入新会话名称: ").strip()

    if name:
        state = get_cli_state()
        state.session_manager.create_session(name)
        state.session_manager.switch_session(name)
        print(f"已创建并切换到会话: {name}")
        return {"action": "session_created", "name": name}

    return {"error": "会话名称不能为空"}


def handler_switch_session() -> dict[str, Any]:
    """切换会话"""
    from ..__main__ import get_cli_state

    state = get_cli_state()
    sessions = state.session_manager.list_sessions()

    print(f"\n可用会话: {', '.join(sessions)}")
    name = input("输入要切换的会话名: ").strip()

    if name and state.session_manager.switch_session(name):
        print(f"已切换到会话: {name}")
        return {"action": "session_switched", "name": name}

    return {"error": f"会话不存在: {name}"}


def handler_list_sessions() -> dict[str, Any]:
    """列出会话"""
    from ..__main__ import get_cli_state

    state = get_cli_state()
    sessions = state.session_manager.list_sessions()
    active = state.session_manager.get_active_session()

    print("\n" + "=" * 50)
    print("会话列表")
    print("=" * 50)

    for name in sessions:
        marker = " *" if active and active.name == name else ""
        print(f"  {name}{marker}")

    print(f"\n当前会话: {active.name if active else 'None'}")

    return {"action": "sessions_listed", "count": len(sessions)}


def handler_delete_session() -> dict[str, Any]:
    """删除会话"""
    from ..__main__ import get_cli_state

    state = get_cli_state()
    sessions = state.session_manager.list_sessions()

    print(f"\n可用会话: {', '.join(sessions)}")
    name = input("输入要删除的会话名: ").strip()

    if name == "default":
        return {"error": "不能删除默认会话"}

    if name and state.session_manager.delete_session(name):
        print(f"已删除会话: {name}")
        return {"action": "session_deleted", "name": name}

    return {"error": f"会话不存在: {name}"}


def handler_model_config() -> dict[str, Any]:
    """模型配置"""
    from ..utils.config import get_settings

    settings = get_settings()

    print("\n" + "=" * 50)
    print("模型配置")
    print("=" * 50)
    print(f"当前模型: {settings.llm.model}")
    print(f"提供商: {settings.llm.provider}")
    print(f"API Key: {'已配置' if settings.llm.api_key else '未配置'}")

    print("\n选择操作:")
    print("  1. 切换模型")
    print("  2. 切换提供商")
    print("  3. 设置 API Key")
    print("  0. 返回")

    choice = input("\n选择: ").strip()

    if choice == "1":
        model = input("输入模型名称: ").strip()
        if model:
            print(f"模型已设置为: {model} (重启后生效)")
    elif choice == "2":
        print("可用提供商: openai, anthropic, google, deepseek, ollama")
        provider = input("输入提供商: ").strip()
        if provider:
            print(f"提供商已设置为: {provider} (重启后生效)")
    elif choice == "3":
        import getpass

        api_key = getpass.getpass("输入 API Key: ")
        if api_key:
            print("API Key 已设置 (重启后生效)")

    return {"action": "model_config"}


def handler_api_key() -> dict[str, Any]:
    """API 密钥管理"""
    from ..utils.config import get_settings

    settings = get_settings()

    print("\n" + "=" * 50)
    print("API 密钥管理")
    print("=" * 50)

    # 显示当前配置状态
    providers = {
        "OpenAI": settings.llm.api_key.startswith("sk-") if settings.llm.api_key else False,
        "Anthropic": settings.llm.api_key.startswith("sk-ant-") if settings.llm.api_key else False,
    }

    for provider, configured in providers.items():
        status = "已配置" if configured else "未配置"
        print(f"  {provider}: {status}")

    print("\n设置 API Key (将保存到环境变量或配置文件)")

    import getpass

    api_key = getpass.getpass("输入 API Key (留空取消): ")

    if api_key:
        # 保存到配置
        config_dir = os.path.expanduser("~/.data-ai")
        os.makedirs(config_dir, exist_ok=True)

        config_file = os.path.join(config_dir, "config.toml")
        with open(config_file, "a") as f:
            f.write(f'\n[llm]\napi_key = "{api_key}"\n')

        print("API Key 已保存到配置文件")

    return {"action": "api_key_configured"}


def handler_log_level() -> dict[str, Any]:
    """日志级别设置"""
    from ..utils.config import get_settings

    settings = get_settings()

    print("\n" + "=" * 50)
    print("日志级别设置")
    print("=" * 50)
    print(f"当前级别: {settings.log_level}")
    print("\n可选级别: DEBUG, INFO, WARNING, ERROR")

    level = input("输入日志级别: ").strip().upper()

    if level in ["DEBUG", "INFO", "WARNING", "ERROR"]:
        print(f"日志级别已设置为: {level} (重启后生效)")
        return {"action": "log_level_set", "level": level}

    return {"error": f"无效的日志级别: {level}"}


def handler_theme() -> dict[str, Any]:
    """主题设置"""
    from .theme import get_theme_manager, list_themes

    manager = get_theme_manager()
    themes = list_themes()

    print("\n" + "=" * 50)
    print("主题设置")
    print("=" * 50)
    print(f"当前主题: {manager.current_theme.name if manager.current_theme else 'default'}")
    print(f"\n可用主题: {', '.join(themes)}")

    name = input("输入主题名称: ").strip().lower()

    if name in themes:
        manager.set_theme(name)
        print(f"主题已切换为: {name}")
        return {"action": "theme_set", "theme": name}

    return {"error": f"未知主题: {name}"}


# ============================================================================
# 菜单创建函数
# ============================================================================


def create_main_menu() -> Menu:
    """创建主菜单"""
    menu = Menu(
        title="DATA-AI CLI - 主菜单",
        prompt="请输入选项: ",
    )

    # 聊天功能
    menu.add_item(
        MenuItem(
            key="1",
            label="开始对话",
            item_type=MenuItemType.COMMAND,
            description="与 AI 助手对话",
            shortcut="chat",
            handler=handler_start_chat,
        )
    )

    menu.add_item(
        MenuItem(
            key="2",
            label="Agent 模式",
            item_type=MenuItemType.SUBMENU,
            description="使用智能体完成任务",
            submenu=create_agent_menu(),
            shortcut="agent",
        )
    )

    menu.add_item(
        MenuItem(
            key="3",
            label="工具箱",
            item_type=MenuItemType.SUBMENU,
            description="使用各种工具",
            submenu=create_tools_menu(),
            shortcut="tools",
        )
    )

    menu.add_item(
        MenuItem(
            key="4",
            label="会话管理",
            item_type=MenuItemType.SUBMENU,
            description="管理对话会话",
            submenu=create_session_menu(),
            shortcut="session",
        )
    )

    menu.add_item(
        MenuItem(
            key="5",
            label="系统设置",
            item_type=MenuItemType.SUBMENU,
            description="配置和设置",
            submenu=create_settings_menu(),
            shortcut="settings",
        )
    )

    menu.add_item(
        MenuItem(
            key="h",
            label="帮助",
            item_type=MenuItemType.COMMAND,
            description="显示帮助信息",
            shortcut="help",
            handler=handler_show_help,
        )
    )

    menu.add_item(
        MenuItem(
            key="",
            label="",
            item_type=MenuItemType.SEPARATOR,
        )
    )

    menu.add_item(
        MenuItem(
            key="q",
            label="退出",
            item_type=MenuItemType.EXIT,
            description="退出程序",
            shortcut="quit",
        )
    )

    return menu


def create_agent_menu() -> Menu:
    """创建 Agent 菜单"""
    menu = Menu(
        title="Agent 模式",
        prompt="选择 Agent 类型: ",
    )

    menu.add_item(
        MenuItem(
            key="1",
            label="通用 Agent",
            item_type=MenuItemType.COMMAND,
            description="通用多用途 Agent",
            handler=handler_general_agent,
        )
    )

    menu.add_item(
        MenuItem(
            key="2",
            label="编程 Agent",
            item_type=MenuItemType.COMMAND,
            description="软件工程专用 Agent",
            handler=handler_swe_agent,
        )
    )

    menu.add_item(
        MenuItem(
            key="3",
            label="数据分析 Agent",
            item_type=MenuItemType.COMMAND,
            description="数据分析专用 Agent",
            handler=handler_data_agent,
        )
    )

    menu.add_item(
        MenuItem(
            key="",
            label="",
            item_type=MenuItemType.SEPARATOR,
        )
    )

    menu.add_item(
        MenuItem(
            key="b",
            label="返回",
            item_type=MenuItemType.BACK,
            shortcut="back",
        )
    )

    return menu


def create_tools_menu() -> Menu:
    """创建工具菜单"""
    menu = Menu(
        title="工具箱",
        prompt="选择工具: ",
    )

    menu.add_item(
        MenuItem(
            key="1",
            label="代码执行",
            item_type=MenuItemType.COMMAND,
            description="执行 Python/Bash 代码",
            handler=handler_code_execute,
        )
    )

    menu.add_item(
        MenuItem(
            key="2",
            label="网络搜索",
            item_type=MenuItemType.COMMAND,
            description="搜索网络信息",
            handler=handler_web_search,
        )
    )

    menu.add_item(
        MenuItem(
            key="3",
            label="浏览器",
            item_type=MenuItemType.COMMAND,
            description="浏览器自动化",
            handler=handler_browser,
        )
    )

    menu.add_item(
        MenuItem(
            key="",
            label="",
            item_type=MenuItemType.SEPARATOR,
        )
    )

    menu.add_item(
        MenuItem(
            key="b",
            label="返回",
            item_type=MenuItemType.BACK,
            shortcut="back",
        )
    )

    return menu


def create_session_menu() -> Menu:
    """创建会话菜单"""
    menu = Menu(
        title="会话管理",
        prompt="选择操作: ",
    )

    menu.add_item(
        MenuItem(
            key="1",
            label="新建会话",
            item_type=MenuItemType.COMMAND,
            description="创建新的对话会话",
            handler=handler_new_session,
        )
    )

    menu.add_item(
        MenuItem(
            key="2",
            label="切换会话",
            item_type=MenuItemType.COMMAND,
            description="切换到其他会话",
            handler=handler_switch_session,
        )
    )

    menu.add_item(
        MenuItem(
            key="3",
            label="列出会话",
            item_type=MenuItemType.COMMAND,
            description="显示所有会话",
            handler=handler_list_sessions,
        )
    )

    menu.add_item(
        MenuItem(
            key="4",
            label="删除会话",
            item_type=MenuItemType.COMMAND,
            description="删除指定会话",
            handler=handler_delete_session,
        )
    )

    menu.add_item(
        MenuItem(
            key="",
            label="",
            item_type=MenuItemType.SEPARATOR,
        )
    )

    menu.add_item(
        MenuItem(
            key="b",
            label="返回",
            item_type=MenuItemType.BACK,
            shortcut="back",
        )
    )

    return menu


def create_settings_menu() -> Menu:
    """创建设置菜单"""
    menu = Menu(
        title="系统设置",
        prompt="选择设置项: ",
    )

    menu.add_item(
        MenuItem(
            key="1",
            label="模型配置",
            item_type=MenuItemType.COMMAND,
            description="配置 AI 模型",
            handler=handler_model_config,
        )
    )

    menu.add_item(
        MenuItem(
            key="2",
            label="API 密钥",
            item_type=MenuItemType.COMMAND,
            description="管理 API 密钥",
            handler=handler_api_key,
        )
    )

    menu.add_item(
        MenuItem(
            key="3",
            label="日志级别",
            item_type=MenuItemType.COMMAND,
            description="设置日志级别",
            handler=handler_log_level,
        )
    )

    menu.add_item(
        MenuItem(
            key="4",
            label="主题设置",
            item_type=MenuItemType.COMMAND,
            description="配置界面主题",
            handler=handler_theme,
        )
    )

    menu.add_item(
        MenuItem(
            key="",
            label="",
            item_type=MenuItemType.SEPARATOR,
        )
    )

    menu.add_item(
        MenuItem(
            key="b",
            label="返回",
            item_type=MenuItemType.BACK,
            shortcut="back",
        )
    )

    return menu


# 全局菜单系统
_menu_system = MenuSystem()


def get_menu_system() -> MenuSystem:
    """获取全局菜单系统"""
    return _menu_system
