"""
DATA-AI 帮助系统

提供动态帮助内容生成和管理功能。
支持查看命令、工具、模型的帮助信息。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ..utils.logging import get_logger

logger = get_logger(__name__)


class HelpTopic(Enum):
    """帮助主题类型"""

    GENERAL = "general"
    COMMANDS = "commands"
    TOOLS = "tools"
    MODELS = "models"
    COMMAND = "command"


@dataclass
class CommandHelp:
    """命令帮助信息"""

    name: str
    description: str
    usage: str
    examples: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    related_commands: list[str] = field(default_factory=list)


@dataclass
class HelpSection:
    """帮助章节"""

    title: str
    content: str
    order: int = 0


class HelpSystem:
    """
    帮助系统

    动态生成帮助内容，从 ToolRegistry、LLMManager 获取实时数据。
    支持 :help, :help commands, :help tools, :help models, :help <command>

    Attributes:
        _commands: 内置命令帮助信息字典
        _sections: 帮助章节字典

    Example:
        >>> help_system = HelpSystem()
        >>> print(help_system.show_help())
        >>> print(help_system.show_tool_help())
    """

    def __init__(self):
        """初始化帮助系统"""
        self._commands: dict[str, CommandHelp] = {}
        self._sections: dict[str, HelpSection] = {}
        self._init_builtin_commands()
        self._init_help_sections()
        logger.info("帮助系统已初始化")

    def _init_builtin_commands(self) -> None:
        """初始化内置命令帮助信息"""
        self._commands = {
            ":help": CommandHelp(
                name=":help",
                description="显示帮助信息",
                usage=":help [topic|command]",
                examples=[
                    ":help - 显示通用帮助",
                    ":help commands - 显示所有命令",
                    ":help tools - 显示可用工具",
                    ":help models - 显示可用模型",
                    ":help :exit - 显示特定命令帮助",
                ],
                aliases=[":h", ":?"],
            ),
            ":exit": CommandHelp(
                name=":exit",
                description="退出程序",
                usage=":exit [code]",
                examples=[":exit", ":exit 0"],
                aliases=[":quit", ":q"],
            ),
            ":clear": CommandHelp(
                name=":clear",
                description="清屏",
                usage=":clear",
                examples=[":clear", ":cls"],
                aliases=[":cls"],
            ),
            ":mode": CommandHelp(
                name=":mode",
                description="切换模式",
                usage=":mode <mode_name>",
                examples=[
                    ":mode chat - 切换到聊天模式",
                    ":mode agent - 切换到代理模式",
                    ":mode code - 切换到代码模式",
                ],
                aliases=[":m"],
            ),
            ":model": CommandHelp(
                name=":model",
                description="切换或查看当前模型",
                usage=":model [model_name]",
                examples=[
                    ":model - 查看当前模型",
                    ":model gpt-4 - 切换到 gpt-4",
                ],
                aliases=[":llm"],
            ),
            ":tools": CommandHelp(
                name=":tools",
                description="列出或管理工具",
                usage=":tools [list|enable|disable]",
                examples=[
                    ":tools - 列出所有工具",
                    ":tools enable calculator - 启用计算器工具",
                ],
            ),
            ":session": CommandHelp(
                name=":session",
                description="会话管理",
                usage=":session [new|save|load|list] [name]",
                examples=[
                    ":session new - 创建新会话",
                    ":session save my_session - 保存当前会话",
                    ":session load my_session - 加载会话",
                ],
                aliases=[":s"],
            ),
            ":history": CommandHelp(
                name=":history",
                description="查看历史记录",
                usage=":history [n]",
                examples=[
                    ":history - 显示所有历史",
                    ":history 10 - 显示最近10条",
                ],
                aliases=[":hist"],
            ),
            ":config": CommandHelp(
                name=":config",
                description="配置管理",
                usage=":config [get|set|list] [key] [value]",
                examples=[
                    ":config list - 列出所有配置",
                    ":config get model - 获取模型配置",
                    ":config set temperature 0.8 - 设置温度参数",
                ],
            ),
            ":theme": CommandHelp(
                name=":theme",
                description="主题管理",
                usage=":theme [list|<name>]",
                examples=[
                    ":theme list - 列出所有主题",
                    ":theme dark - 切换到暗色主题",
                ],
            ),
            ":alias": CommandHelp(
                name=":alias",
                description="别名管理",
                usage=":alias [list|add|remove] [name] [command]",
                examples=[
                    ":alias list - 列出所有别名",
                    ":alias add h :help - 添加别名",
                    ":alias remove h - 删除别名",
                ],
            ),
            ":examples": CommandHelp(
                name=":examples",
                description="查看使用示例",
                usage=":examples [name]",
                examples=[
                    ":examples - 列出所有示例",
                    ":examples chat - 查看聊天示例",
                ],
            ),
            ":rag": CommandHelp(
                name=":rag",
                description="RAG 知识库管理",
                usage=":rag [add|query|list] [args...]",
                examples=[
                    ":rag list - 列出所有知识库",
                    ":rag add docs ./documents - 添加文档到知识库",
                    ':rag query "什么是AI?" - 查询知识库',
                ],
            ),
            ":sandbox": CommandHelp(
                name=":sandbox",
                description="沙箱管理",
                usage=":sandbox [create|enter|list|destroy] [name]",
                examples=[
                    ":sandbox list - 列出所有沙箱",
                    ":sandbox create python_env - 创建沙箱",
                    ":sandbox enter python_env - 进入沙箱",
                ],
                aliases=[":sb"],
            ),
            ":browser": CommandHelp(
                name=":browser",
                description="浏览器工具",
                usage=":browser [open|close|screenshot] [url]",
                examples=[
                    ":browser open https://example.com - 打开网页",
                    ":browser screenshot - 截图当前页面",
                ],
            ),
            ":search": CommandHelp(
                name=":search",
                description="网络搜索",
                usage=":search <query>",
                examples=[
                    ":search Python教程 - 搜索Python教程",
                ],
            ),
            ":file": CommandHelp(
                name=":file",
                description="文件操作",
                usage=":file [read|write|list] [path] [content]",
                examples=[
                    ":file list ./ - 列出目录文件",
                    ":file read config.txt - 读取文件",
                ],
            ),
            ":wizard": CommandHelp(
                name=":wizard",
                description="运行设置向导",
                usage=":wizard",
                examples=[":wizard - 启动交互式设置向导"],
            ),
        }
        logger.debug(f"已初始化 {len(self._commands)} 个内置命令")

    def _init_help_sections(self) -> None:
        """初始化帮助章节"""
        self._sections = {
            "header": HelpSection(
                title="DATA-AI 帮助系统",
                content="""
╔══════════════════════════════════════════════════════════════╗
║                    DATA-AI 交互式助手                         ║
║                                                              ║
║  输入 :help <topic> 查看特定主题帮助                          ║
║  输入 :help commands 查看所有可用命令                         ║
║  输入 :quit 或 :exit 退出程序                                 ║
╚══════════════════════════════════════════════════════════════╝
""",
                order=0,
            ),
            "quick_start": HelpSection(
                title="快速开始",
                content="""
【快速开始】

1. 直接输入消息与 AI 对话
2. 使用 :mode 切换工作模式
3. 使用 :tools 查看可用工具
4. 使用 :examples 查看使用示例

常用命令：
  :help          - 显示此帮助
  :mode chat     - 切换到聊天模式
  :mode agent    - 切换到代理模式
  :model         - 查看/切换模型
  :clear         - 清屏
  :exit          - 退出
""",
                order=1,
            ),
            "modes": HelpSection(
                title="工作模式",
                content="""
【工作模式】

  chat   - 聊天模式：直接与 AI 对话
  agent  - 代理模式：AI 可以使用工具自动完成任务
  code   - 代码模式：专注于代码生成和调试
  file   - 文件模式：处理文件操作
  rag    - RAG 模式：基于知识库问答
""",
                order=2,
            ),
            "tips": HelpSection(
                title="使用技巧",
                content="""
【使用技巧】

• 使用 Tab 键自动补全命令和文件路径
• 使用 ↑↓ 键浏览历史记录
• 使用 :alias 创建自定义快捷命令
• 使用 :theme 切换界面主题
• 使用 :session 管理对话会话

更多帮助：
  :help commands - 所有命令列表
  :help tools    - 可用工具列表
  :help models   - 可用模型列表
""",
                order=3,
            ),
        }

    def show_help(self, topic: str | None = None) -> str:
        """
        显示帮助信息

        Args:
            topic: 帮助主题，None 表示显示通用帮助

        Returns:
            格式化的帮助文本

        Example:
            >>> help_system = HelpSystem()
            >>> print(help_system.show_help())  # 通用帮助
            >>> print(help_system.show_help("commands"))  # 命令帮助
        """
        try:
            if topic is None:
                return self._show_general_help()

            topic_lower = topic.lower()

            if topic_lower in ("commands", "cmd", "command"):
                return self.show_command_help()
            elif topic_lower in ("tools", "tool"):
                return self.show_tool_help()
            elif topic_lower in ("models", "model", "llm"):
                return self.show_model_help()
            elif topic_lower.startswith(":"):
                return self._show_specific_command_help(topic_lower)
            else:
                return self._show_topic_help(topic_lower)

        except Exception as e:
            logger.error(f"显示帮助失败: {e}", topic=topic)
            return f"获取帮助失败: {e}"

    def _show_general_help(self) -> str:
        """显示通用帮助"""
        sections = sorted(self._sections.values(), key=lambda s: s.order)
        content = "\n".join([section.content for section in sections])
        return content.strip()

    def _show_specific_command_help(self, command: str) -> str:
        """
        显示特定命令的帮助

        Args:
            command: 命令名称（如 :help）

        Returns:
            命令帮助文本
        """
        if command not in self._commands:
            # 尝试查找别名
            for cmd_name, cmd_help in self._commands.items():
                if command in cmd_help.aliases:
                    command = cmd_name
                    break
            else:
                return f"未知命令: {command}\n使用 :help commands 查看所有命令"

        cmd = self._commands[command]

        lines = [
            f"\n【命令】{cmd.name}",
            f"\n描述: {cmd.description}",
            f"用法: {cmd.usage}",
        ]

        if cmd.aliases:
            lines.append(f"别名: {', '.join(cmd.aliases)}")

        if cmd.examples:
            lines.append("\n示例:")
            for example in cmd.examples:
                lines.append(f"  {example}")

        if cmd.related_commands:
            lines.append(f"\n相关命令: {', '.join(cmd.related_commands)}")

        lines.append("")
        return "\n".join(lines)

    def _show_topic_help(self, topic: str) -> str:
        """显示主题帮助"""
        return f"""
未知帮助主题: {topic}

可用主题:
  :help commands  - 显示所有命令
  :help tools     - 显示可用工具
  :help models    - 显示可用模型
  :help <command> - 显示特定命令帮助（如 :help :exit）
"""

    def show_command_help(self) -> str:
        """
        显示所有命令的帮助

        Returns:
            格式化的命令列表文本
        """
        lines = [
            "\n【可用命令】\n",
            f"{'命令':<15} {'别名':<12} {'描述'}",
            "-" * 60,
        ]

        for name in sorted(self._commands.keys()):
            cmd = self._commands[name]
            aliases = ", ".join(cmd.aliases) if cmd.aliases else "-"
            # 截断过长的别名
            if len(aliases) > 10:
                aliases = aliases[:8] + ".."
            lines.append(f"{name:<15} {aliases:<12} {cmd.description}")

        lines.extend(
            [
                "",
                "提示: 使用 :help <command> 查看详细帮助",
                "      例如: :help :session",
            ]
        )

        return "\n".join(lines)

    def show_tool_help(self) -> str:
        """
        显示可用工具的帮助

        动态从 ToolRegistry 获取工具信息。

        Returns:
            格式化的工具列表文本
        """
        lines = ["\n【可用工具】\n"]

        try:
            from ..core.tool.registry import get_tool_registry

            registry = get_tool_registry()
            categories = registry.list_categories()

            if not categories:
                lines.append("暂无可用工具")
                return "\n".join(lines)

            for category in sorted(categories):
                tools = registry.list_tools(category)
                if tools:
                    lines.append(f"\n[{category}]")

                    for tool_name in sorted(tools):
                        try:
                            tool = registry.get(tool_name)
                            definition = tool.to_definition()
                            lines.append(f"  {definition.name:<20} - {definition.description}")
                        except Exception as e:
                            lines.append(f"  {tool_name:<20} - (加载失败: {e})")

            lines.extend(
                [
                    "",
                    "提示: 在 agent 模式下，AI 会自动选择合适的工具",
                    "      使用 :tools 命令管理工具",
                ]
            )

        except ImportError:
            logger.warning("无法导入 ToolRegistry")
            lines.append("工具系统暂不可用")
        except Exception as e:
            logger.error(f"获取工具帮助失败: {e}")
            lines.append(f"获取工具信息失败: {e}")

        return "\n".join(lines)

    def show_model_help(self) -> str:
        """
        显示可用模型的帮助

        动态从 LLMManager 获取模型信息。

        Returns:
            格式化的模型列表文本
        """
        lines = ["\n【可用模型】\n"]

        try:
            from ..core.llm.manager import get_llm_manager

            manager = get_llm_manager()
            models = manager.list_models()
            default_model = manager.get_default_model()

            if not models:
                lines.append("暂无可用模型")
                lines.append("\n使用 :wizard 运行设置向导配置模型")
                return "\n".join(lines)

            lines.append(f"{'模型名称':<20} {'默认':<6} {'状态'}")
            lines.append("-" * 40)

            for model_name in sorted(models):
                is_default = "*" if model_name == default_model else ""
                lines.append(f"{model_name:<20} {is_default:<6} 可用")

            lines.extend(
                [
                    "",
                    "提示: * 表示当前默认模型",
                    "      使用 :model <name> 切换模型",
                    "      使用 :config set model <name> 设置默认模型",
                ]
            )

        except ImportError:
            logger.warning("无法导入 LLMManager")
            lines.append("模型系统暂不可用")
        except Exception as e:
            logger.error(f"获取模型帮助失败: {e}")
            lines.append(f"获取模型信息失败: {e}")

        return "\n".join(lines)

    def get_command_list(self) -> list[str]:
        """
        获取所有命令名称列表

        Returns:
            命令名称列表（包括别名）
        """
        commands = list(self._commands.keys())
        for cmd in self._commands.values():
            commands.extend(cmd.aliases)
        return commands

    def get_command_usage(self, command: str) -> str | None:
        """
        获取命令用法

        Args:
            command: 命令名称

        Returns:
            命令用法字符串，命令不存在返回 None
        """
        if command in self._commands:
            return self._commands[command].usage

        # 检查别名
        for cmd in self._commands.values():
            if command in cmd.aliases:
                return cmd.usage

        return None

    def register_custom_help(self, name: str, content: str, title: str | None = None) -> None:
        """
        注册自定义帮助内容

        Args:
            name: 帮助标识名
            content: 帮助内容
            title: 帮助标题
        """
        self._sections[name] = HelpSection(
            title=title or name,
            content=content,
            order=len(self._sections),
        )
        logger.info(f"已注册自定义帮助: {name}")

    def add_command_help(self, command_help: CommandHelp) -> None:
        """
        添加命令帮助信息

        Args:
            command_help: 命令帮助对象
        """
        self._commands[command_help.name] = command_help
        logger.debug(f"已添加命令帮助: {command_help.name}")


# 全局帮助系统实例
_help_system: HelpSystem | None = None


def get_help_system() -> HelpSystem:
    """
    获取全局帮助系统实例

    Returns:
        HelpSystem 单例实例
    """
    global _help_system
    if _help_system is None:
        _help_system = HelpSystem()
    return _help_system


def show_help(topic: str | None = None) -> str:
    """
    便捷函数：显示帮助

    Args:
        topic: 帮助主题

    Returns:
        帮助文本
    """
    return get_help_system().show_help(topic)
