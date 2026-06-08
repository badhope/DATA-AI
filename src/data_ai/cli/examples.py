"""
DATA-AI 内置示例系统

提供预置使用示例，帮助用户快速了解系统功能。
支持查看和运行各种使用示例。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ..utils.logging import get_logger

logger = get_logger(__name__)


class ExampleCategory(Enum):
    """示例分类"""

    BASIC = "basic"
    CHAT = "chat"
    CODE = "code"
    TOOLS = "tools"
    RAG = "rag"
    SANDBOX = "sandbox"
    BROWSER = "browser"
    ADVANCED = "advanced"


@dataclass
class Example:
    """
    示例数据类

    Attributes:
        name: 示例标识名
        title: 示例标题
        description: 示例描述
        category: 示例分类
        steps: 示例步骤列表
        expected_output: 预期输出描述
        tips: 使用提示

    Example:
        >>> example = Example(
        ...     name="chat",
        ...     title="基础聊天",
        ...     description="与AI进行基础对话",
        ...     category=ExampleCategory.CHAT,
        ...     steps=["输入: 你好", "观察AI回复"],
        ...     expected_output="AI会友好地回应问候"
        ... )
    """

    name: str
    title: str
    description: str
    category: ExampleCategory
    steps: list[str] = field(default_factory=list)
    expected_output: str = ""
    tips: list[str] = field(default_factory=list)

    def to_string(self) -> str:
        """
        将示例转换为可读的字符串格式

        Returns:
            格式化的示例文本
        """
        lines = [
            f"\n{'=' * 50}",
            f"【示例】{self.title}",
            f"{'=' * 50}",
            f"\n名称: {self.name}",
            f"分类: {self.category.value}",
            f"描述: {self.description}",
            "\n【步骤】",
        ]

        for i, step in enumerate(self.steps, 1):
            lines.append(f"  {i}. {step}")

        if self.expected_output:
            lines.extend(
                [
                    "\n【预期输出】",
                    f"  {self.expected_output}",
                ]
            )

        if self.tips:
            lines.extend(
                [
                    "\n【提示】",
                ]
            )
            for tip in self.tips:
                lines.append(f"  • {tip}")

        lines.append("")
        return "\n".join(lines)


class ExampleRegistry:
    """
    示例注册表

    管理所有预置示例，支持按分类查询和检索。

    Attributes:
        _examples: 示例字典，name -> Example

    Example:
        >>> registry = ExampleRegistry()
        >>> registry.list_examples()
        >>> registry.get_example("chat")
    """

    def __init__(self):
        """初始化示例注册表"""
        self._examples: dict[str, Example] = {}
        self._init_builtin_examples()
        logger.info(f"示例注册表已初始化，共 {len(self._examples)} 个示例")

    def _init_builtin_examples(self) -> None:
        """初始化内置示例"""
        builtin_examples = [
            # 1. 聊天示例
            Example(
                name="chat",
                title="基础聊天",
                description="与AI进行基础对话，了解基本交互方式",
                category=ExampleCategory.CHAT,
                steps=[
                    "直接输入: 你好，请介绍一下自己",
                    "观察AI的自我介绍",
                    "继续提问: 你能帮我做什么？",
                    "查看AI的能力说明",
                ],
                expected_output="AI会进行自我介绍并列出能够帮助的任务类型",
                tips=[
                    "可以直接用自然语言与AI对话",
                    "支持中文和英文",
                    "使用 :mode chat 确保在聊天模式",
                ],
            ),
            # 2. 代码示例
            Example(
                name="code",
                title="代码生成与调试",
                description="使用AI生成代码、解释代码或调试程序",
                category=ExampleCategory.CODE,
                steps=[
                    "切换到代码模式: :mode code",
                    "输入: 写一个Python函数，计算斐波那契数列",
                    "查看生成的代码",
                    "继续输入: 给这个函数加上类型注解和文档字符串",
                    "查看改进后的代码",
                ],
                expected_output="AI会生成完整的、带注释的Python函数代码",
                tips=[
                    "代码模式下AI更专注于编程任务",
                    "可以要求解释代码的每一部分",
                    "支持多种编程语言",
                ],
            ),
            # 3. 文件示例
            Example(
                name="file",
                title="文件操作",
                description="使用AI读取、分析和处理文件",
                category=ExampleCategory.TOOLS,
                steps=[
                    "使用 :file 命令查看当前目录",
                    "输入: 请读取 ./README.md 文件并总结内容",
                    "AI会自动读取文件并提供摘要",
                    "输入: 帮我把这个文件翻译成英文",
                    "查看翻译结果",
                ],
                expected_output="AI能够读取文件内容并进行分析、翻译等操作",
                tips=[
                    "使用 :file list <path> 列出目录内容",
                    "使用 :file read <path> 读取文件",
                    "AI可以处理文本、代码、配置文件等",
                ],
            ),
            # 4. 搜索示例
            Example(
                name="search",
                title="网络搜索",
                description="使用AI进行网络搜索并汇总信息",
                category=ExampleCategory.TOOLS,
                steps=[
                    "输入: :search Python 3.12 新特性",
                    "查看搜索结果",
                    "继续输入: 总结一下这些新特性中最重要的三个",
                    "AI会分析搜索结果并给出总结",
                ],
                expected_output="AI会搜索网络信息并提供结构化的总结",
                tips=[
                    "搜索功能需要配置搜索引擎API",
                    "可以搜索最新信息，弥补模型知识截止日期",
                    "支持复杂查询",
                ],
            ),
            # 5. 浏览器示例
            Example(
                name="browser",
                title="浏览器自动化",
                description="使用AI控制浏览器访问网页",
                category=ExampleCategory.BROWSER,
                steps=[
                    "输入: :browser open https://github.com",
                    "等待浏览器打开页面",
                    "输入: 请提取这个页面的主要导航链接",
                    "AI会分析页面内容",
                    "输入: :browser screenshot 保存截图",
                ],
                expected_output="AI能够控制浏览器、访问网页、提取信息、截图等",
                tips=[
                    "浏览器工具可以访问动态网页",
                    "支持页面截图保存",
                    "可以提取页面特定信息",
                ],
            ),
            # 6. 沙箱示例
            Example(
                name="sandbox",
                title="代码沙箱执行",
                description="在隔离环境中安全执行代码",
                category=ExampleCategory.SANDBOX,
                steps=[
                    "输入: :sandbox create python_env",
                    "创建Python沙箱环境",
                    "输入: 在沙箱中运行: print('Hello, World!')",
                    "查看执行结果",
                    "输入: :sandbox enter python_env",
                    "进入交互式沙箱环境",
                ],
                expected_output="代码在隔离的沙箱环境中安全执行",
                tips=[
                    "沙箱提供安全的代码执行环境",
                    "支持多种编程语言",
                    "可以安装额外的依赖包",
                ],
            ),
            # 7. RAG示例
            Example(
                name="rag",
                title="RAG 知识库问答",
                description="基于私有知识库进行问答",
                category=ExampleCategory.RAG,
                steps=[
                    "输入: :rag add documents ./my_docs",
                    "将文档添加到知识库",
                    "等待文档索引完成",
                    "切换到RAG模式: :mode rag",
                    "输入: 根据文档，公司的休假政策是什么？",
                    "AI会基于知识库内容回答",
                ],
                expected_output="AI基于上传的文档内容回答特定问题",
                tips=[
                    "RAG模式让AI基于私有知识回答",
                    "支持多种文档格式（PDF、Word、TXT等）",
                    "可以创建多个知识库",
                ],
            ),
            # 8. 工具示例
            Example(
                name="tool",
                title="Agent 工具使用",
                description="让AI自动选择和使用工具完成任务",
                category=ExampleCategory.ADVANCED,
                steps=[
                    "切换到代理模式: :mode agent",
                    "输入: 帮我查一下今天北京的天气，然后写一个简单的Python程序记录天气数据",
                    "观察AI如何规划任务",
                    "AI会自动调用搜索工具查天气",
                    "然后生成Python代码",
                    "查看完整的执行过程和结果",
                ],
                expected_output="AI自动规划并执行多步骤任务，使用合适的工具",
                tips=[
                    "Agent模式下AI可以自主决策",
                    "AI会自动选择合适的工具",
                    "可以观察AI的思考过程",
                ],
            ),
        ]

        for example in builtin_examples:
            self._examples[example.name] = example

        logger.debug(f"已初始化 {len(builtin_examples)} 个内置示例")

    def get_example(self, name: str) -> Example | None:
        """
        获取指定名称的示例

        Args:
            name: 示例名称

        Returns:
            Example 对象，不存在返回 None
        """
        return self._examples.get(name)

    def list_examples(self, category: ExampleCategory | None = None) -> list[str]:
        """
        列出示例名称列表

        Args:
            category: 分类筛选，None 表示所有

        Returns:
            示例名称列表
        """
        if category:
            return [name for name, example in self._examples.items() if example.category == category]
        return list(self._examples.keys())

    def list_categories(self) -> list[ExampleCategory]:
        """
        列出所有示例分类

        Returns:
            分类列表
        """
        categories = set()
        for example in self._examples.values():
            categories.add(example.category)
        return sorted(list(categories), key=lambda c: c.value)

    def get_examples_by_category(self, category: ExampleCategory) -> list[Example]:
        """
        获取指定分类的所有示例

        Args:
            category: 示例分类

        Returns:
            Example 对象列表
        """
        return [example for example in self._examples.values() if example.category == category]

    def show_example(self, name: str) -> str:
        """
        显示指定示例的详细信息

        Args:
            name: 示例名称

        Returns:
            格式化的示例文本
        """
        example = self.get_example(name)
        if example is None:
            available = ", ".join(sorted(self._examples.keys()))
            return f"未知示例: {name}\n\n可用示例: {available}"

        return example.to_string()

    def show_all_examples(self) -> str:
        """
        显示所有示例列表

        Returns:
            格式化的示例列表文本
        """
        lines = [
            "\n【使用示例】\n",
            f"{'名称':<12} {'分类':<10} {'标题'}",
            "-" * 50,
        ]

        for name in sorted(self._examples.keys()):
            example = self._examples[name]
            lines.append(f"{name:<12} {example.category.value:<10} {example.title}")

        lines.extend(
            [
                "",
                "提示: 使用 :examples <name> 查看详细示例",
                "      例如: :examples chat",
            ]
        )

        return "\n".join(lines)

    def show_category_examples(self, category: ExampleCategory) -> str:
        """
        显示指定分类的示例

        Args:
            category: 示例分类

        Returns:
            格式化的示例列表文本
        """
        examples = self.get_examples_by_category(category)

        if not examples:
            return f"分类 '{category.value}' 下暂无示例"

        lines = [
            f"\n【{category.value} 分类示例】\n",
        ]

        for example in examples:
            lines.append(f"  {example.name:<12} - {example.title}")

        return "\n".join(lines)

    def register_example(self, example: Example) -> None:
        """
        注册自定义示例

        Args:
            example: 示例对象
        """
        self._examples[example.name] = example
        logger.info(f"已注册示例: {example.name}")

    def unregister_example(self, name: str) -> bool:
        """
        注销示例

        Args:
            name: 示例名称

        Returns:
            是否成功注销
        """
        if name in self._examples:
            del self._examples[name]
            logger.info(f"已注销示例: {name}")
            return True
        return False

    def has_example(self, name: str) -> bool:
        """
        检查示例是否存在

        Args:
            name: 示例名称

        Returns:
            是否存在
        """
        return name in self._examples

    def search_examples(self, keyword: str) -> list[Example]:
        """
        搜索示例

        Args:
            keyword: 搜索关键词

        Returns:
            匹配的示例列表
        """
        keyword_lower = keyword.lower()
        results = []

        for example in self._examples.values():
            if (
                keyword_lower in example.name.lower()
                or keyword_lower in example.title.lower()
                or keyword_lower in example.description.lower()
            ):
                results.append(example)

        return results


# 全局示例注册表实例
_example_registry: ExampleRegistry | None = None


def get_example_registry() -> ExampleRegistry:
    """
    获取全局示例注册表实例

    Returns:
        ExampleRegistry 单例实例
    """
    global _example_registry
    if _example_registry is None:
        _example_registry = ExampleRegistry()
    return _example_registry


def show_examples(name: str | None = None) -> str:
    """
    便捷函数：显示示例

    Args:
        name: 示例名称，None 表示显示所有

    Returns:
        示例文本
    """
    registry = get_example_registry()

    if name is None:
        return registry.show_all_examples()

    return registry.show_example(name)


def get_example(name: str) -> Example | None:
    """
    便捷函数：获取示例

    Args:
        name: 示例名称

    Returns:
        Example 对象
    """
    return get_example_registry().get_example(name)


def list_examples(category: str | None = None) -> list[str]:
    """
    便捷函数：列表示例

    Args:
        category: 分类名称，None 表示所有

    Returns:
        示例名称列表
    """
    cat = ExampleCategory(category) if category else None
    return get_example_registry().list_examples(cat)
