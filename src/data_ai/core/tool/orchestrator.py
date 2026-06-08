"""
DATA-AI 智能工具编排系统

参考 Trae Agent 和 Codex CLI 的工具调度机制，实现：
- 工具依赖关系分析与解析
- 最优执行计划生成
- 并行执行优化
- 冲突检测与处理
- 资源估算与管理
- 执行监控与瓶颈检测
- 预定义工具链管理

核心组件：
- ToolDependency: 工具依赖关系定义
- ExecutionPlan: 执行计划
- ToolOrchestrator: 工具编排器
- ExecutionMonitor: 执行监控器
- ToolChain: 工具链管理
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections import defaultdict, deque
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import (
    Any,
    TypeVar,
)

from data_ai.core.tool.registry import get_tool_registry

from ...utils.exceptions import ToolException, ToolExecutionError, ToolNotFoundError
from ...utils.logging import get_logger

logger = get_logger(__name__)

# 类型变量
T = TypeVar("T")
ToolCallable = Callable[..., Coroutine[Any, Any, dict[str, Any]]]


# ─── 枚举定义 ────────────────────────────────────────────────────────────────


class RiskLevel(Enum):
    """风险等级"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ExecutionStatus(Enum):
    """执行状态"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class ConflictType(Enum):
    """冲突类型"""

    RESOURCE = "resource"  # 资源冲突（文件、网络等）
    DEPENDENCY = "dependency"  # 依赖冲突
    EXCLUSIVE = "exclusive"  # 互斥冲突
    ORDER = "order"  # 顺序冲突
    STATE = "state"  # 状态冲突


class OptimizationStrategy(Enum):
    """优化策略"""

    SPEED = "speed"  # 优先速度
    RESOURCE = "resource"  # 优先资源效率
    RELIABILITY = "reliability"  # 优先可靠性
    BALANCED = "balanced"  # 平衡策略


class FailureHandlingStrategy(Enum):
    """失败处理策略"""

    STOP = "stop"  # 停止执行
    SKIP = "skip"  # 跳过失败步骤
    RETRY = "retry"  # 重试
    ROLLBACK = "rollback"  # 回滚
    CONTINUE = "continue"  # 继续执行


# ─── 数据类定义 ──────────────────────────────────────────────────────────────


@dataclass
class ResourceRequirement:
    """资源需求定义"""

    cpu: float = 0.0  # CPU 使用率 (0-1)
    memory: float = 0.0  # 内存使用量 (MB)
    disk: float = 0.0  # 磁盘使用量 (MB)
    network: bool = False  # 是否需要网络
    file_handles: int = 0  # 文件句柄数
    timeout: float = 30.0  # 超时时间（秒）

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "cpu": self.cpu,
            "memory": self.memory,
            "disk": self.disk,
            "network": self.network,
            "file_handles": self.file_handles,
            "timeout": self.timeout,
        }

    def __add__(self, other: ResourceRequirement) -> ResourceRequirement:
        """资源需求相加"""
        return ResourceRequirement(
            cpu=self.cpu + other.cpu,
            memory=self.memory + other.memory,
            disk=self.disk + other.disk,
            network=self.network or other.network,
            file_handles=self.file_handles + other.file_handles,
            timeout=max(self.timeout, other.timeout),
        )


@dataclass
class ToolDependency:
    """
    工具依赖关系定义

    定义工具之间的依赖关系、冲突关系和资源需求。
    用于编排器分析工具调用顺序和并行执行策略。

    Attributes:
        tool_name: 工具名称
        depends_on: 依赖的工具列表（必须先执行）
        conflicts_with: 冲突的工具列表（不能同时执行）
        soft_depends_on: 软依赖（建议顺序，非强制）
        resource_requirements: 资源需求
        priority: 优先级 (1-10，数字越大优先级越高)
        can_run_parallel: 是否可以并行执行
        estimated_duration: 预估执行时间（秒）
        retry_count: 失败重试次数
        timeout: 超时时间（秒）

    Example:
        >>> dep = ToolDependency(
        ...     tool_name="file_write",
        ...     depends_on=["file_read"],
        ...     conflicts_with=["file_delete"],
        ...     estimated_duration=2.0,
        ... )
    """

    tool_name: str
    depends_on: list[str] = field(default_factory=list)
    conflicts_with: list[str] = field(default_factory=list)
    soft_depends_on: list[str] = field(default_factory=list)
    resource_requirements: ResourceRequirement = field(default_factory=ResourceRequirement)
    priority: int = 5
    can_run_parallel: bool = True
    estimated_duration: float = 1.0
    retry_count: int = 0
    timeout: float = 30.0

    def __post_init__(self):
        """初始化后验证"""
        if self.priority < 1 or self.priority > 10:
            raise ValueError(f"Priority must be between 1 and 10, got {self.priority}")

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "tool_name": self.tool_name,
            "depends_on": self.depends_on,
            "conflicts_with": self.conflicts_with,
            "soft_depends_on": self.soft_depends_on,
            "resource_requirements": self.resource_requirements.to_dict(),
            "priority": self.priority,
            "can_run_parallel": self.can_run_parallel,
            "estimated_duration": self.estimated_duration,
            "retry_count": self.retry_count,
            "timeout": self.timeout,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolDependency:
        """从字典创建"""
        resource_data = data.get("resource_requirements", {})
        resource_req = ResourceRequirement(
            cpu=resource_data.get("cpu", 0.0),
            memory=resource_data.get("memory", 0.0),
            disk=resource_data.get("disk", 0.0),
            network=resource_data.get("network", False),
            file_handles=resource_data.get("file_handles", 0),
            timeout=resource_data.get("timeout", 30.0),
        )
        return cls(
            tool_name=data["tool_name"],
            depends_on=data.get("depends_on", []),
            conflicts_with=data.get("conflicts_with", []),
            soft_depends_on=data.get("soft_depends_on", []),
            resource_requirements=resource_req,
            priority=data.get("priority", 5),
            can_run_parallel=data.get("can_run_parallel", True),
            estimated_duration=data.get("estimated_duration", 1.0),
            retry_count=data.get("retry_count", 0),
            timeout=data.get("timeout", 30.0),
        )


@dataclass
class ExecutionStep:
    """
    执行步骤

    表示执行计划中的单个步骤。

    Attributes:
        step_id: 步骤唯一标识
        tool_name: 工具名称
        arguments: 工具参数
        dependencies: 依赖的步骤ID列表
        status: 执行状态
        result: 执行结果
        start_time: 开始时间
        end_time: 结束时间
        error: 错误信息
        retry_count: 已重试次数
        parallel_group: 并行组ID（相同ID可并行执行）
    """

    step_id: str
    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    status: ExecutionStatus = ExecutionStatus.PENDING
    result: dict[str, Any] | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    error: str | None = None
    retry_count: int = 0
    parallel_group: int | None = None

    @property
    def duration(self) -> float | None:
        """获取执行时长（秒）"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "step_id": self.step_id,
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "dependencies": self.dependencies,
            "status": self.status.value,
            "result": self.result,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration": self.duration,
            "error": self.error,
            "retry_count": self.retry_count,
            "parallel_group": self.parallel_group,
        }


@dataclass
class ParallelGroup:
    """
    并行执行组

    表示可以并行执行的一组步骤。

    Attributes:
        group_id: 组ID
        steps: 步骤列表
        total_resources: 总资源需求
        estimated_duration: 预估执行时间
    """

    group_id: int
    steps: list[ExecutionStep] = field(default_factory=list)
    total_resources: ResourceRequirement = field(default_factory=ResourceRequirement)
    estimated_duration: float = 0.0

    def add_step(self, step: ExecutionStep) -> None:
        """添加步骤"""
        self.steps.append(step)
        self.total_resources = self.total_resources + step._resource_requirement
        self.estimated_duration = max(self.estimated_duration, step._estimated_duration)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "group_id": self.group_id,
            "steps": [s.to_dict() for s in self.steps],
            "total_resources": self.total_resources.to_dict(),
            "estimated_duration": self.estimated_duration,
        }


@dataclass
class ConflictInfo:
    """
    冲突信息

    描述检测到的工具冲突。

    Attributes:
        conflict_type: 冲突类型
        tools: 涉及的工具列表
        description: 冲突描述
        severity: 严重程度
        suggestion: 解决建议
    """

    conflict_type: ConflictType
    tools: list[str]
    description: str
    severity: RiskLevel
    suggestion: str

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "conflict_type": self.conflict_type.value,
            "tools": self.tools,
            "description": self.description,
            "severity": self.severity.value,
            "suggestion": self.suggestion,
        }


@dataclass
class ExecutionPlan:
    """
    执行计划

    包含完整的工具执行计划，包括步骤、并行组、
    资源估算和风险评估。

    Attributes:
        plan_id: 计划唯一标识
        steps: 执行步骤列表
        parallel_groups: 可并行执行的组
        estimated_time: 预估总执行时间（秒）
        risk_level: 风险等级
        resource_requirements: 总资源需求
        conflicts: 检测到的冲突列表
        created_at: 创建时间
        optimization_strategy: 优化策略

    Example:
        >>> plan = orchestrator.create_execution_plan([
        ...     ("file_read", {"path": "/tmp/test.txt"}),
        ...     ("file_write", {"path": "/tmp/output.txt", "content": "data"}),
        ... ])
        >>> await orchestrator.execute_plan(plan)
    """

    plan_id: str = field(default_factory=lambda: hashlib.md5(str(time.time()).encode()).hexdigest()[:12])
    steps: list[ExecutionStep] = field(default_factory=list)
    parallel_groups: list[ParallelGroup] = field(default_factory=list)
    estimated_time: float = 0.0
    risk_level: RiskLevel = RiskLevel.LOW
    resource_requirements: ResourceRequirement = field(default_factory=ResourceRequirement)
    conflicts: list[ConflictInfo] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    optimization_strategy: OptimizationStrategy = OptimizationStrategy.BALANCED

    @property
    def step_count(self) -> int:
        """获取步骤数量"""
        return len(self.steps)

    @property
    def parallel_group_count(self) -> int:
        """获取并行组数量"""
        return len(self.parallel_groups)

    @property
    def max_parallelism(self) -> int:
        """获取最大并行度"""
        if not self.parallel_groups:
            return 0
        return max(len(g.steps) for g in self.parallel_groups)

    def get_step(self, step_id: str) -> ExecutionStep | None:
        """获取指定步骤"""
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None

    def get_ready_steps(self) -> list[ExecutionStep]:
        """获取可执行的步骤（依赖已满足）"""
        completed_ids = {s.step_id for s in self.steps if s.status == ExecutionStatus.COMPLETED}
        failed_ids = {s.step_id for s in self.steps if s.status == ExecutionStatus.FAILED}

        ready = []
        for step in self.steps:
            if step.status != ExecutionStatus.PENDING:
                continue
            # 检查依赖是否满足
            deps_satisfied = all(dep_id in completed_ids for dep_id in step.dependencies)
            # 检查是否有失败的依赖
            deps_failed = any(dep_id in failed_ids for dep_id in step.dependencies)
            if deps_satisfied and not deps_failed:
                ready.append(step)

        return ready

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "plan_id": self.plan_id,
            "step_count": self.step_count,
            "parallel_group_count": self.parallel_group_count,
            "max_parallelism": self.max_parallelism,
            "estimated_time": self.estimated_time,
            "risk_level": self.risk_level.value,
            "resource_requirements": self.resource_requirements.to_dict(),
            "conflicts": [c.to_dict() for c in self.conflicts],
            "created_at": self.created_at.isoformat(),
            "optimization_strategy": self.optimization_strategy.value,
            "steps": [s.to_dict() for s in self.steps],
            "parallel_groups": [g.to_dict() for g in self.parallel_groups],
        }


# ─── 执行监控器 ──────────────────────────────────────────────────────────────


@dataclass
class ExecutionMetrics:
    """执行指标"""

    total_steps: int = 0
    completed_steps: int = 0
    failed_steps: int = 0
    skipped_steps: int = 0
    total_time: float = 0.0
    avg_step_time: float = 0.0
    max_step_time: float = 0.0
    min_step_time: float = float("inf")
    parallel_efficiency: float = 0.0
    resource_utilization: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "total_steps": self.total_steps,
            "completed_steps": self.completed_steps,
            "failed_steps": self.failed_steps,
            "skipped_steps": self.skipped_steps,
            "total_time": self.total_time,
            "avg_step_time": self.avg_step_time,
            "max_step_time": self.max_step_time,
            "min_step_time": self.min_step_time if self.min_step_time != float("inf") else 0,
            "parallel_efficiency": self.parallel_efficiency,
            "resource_utilization": self.resource_utilization,
        }


@dataclass
class BottleneckInfo:
    """瓶颈信息"""

    step_id: str
    tool_name: str
    duration: float
    expected_duration: float
    delay_ratio: float  # 实际时间/预期时间
    possible_causes: list[str]
    suggestions: list[str]

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "step_id": self.step_id,
            "tool_name": self.tool_name,
            "duration": self.duration,
            "expected_duration": self.expected_duration,
            "delay_ratio": self.delay_ratio,
            "possible_causes": self.possible_causes,
            "suggestions": self.suggestions,
        }


class ExecutionMonitor:
    """
    执行监控器

    监控工具执行过程，跟踪进度，检测瓶颈，
    提供优化建议，处理失败情况。

    Features:
        - 实时进度跟踪
        - 瓶颈检测与分析
        - 性能指标收集
        - 失败处理与恢复
        - 优化建议生成

    Example:
        >>> monitor = ExecutionMonitor()
        >>> monitor.start_tracking(plan)
        >>> # 执行过程中...
        >>> metrics = monitor.get_metrics()
        >>> bottlenecks = monitor.detect_bottlenecks()
    """

    def __init__(
        self,
        history_size: int = 100,
        bottleneck_threshold: float = 2.0,
    ):
        """
        初始化监控器

        Args:
            history_size: 历史记录大小
            bottleneck_threshold: 瓶颈检测阈值（实际时间/预期时间）
        """
        self.history_size = history_size
        self.bottleneck_threshold = bottleneck_threshold

        self._current_plan: ExecutionPlan | None = None
        self._start_time: float | None = None
        self._metrics = ExecutionMetrics()
        self._step_times: dict[str, float] = {}
        self._execution_history: list[dict[str, Any]] = []
        self._callbacks: dict[str, list[Callable]] = defaultdict(list)

        self.logger = get_logger(f"{__name__}.monitor")

    def start_tracking(self, plan: ExecutionPlan) -> None:
        """
        开始跟踪执行计划

        Args:
            plan: 执行计划
        """
        self._current_plan = plan
        self._start_time = time.time()
        self._metrics = ExecutionMetrics(total_steps=len(plan.steps))
        self._step_times.clear()

        self.logger.info(
            "开始跟踪执行计划",
            plan_id=plan.plan_id,
            step_count=len(plan.steps),
        )

    def track_progress(
        self,
        step: ExecutionStep,
        status: ExecutionStatus,
    ) -> None:
        """
        跟踪执行进度

        Args:
            step: 执行步骤
            status: 新状态
        """
        old_status = step.status
        step.status = status

        if status == ExecutionStatus.RUNNING:
            step.start_time = datetime.now()
            self._trigger_callback("step_start", step)

        elif status == ExecutionStatus.COMPLETED:
            step.end_time = datetime.now()
            self._metrics.completed_steps += 1
            if step.duration:
                self._step_times[step.step_id] = step.duration
                self._update_time_metrics(step.duration)
            self._trigger_callback("step_complete", step)

        elif status == ExecutionStatus.FAILED:
            step.end_time = datetime.now()
            self._metrics.failed_steps += 1
            self._trigger_callback("step_failed", step)

        elif status == ExecutionStatus.SKIPPED:
            self._metrics.skipped_steps += 1
            self._trigger_callback("step_skipped", step)

        # 更新总时间
        if self._start_time:
            self._metrics.total_time = time.time() - self._start_time

        self.logger.debug(
            "步骤状态更新",
            step_id=step.step_id,
            tool_name=step.tool_name,
            old_status=old_status.value,
            new_status=status.value,
        )

    def _update_time_metrics(self, duration: float) -> None:
        """更新时间指标"""
        times = list(self._step_times.values())
        self._metrics.avg_step_time = sum(times) / len(times)
        self._metrics.max_step_time = max(times)
        self._metrics.min_step_time = min(times)

    def detect_bottlenecks(self) -> list[BottleneckInfo]:
        """
        检测执行瓶颈

        Returns:
            瓶颈信息列表
        """
        bottlenecks = []

        if not self._current_plan:
            return bottlenecks

        for step in self._current_plan.steps:
            if step.status != ExecutionStatus.COMPLETED:
                continue

            if not step.duration:
                continue

            # 获取预期时间
            expected = self._get_expected_duration(step.tool_name)
            if expected <= 0:
                continue

            delay_ratio = step.duration / expected

            if delay_ratio >= self.bottleneck_threshold:
                bottleneck = BottleneckInfo(
                    step_id=step.step_id,
                    tool_name=step.tool_name,
                    duration=step.duration,
                    expected_duration=expected,
                    delay_ratio=delay_ratio,
                    possible_causes=self._analyze_causes(step, delay_ratio),
                    suggestions=self._generate_suggestions(step, delay_ratio),
                )
                bottlenecks.append(bottleneck)

        return bottlenecks

    def _get_expected_duration(self, tool_name: str) -> float:
        """获取工具预期执行时间"""
        # 从历史记录计算平均时间
        history_times = [
            h["duration"] for h in self._execution_history if h["tool_name"] == tool_name and h.get("duration")
        ]
        if history_times:
            return sum(history_times) / len(history_times)

        # 默认预期时间
        default_times = {
            "file_read": 0.5,
            "file_write": 0.5,
            "bash": 2.0,
            "python_execute": 3.0,
            "web_search": 5.0,
        }
        return default_times.get(tool_name, 1.0)

    def _analyze_causes(
        self,
        step: ExecutionStep,
        delay_ratio: float,
    ) -> list[str]:
        """分析瓶颈原因"""
        causes = []

        if step.tool_name in ["web_search", "http_request"]:
            causes.append("网络延迟或连接问题")

        if step.tool_name in ["file_read", "file_write"]:
            causes.append("磁盘I/O瓶颈")
            causes.append("文件过大")

        if step.tool_name in ["python_execute", "bash"]:
            causes.append("计算密集型任务")
            causes.append("资源竞争")

        if delay_ratio > 5.0:
            causes.append("可能存在死锁或无限循环")

        if not causes:
            causes.append("未知原因")

        return causes

    def _generate_suggestions(
        self,
        step: ExecutionStep,
        delay_ratio: float,
    ) -> list[str]:
        """生成优化建议"""
        suggestions = []

        if step.tool_name in ["web_search", "http_request"]:
            suggestions.append("考虑使用缓存减少网络请求")
            suggestions.append("增加超时时间或使用异步请求")

        if step.tool_name in ["file_read", "file_write"]:
            suggestions.append("使用流式读写处理大文件")
            suggestions.append("考虑使用内存缓存")

        if step.tool_name in ["python_execute", "bash"]:
            suggestions.append("优化算法复杂度")
            suggestions.append("使用并行处理")

        if delay_ratio > 3.0:
            suggestions.append("考虑将任务拆分为更小的子任务")

        return suggestions

    def suggest_optimizations(self) -> list[dict[str, Any]]:
        """
        建议优化方案

        Returns:
            优化建议列表
        """
        suggestions = []

        if not self._current_plan:
            return suggestions

        # 分析并行效率
        if self._metrics.total_time > 0:
            theoretical_min = sum(self._step_times.values())
            if theoretical_min > 0:
                efficiency = theoretical_min / (self._metrics.total_time * self._current_plan.max_parallelism)
                self._metrics.parallel_efficiency = efficiency

                if efficiency < 0.5:
                    suggestions.append(
                        {
                            "type": "parallelism",
                            "message": f"并行效率较低 ({efficiency:.1%})，考虑增加并行度",
                            "current_efficiency": efficiency,
                        }
                    )

        # 分析失败率
        if self._metrics.total_steps > 0:
            failure_rate = self._metrics.failed_steps / self._metrics.total_steps
            if failure_rate > 0.1:
                suggestions.append(
                    {
                        "type": "reliability",
                        "message": f"失败率较高 ({failure_rate:.1%})，建议增加重试机制",
                        "failure_rate": failure_rate,
                    }
                )

        # 分析平均执行时间
        if self._metrics.avg_step_time > 5.0:
            suggestions.append(
                {
                    "type": "performance",
                    "message": f"平均步骤执行时间较长 ({self._metrics.avg_step_time:.1f}s)",
                    "avg_time": self._metrics.avg_step_time,
                }
            )

        return suggestions

    def handle_failures(
        self,
        step: ExecutionStep,
        strategy: FailureHandlingStrategy = FailureHandlingStrategy.RETRY,
        max_retries: int = 3,
    ) -> ExecutionStep | None:
        """
        处理失败情况

        Args:
            step: 失败的步骤
            strategy: 失败处理策略
            max_retries: 最大重试次数

        Returns:
            重试时返回新的步骤，否则返回 None
        """
        self.logger.warning(
            "处理步骤失败",
            step_id=step.step_id,
            tool_name=step.tool_name,
            strategy=strategy.value,
            error=step.error,
        )

        if strategy == FailureHandlingStrategy.STOP:
            # 停止执行，标记所有待执行步骤为跳过
            if self._current_plan:
                for s in self._current_plan.steps:
                    if s.status == ExecutionStatus.PENDING:
                        s.status = ExecutionStatus.SKIPPED
            return None

        elif strategy == FailureHandlingStrategy.SKIP:
            # 跳过失败步骤
            step.status = ExecutionStatus.SKIPPED
            return None

        elif strategy == FailureHandlingStrategy.RETRY:
            # 重试
            if step.retry_count < max_retries:
                step.retry_count += 1
                step.status = ExecutionStatus.PENDING
                step.error = None
                step.start_time = None
                step.end_time = None
                return step
            return None

        elif strategy == FailureHandlingStrategy.CONTINUE:
            # 继续执行
            return None

        return None

    def get_metrics(self) -> ExecutionMetrics:
        """
        获取执行指标

        Returns:
            执行指标
        """
        return self._metrics

    def get_progress(self) -> dict[str, Any]:
        """
        获取执行进度

        Returns:
            进度信息
        """
        if not self._current_plan:
            return {"status": "no_plan"}

        total = self._metrics.total_steps
        completed = self._metrics.completed_steps
        failed = self._metrics.failed_steps
        skipped = self._metrics.skipped_steps

        progress = (completed + failed + skipped) / total if total > 0 else 0

        return {
            "plan_id": self._current_plan.plan_id,
            "total_steps": total,
            "completed_steps": completed,
            "failed_steps": failed,
            "skipped_steps": skipped,
            "pending_steps": total - completed - failed - skipped,
            "progress": progress,
            "elapsed_time": self._metrics.total_time,
            "estimated_remaining": self._estimate_remaining_time(),
        }

    def _estimate_remaining_time(self) -> float:
        """估算剩余时间"""
        if not self._current_plan:
            return 0

        pending_steps = [s for s in self._current_plan.steps if s.status == ExecutionStatus.PENDING]

        if not pending_steps:
            return 0

        avg_time = self._metrics.avg_step_time or 1.0
        parallelism = self._current_plan.max_parallelism or 1

        return (len(pending_steps) * avg_time) / parallelism

    def record_history(self, step: ExecutionStep) -> None:
        """
        记录执行历史

        Args:
            step: 执行步骤
        """
        record = {
            "tool_name": step.tool_name,
            "duration": step.duration,
            "success": step.status == ExecutionStatus.COMPLETED,
            "timestamp": datetime.now().isoformat(),
        }

        self._execution_history.append(record)

        # 限制历史记录大小
        if len(self._execution_history) > self.history_size:
            self._execution_history = self._execution_history[-self.history_size :]

    def on(self, event: str, callback: Callable) -> None:
        """
        注册事件回调

        Args:
            event: 事件名称 (step_start, step_complete, step_failed, step_skipped)
            callback: 回调函数
        """
        self._callbacks[event].append(callback)

    def _trigger_callback(self, event: str, step: ExecutionStep) -> None:
        """触发事件回调"""
        for callback in self._callbacks.get(event, []):
            try:
                callback(step)
            except Exception as e:
                self.logger.error(
                    "回调执行失败",
                    event=event,
                    error=str(e),
                )

    def stop_tracking(self) -> ExecutionMetrics:
        """
        停止跟踪

        Returns:
            最终执行指标
        """
        if self._start_time:
            self._metrics.total_time = time.time() - self._start_time

        self.logger.info(
            "停止跟踪执行计划",
            metrics=self._metrics.to_dict(),
        )

        return self._metrics


# ─── 工具链 ───────────────────────────────────────────────────────────────────


@dataclass
class ToolChainDefinition:
    """
    工具链定义

    定义预定义的工具链，用于常见任务的自动化执行。

    Attributes:
        name: 工具链名称
        description: 工具链描述
        tools: 工具列表（按执行顺序）
        default_args: 默认参数
        dependencies: 工具间依赖关系
        tags: 标签
    """

    name: str
    description: str
    tools: list[str]
    default_args: dict[str, dict[str, Any]] = field(default_factory=dict)
    dependencies: dict[str, list[str]] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "description": self.description,
            "tools": self.tools,
            "default_args": self.default_args,
            "dependencies": self.dependencies,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolChainDefinition:
        """从字典创建"""
        return cls(
            name=data["name"],
            description=data["description"],
            tools=data["tools"],
            default_args=data.get("default_args", {}),
            dependencies=data.get("dependencies", {}),
            tags=data.get("tags", []),
        )


class ToolChain:
    """
    工具链管理器

    管理预定义的工具链，支持工具链的自动组合、缓存和复用。

    Features:
        - 预定义常用工具链
        - 工具链自动组合
        - 工具链缓存和复用
        - 工具链参数化

    Example:
        >>> chain_manager = ToolChain()
        >>> chain_manager.register_builtin_chains()
        >>> plan = chain_manager.create_plan("file_processing", {
        ...     "input_path": "/data/input.txt",
        ...     "output_path": "/data/output.txt",
        ... })
    """

    def __init__(self, cache_size: int = 50):
        """
        初始化工具链管理器

        Args:
            cache_size: 缓存大小
        """
        self._chains: dict[str, ToolChainDefinition] = {}
        self._cache: dict[str, ExecutionPlan] = {}
        self._cache_size = cache_size

        self.logger = get_logger(f"{__name__}.toolchain")

    def register(self, chain: ToolChainDefinition) -> None:
        """
        注册工具链

        Args:
            chain: 工具链定义
        """
        self._chains[chain.name] = chain
        self.logger.info(f"注册工具链: {chain.name}", tools=chain.tools)

    def unregister(self, name: str) -> None:
        """
        注销工具链

        Args:
            name: 工具链名称
        """
        if name in self._chains:
            del self._chains[name]
            self.logger.info(f"注销工具链: {name}")

    def get(self, name: str) -> ToolChainDefinition | None:
        """
        获取工具链

        Args:
            name: 工具链名称

        Returns:
            工具链定义，不存在则返回 None
        """
        return self._chains.get(name)

    def list_chains(self, tag: str | None = None) -> list[str]:
        """
        列出工具链

        Args:
            tag: 标签筛选

        Returns:
            工具链名称列表
        """
        if tag:
            return [name for name, chain in self._chains.items() if tag in chain.tags]
        return list(self._chains.keys())

    def create_plan(
        self,
        chain_name: str,
        args: dict[str, Any] | None = None,
        use_cache: bool = True,
    ) -> ExecutionPlan | None:
        """
        从工具链创建执行计划

        Args:
            chain_name: 工具链名称
            args: 参数
            use_cache: 是否使用缓存

        Returns:
            执行计划
        """
        chain = self.get(chain_name)
        if not chain:
            self.logger.warning(f"工具链不存在: {chain_name}")
            return None

        # 检查缓存
        cache_key = self._make_cache_key(chain_name, args)
        if use_cache and cache_key in self._cache:
            self.logger.debug(f"使用缓存的执行计划: {cache_key}")
            return self._cache[cache_key]

        # 创建执行计划
        plan = ExecutionPlan()

        for i, tool_name in enumerate(chain.tools):
            step_id = f"{chain_name}_{tool_name}_{i}"

            # 合并默认参数和传入参数
            tool_args = dict(chain.default_args.get(tool_name, {}))
            if args:
                tool_args.update(args)

            # 获取依赖
            deps = chain.dependencies.get(tool_name, [])
            dep_ids = [f"{chain_name}_{d}_{j}" for j, d in enumerate(chain.tools[:i]) if d in deps]

            step = ExecutionStep(
                step_id=step_id,
                tool_name=tool_name,
                arguments=tool_args,
                dependencies=dep_ids,
            )
            plan.steps.append(step)

        # 缓存计划
        if use_cache:
            self._cache[cache_key] = plan
            self._trim_cache()

        return plan

    def _make_cache_key(self, chain_name: str, args: dict[str, Any] | None) -> str:
        """生成缓存键"""
        key_data = f"{chain_name}:{json.dumps(args, sort_keys=True, default=str)}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def _trim_cache(self) -> None:
        """修剪缓存"""
        if len(self._cache) > self._cache_size:
            # 删除最旧的缓存项
            keys_to_remove = list(self._cache.keys())[: -self._cache_size]
            for key in keys_to_remove:
                del self._cache[key]

    def auto_combine(
        self,
        tools: list[str],
        strategy: OptimizationStrategy = OptimizationStrategy.BALANCED,
    ) -> ToolChainDefinition:
        """
        自动组合工具链

        根据工具列表自动分析依赖关系，生成最优工具链。

        Args:
            tools: 工具列表
            strategy: 优化策略

        Returns:
            生成的工具链定义
        """
        # 分析工具依赖
        dependencies = self._analyze_tool_dependencies(tools)

        # 拓扑排序
        sorted_tools = self._topological_sort(tools, dependencies)

        # 生成工具链
        chain = ToolChainDefinition(
            name=f"auto_chain_{hashlib.md5(str(sorted_tools).encode()).hexdigest()[:8]}",
            description=f"自动生成的工具链: {' -> '.join(sorted_tools)}",
            tools=sorted_tools,
            dependencies=dependencies,
            tags=["auto-generated"],
        )

        return chain

    def _analyze_tool_dependencies(self, tools: list[str]) -> dict[str, list[str]]:
        """分析工具依赖关系"""
        # 预定义的工具依赖规则
        dependency_rules = {
            "file_write": ["file_read"],
            "file_delete": ["file_read"],
            "file_move": ["file_read"],
            "file_copy": ["file_read"],
            "python_execute": ["file_read"],
            "bash": ["file_read"],
            "web_search": [],
        }

        dependencies = {}
        for tool in tools:
            deps = dependency_rules.get(tool, [])
            # 只保留在工具列表中的依赖
            dependencies[tool] = [d for d in deps if d in tools]

        return dependencies

    def _topological_sort(
        self,
        tools: list[str],
        dependencies: dict[str, list[str]],
    ) -> list[str]:
        """拓扑排序"""
        in_degree = {tool: 0 for tool in tools}

        # 计算入度
        for tool, deps in dependencies.items():
            for dep in deps:
                if dep in in_degree:
                    in_degree[tool] += 1

        # 使用优先队列（按工具名排序保证稳定性）
        queue = deque(sorted([t for t, d in in_degree.items() if d == 0]))
        result = []

        while queue:
            tool = queue.popleft()
            result.append(tool)

            # 更新依赖此工具的其他工具的入度
            for other_tool, deps in dependencies.items():
                if tool in deps:
                    in_degree[other_tool] -= 1
                    if in_degree[other_tool] == 0:
                        queue.append(other_tool)
                        # 保持排序
                        queue = deque(sorted(queue))

        return result

    def register_builtin_chains(self) -> None:
        """注册内置工具链"""
        # 文件处理链
        self.register(
            ToolChainDefinition(
                name="file_processing",
                description="文件读取、处理、写入链",
                tools=["file_read", "python_execute", "file_write"],
                dependencies={
                    "python_execute": ["file_read"],
                    "file_write": ["python_execute"],
                },
                tags=["file", "processing"],
            )
        )

        # 代码分析链
        self.register(
            ToolChainDefinition(
                name="code_analysis",
                description="代码读取、分析、报告生成链",
                tools=["file_read", "python_execute", "file_write"],
                dependencies={
                    "python_execute": ["file_read"],
                    "file_write": ["python_execute"],
                },
                tags=["code", "analysis"],
            )
        )

        # 网络搜索链
        self.register(
            ToolChainDefinition(
                name="web_research",
                description="网络搜索、信息提取、总结链",
                tools=["web_search", "python_execute", "file_write"],
                dependencies={
                    "python_execute": ["web_search"],
                    "file_write": ["python_execute"],
                },
                tags=["web", "research"],
            )
        )

        # 数据处理链
        self.register(
            ToolChainDefinition(
                name="data_pipeline",
                description="数据读取、转换、存储链",
                tools=["file_read", "python_execute", "file_write"],
                dependencies={
                    "python_execute": ["file_read"],
                    "file_write": ["python_execute"],
                },
                tags=["data", "pipeline"],
            )
        )

        # 项目分析链
        self.register(
            ToolChainDefinition(
                name="project_analysis",
                description="项目结构分析、代码检查、报告生成链",
                tools=["bash", "file_read", "python_execute", "file_write"],
                dependencies={
                    "file_read": ["bash"],
                    "python_execute": ["file_read"],
                    "file_write": ["python_execute"],
                },
                tags=["project", "analysis"],
            )
        )

        self.logger.info(f"已注册 {len(self._chains)} 个内置工具链")


# ─── 工具编排器 ───────────────────────────────────────────────────────────────


class ToolOrchestrator:
    """
    工具编排器

    智能工具编排系统的核心组件，负责：
    - 分析工具依赖关系
    - 创建最优执行计划
    - 优化并行执行
    - 检测工具冲突
    - 估算资源需求
    - 执行计划并监控

    参考 Trae Agent 和 Codex CLI 的工具调度机制实现。

    Features:
        - 智能依赖分析
        - 自动并行优化
        - 冲突检测与解决
        - 资源估算
        - 失败恢复
        - 执行监控

    Example:
        >>> orchestrator = ToolOrchestrator()
        >>> plan = orchestrator.create_execution_plan([
        ...     ("file_read", {"path": "/data/input.txt"}),
        ...     ("file_write", {"path": "/data/output.txt", "content": "..."}),
        ... ])
        >>> result = await orchestrator.execute_plan(plan)
    """

    def __init__(
        self,
        max_parallel: int = 4,
        default_timeout: float = 30.0,
        optimization_strategy: OptimizationStrategy = OptimizationStrategy.BALANCED,
        failure_strategy: FailureHandlingStrategy = FailureHandlingStrategy.RETRY,
        max_retries: int = 3,
    ):
        """
        初始化工具编排器

        Args:
            max_parallel: 最大并行数
            default_timeout: 默认超时时间（秒）
            optimization_strategy: 优化策略
            failure_strategy: 失败处理策略
            max_retries: 最大重试次数
        """
        self.max_parallel = max_parallel
        self.default_timeout = default_timeout
        self.optimization_strategy = optimization_strategy
        self.failure_strategy = failure_strategy
        self.max_retries = max_retries

        self._registry = get_tool_registry()
        self._monitor = ExecutionMonitor()
        self._toolchain = ToolChain()
        self._dependencies: dict[str, ToolDependency] = {}
        self._execution_lock = asyncio.Lock()

        self.logger = get_logger(f"{__name__}.orchestrator")

        # 注册默认依赖
        self._register_default_dependencies()

    def _register_default_dependencies(self) -> None:
        """注册默认工具依赖"""
        default_deps = [
            ToolDependency(
                tool_name="file_read",
                estimated_duration=0.5,
                can_run_parallel=True,
            ),
            ToolDependency(
                tool_name="file_write",
                conflicts_with=["file_delete", "file_move"],
                estimated_duration=0.5,
                can_run_parallel=False,
            ),
            ToolDependency(
                tool_name="file_delete",
                conflicts_with=["file_read", "file_write", "file_move", "file_copy"],
                estimated_duration=0.3,
                can_run_parallel=False,
            ),
            ToolDependency(
                tool_name="file_move",
                conflicts_with=["file_delete", "file_copy"],
                estimated_duration=0.5,
                can_run_parallel=False,
            ),
            ToolDependency(
                tool_name="python_execute",
                resource_requirements=ResourceRequirement(cpu=0.5, memory=100),
                estimated_duration=3.0,
                can_run_parallel=True,
            ),
            ToolDependency(
                tool_name="bash",
                resource_requirements=ResourceRequirement(cpu=0.3, memory=50),
                estimated_duration=2.0,
                can_run_parallel=True,
            ),
            ToolDependency(
                tool_name="web_search",
                resource_requirements=ResourceRequirement(network=True),
                estimated_duration=5.0,
                can_run_parallel=True,
            ),
        ]

        for dep in default_deps:
            self._dependencies[dep.tool_name] = dep

    def register_dependency(self, dependency: ToolDependency) -> None:
        """
        注册工具依赖

        Args:
            dependency: 工具依赖定义
        """
        self._dependencies[dependency.tool_name] = dependency
        self.logger.info(f"注册工具依赖: {dependency.tool_name}")

    def get_dependency(self, tool_name: str) -> ToolDependency | None:
        """
        获取工具依赖

        Args:
            tool_name: 工具名称

        Returns:
            工具依赖定义
        """
        return self._dependencies.get(tool_name)

    def analyze_dependencies(
        self,
        tools: list[str],
    ) -> dict[str, ToolDependency]:
        """
        分析工具依赖关系

        分析给定工具列表的依赖关系，返回依赖图。

        Args:
            tools: 工具名称列表

        Returns:
            工具依赖映射
        """
        result = {}

        for tool_name in tools:
            if tool_name in self._dependencies:
                result[tool_name] = self._dependencies[tool_name]
            else:
                # 创建默认依赖
                result[tool_name] = ToolDependency(
                    tool_name=tool_name,
                    estimated_duration=1.0,
                    can_run_parallel=True,
                )

        self.logger.debug(
            "分析工具依赖",
            tools=tools,
            dependencies={k: v.to_dict() for k, v in result.items()},
        )

        return result

    def detect_conflicts(
        self,
        tools: list[str],
    ) -> list[ConflictInfo]:
        """
        检测工具冲突

        检测给定工具列表中存在的冲突。

        Args:
            tools: 工具名称列表

        Returns:
            冲突信息列表
        """
        conflicts = []
        dependencies = self.analyze_dependencies(tools)

        # 检测冲突
        for i, tool1 in enumerate(tools):
            dep1 = dependencies.get(tool1)
            if not dep1:
                continue

            for tool2 in tools[i + 1 :]:
                dep2 = dependencies.get(tool2)
                if not dep2:
                    continue

                # 检查冲突列表
                if tool2 in dep1.conflicts_with or tool1 in dep2.conflicts_with:
                    conflicts.append(
                        ConflictInfo(
                            conflict_type=ConflictType.EXCLUSIVE,
                            tools=[tool1, tool2],
                            description=f"工具 '{tool1}' 和 '{tool2}' 存在互斥冲突",
                            severity=RiskLevel.HIGH,
                            suggestion="避免同时执行这两个工具，或调整执行顺序",
                        )
                    )

                # 检查资源冲突
                if not dep1.can_run_parallel or not dep2.can_run_parallel:
                    if dep1.resource_requirements.file_handles > 0 and dep2.resource_requirements.file_handles > 0:
                        conflicts.append(
                            ConflictInfo(
                                conflict_type=ConflictType.RESOURCE,
                                tools=[tool1, tool2],
                                description=f"工具 '{tool1}' 和 '{tool2}' 可能存在资源竞争",
                                severity=RiskLevel.MEDIUM,
                                suggestion="考虑串行执行或限制并行度",
                            )
                        )

        self.logger.debug(
            "检测工具冲突",
            tools=tools,
            conflict_count=len(conflicts),
        )

        return conflicts

    def estimate_resources(
        self,
        tools: list[str],
    ) -> ResourceRequirement:
        """
        估算资源需求

        估算执行给定工具列表所需的资源。

        Args:
            tools: 工具名称列表

        Returns:
            资源需求
        """
        dependencies = self.analyze_dependencies(tools)

        total = ResourceRequirement()
        for tool_name in tools:
            dep = dependencies.get(tool_name)
            if dep:
                total = total + dep.resource_requirements

        return total

    def create_execution_plan(
        self,
        tool_calls: list[tuple[str, dict[str, Any]]],
        strategy: OptimizationStrategy | None = None,
    ) -> ExecutionPlan:
        """
        创建执行计划

        根据工具调用列表创建最优执行计划。

        Args:
            tool_calls: 工具调用列表，每个元素为 (工具名, 参数) 元组
            strategy: 优化策略，None 使用默认策略

        Returns:
            执行计划
        """
        strategy = strategy or self.optimization_strategy

        plan = ExecutionPlan(optimization_strategy=strategy)

        # 提取工具名称
        tool_names = [call[0] for call in tool_calls]

        # 分析依赖
        dependencies = self.analyze_dependencies(tool_names)

        # 检测冲突
        conflicts = self.detect_conflicts(tool_names)
        plan.conflicts = conflicts

        # 创建步骤
        steps = []
        for i, (tool_name, args) in enumerate(tool_calls):
            step_id = f"step_{i:03d}"
            dep = dependencies.get(tool_name)

            # 计算依赖步骤
            dep_step_ids = []
            if dep:
                for dep_tool in dep.depends_on:
                    # 找到依赖工具的步骤
                    for j, (t, _) in enumerate(tool_calls[:i]):
                        if t == dep_tool:
                            dep_step_ids.append(f"step_{j:03d}")

            step = ExecutionStep(
                step_id=step_id,
                tool_name=tool_name,
                arguments=args,
                dependencies=dep_step_ids,
            )
            # 存储资源需求用于后续计算
            step._resource_requirement = dep.resource_requirements if dep else ResourceRequirement()
            step._estimated_duration = dep.estimated_duration if dep else 1.0

            steps.append(step)

        plan.steps = steps

        # 优化并行执行
        self._optimize_parallel_groups(plan, dependencies, strategy)

        # 计算预估时间
        self._estimate_total_time(plan, dependencies)

        # 估算资源
        plan.resource_requirements = self.estimate_resources(tool_names)

        # 评估风险
        plan.risk_level = self._assess_risk(plan, conflicts)

        self.logger.info(
            "创建执行计划",
            plan_id=plan.plan_id,
            step_count=len(plan.steps),
            parallel_groups=len(plan.parallel_groups),
            estimated_time=plan.estimated_time,
            risk_level=plan.risk_level.value,
        )

        return plan

    def _optimize_parallel_groups(
        self,
        plan: ExecutionPlan,
        dependencies: dict[str, ToolDependency],
        strategy: OptimizationStrategy,
    ) -> None:
        """优化并行分组"""
        # 构建依赖图
        graph = defaultdict(set)
        in_degree = defaultdict(int)

        for step in plan.steps:
            for dep_id in step.dependencies:
                graph[dep_id].add(step.step_id)
                in_degree[step.step_id] += 1

        # 拓扑排序分层
        layers = []
        current_layer = [s.step_id for s in plan.steps if in_degree[s.step_id] == 0]

        while current_layer:
            layers.append(sorted(current_layer))  # 排序保证稳定性
            next_layer = []

            for step_id in current_layer:
                for next_id in graph[step_id]:
                    in_degree[next_id] -= 1
                    if in_degree[next_id] == 0:
                        next_layer.append(next_id)

            current_layer = next_layer

        # 根据策略调整并行度
        if strategy == OptimizationStrategy.RESOURCE:
            max(1, self.max_parallel // 2)
        elif strategy == OptimizationStrategy.RELIABILITY:
            max(1, self.max_parallel // 3)

        # 创建并行组
        for group_id, layer in enumerate(layers):
            group = ParallelGroup(group_id=group_id)

            for step_id in layer:
                step = plan.get_step(step_id)
                if step:
                    step.parallel_group = group_id

                    # 检查是否可以并行
                    dep = dependencies.get(step.tool_name)
                    if dep and not dep.can_run_parallel:
                        # 不并行的步骤单独成组
                        if group.steps:
                            plan.parallel_groups.append(group)
                            group_id += 1
                            group = ParallelGroup(group_id=group_id)

                    group.steps.append(step)

            if group.steps:
                plan.parallel_groups.append(group)

    def _estimate_total_time(
        self,
        plan: ExecutionPlan,
        dependencies: dict[str, ToolDependency],
    ) -> None:
        """估算总执行时间"""
        total_time = 0.0

        for group in plan.parallel_groups:
            # 并行组的时间取决于最长的步骤
            group_max_time = 0.0
            for step in group.steps:
                dep = dependencies.get(step.tool_name)
                step_time = dep.estimated_duration if dep else 1.0
                group_max_time = max(group_max_time, step_time)

            total_time += group_max_time
            group.estimated_duration = group_max_time

        plan.estimated_time = total_time

    def _assess_risk(
        self,
        plan: ExecutionPlan,
        conflicts: list[ConflictInfo],
    ) -> RiskLevel:
        """评估风险等级"""
        if not conflicts:
            return RiskLevel.LOW

        # 根据冲突严重程度评估
        max_severity = max(c.severity for c in conflicts)

        # 根据步骤数量调整
        if len(plan.steps) > 10:
            if max_severity == RiskLevel.LOW:
                return RiskLevel.MEDIUM
            elif max_severity == RiskLevel.MEDIUM:
                return RiskLevel.HIGH

        return max_severity

    def optimize_parallel(
        self,
        plan: ExecutionPlan,
        max_workers: int | None = None,
    ) -> ExecutionPlan:
        """
        优化并行执行

        重新分析执行计划，优化并行执行策略。

        Args:
            plan: 执行计划
            max_workers: 最大工作线程数

        Returns:
            优化后的执行计划
        """
        max_workers = max_workers or self.max_parallel

        # 重新分析依赖
        tool_names = [s.tool_name for s in plan.steps]
        dependencies = self.analyze_dependencies(tool_names)

        # 重新优化并行组
        self._optimize_parallel_groups(plan, dependencies, self.optimization_strategy)

        return plan

    async def execute_plan(
        self,
        plan: ExecutionPlan,
        context: dict[str, Any] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """
        执行计划

        执行执行计划中的所有步骤，返回执行结果。

        Args:
            plan: 执行计划
            context: 执行上下文

        Returns:
            步骤ID到执行结果的映射
        """
        async with self._execution_lock:
            self._monitor.start_tracking(plan)

            results: dict[str, dict[str, Any]] = {}

            try:
                # 按并行组执行
                for group in plan.parallel_groups:
                    # 获取可执行的步骤
                    ready_steps = [step for step in group.steps if step.status == ExecutionStatus.PENDING]

                    if not ready_steps:
                        continue

                    # 并行执行
                    tasks = [self._execute_step(step, context) for step in ready_steps]

                    group_results = await asyncio.gather(*tasks, return_exceptions=True)

                    # 处理结果
                    for step, result in zip(ready_steps, group_results):
                        if isinstance(result, Exception):
                            step.error = str(result)
                            step.status = ExecutionStatus.FAILED
                            self._monitor.track_progress(step, ExecutionStatus.FAILED)

                            # 失败处理
                            if self.failure_strategy != FailureHandlingStrategy.CONTINUE:
                                retry_step = self._monitor.handle_failures(
                                    step,
                                    self.failure_strategy,
                                    self.max_retries,
                                )
                                if retry_step:
                                    # 重试
                                    retry_result = await self._execute_step(retry_step, context)
                                    results[step.step_id] = retry_result
                                    continue

                            results[step.step_id] = {
                                "success": False,
                                "data": None,
                                "error": str(result),
                                "tool_name": step.tool_name,
                            }
                        else:
                            results[step.step_id] = result
                            if result.get("success"):
                                self._monitor.track_progress(step, ExecutionStatus.COMPLETED)
                            else:
                                self._monitor.track_progress(step, ExecutionStatus.FAILED)

                        self._monitor.record_history(step)

                return results

            except Exception as e:
                self.logger.error(
                    "执行计划失败",
                    plan_id=plan.plan_id,
                    error=str(e),
                )
                raise ToolExecutionError(
                    tool="orchestrator",
                    message=f"执行计划失败: {e}",
                )

            finally:
                self._monitor.stop_tracking()

    async def _execute_step(
        self,
        step: ExecutionStep,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        执行单个步骤

        Args:
            step: 执行步骤
            context: 执行上下文

        Returns:
            执行结果
        """
        self._monitor.track_progress(step, ExecutionStatus.RUNNING)

        try:
            # 合并上下文
            args = dict(step.arguments)
            if context:
                args.setdefault("_context", context)

            # 获取超时时间
            dep = self._dependencies.get(step.tool_name)
            timeout = dep.timeout if dep else self.default_timeout

            # 执行工具
            result = await asyncio.wait_for(
                self._registry.execute(step.tool_name, args),
                timeout=timeout,
            )

            result_dict = {
                "success": True,
                "data": result,
                "error": None,
                "tool_name": step.tool_name,
            }
            step.result = result_dict

            if result_dict.get("success"):
                self.logger.info(
                    "步骤执行成功",
                    step_id=step.step_id,
                    tool_name=step.tool_name,
                )
            else:
                self.logger.warning(
                    "步骤执行失败",
                    step_id=step.step_id,
                    tool_name=step.tool_name,
                    error=result_dict.get("error"),
                )

            return result_dict

        except asyncio.TimeoutError:
            error_msg = f"步骤执行超时: {step.tool_name}"
            self.logger.error(
                "步骤执行超时",
                step_id=step.step_id,
                tool_name=step.tool_name,
            )
            return {
                "success": False,
                "data": None,
                "error": error_msg,
                "tool_name": step.tool_name,
            }

        except ToolNotFoundError:
            error_msg = f"工具不存在: {step.tool_name}"
            self.logger.error(
                "工具不存在",
                step_id=step.step_id,
                tool_name=step.tool_name,
            )
            return {
                "success": False,
                "data": None,
                "error": error_msg,
                "tool_name": step.tool_name,
            }

        except Exception as e:
            self.logger.error(
                "步骤执行异常",
                step_id=step.step_id,
                tool_name=step.tool_name,
                error=str(e),
            )
            return {
                "success": False,
                "data": None,
                "error": str(e),
                "tool_name": step.tool_name,
            }

    def get_monitor(self) -> ExecutionMonitor:
        """获取执行监控器"""
        return self._monitor

    def get_toolchain(self) -> ToolChain:
        """获取工具链管理器"""
        return self._toolchain

    async def execute_tool_chain(
        self,
        chain_name: str,
        args: dict[str, Any] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """
        执行工具链

        Args:
            chain_name: 工具链名称
            args: 参数

        Returns:
            执行结果
        """
        plan = self._toolchain.create_plan(chain_name, args)
        if not plan:
            raise ToolException(f"工具链不存在: {chain_name}")

        return await self.execute_plan(plan)


# ─── 全局实例 ─────────────────────────────────────────────────────────────────

_orchestrator: ToolOrchestrator | None = None
_toolchain: ToolChain | None = None


def get_orchestrator() -> ToolOrchestrator:
    """获取全局工具编排器"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = ToolOrchestrator()
    return _orchestrator


def get_toolchain() -> ToolChain:
    """获取全局工具链管理器"""
    global _toolchain
    if _toolchain is None:
        _toolchain = ToolChain()
        _toolchain.register_builtin_chains()
    return _toolchain


# ─── 便捷函数 ─────────────────────────────────────────────────────────────────


async def execute_tools(
    tool_calls: list[tuple[str, dict[str, Any]]],
    max_parallel: int = 4,
) -> dict[str, dict[str, Any]]:
    """
    便捷函数：执行工具列表

    Args:
        tool_calls: 工具调用列表
        max_parallel: 最大并行数

    Returns:
        执行结果
    """
    orchestrator = ToolOrchestrator(max_parallel=max_parallel)
    plan = orchestrator.create_execution_plan(tool_calls)
    return await orchestrator.execute_plan(plan)


async def execute_chain(
    chain_name: str,
    args: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """
    便捷函数：执行工具链

    Args:
        chain_name: 工具链名称
        args: 参数

    Returns:
        执行结果
    """
    orchestrator = get_orchestrator()
    return await orchestrator.execute_tool_chain(chain_name, args)


# ─── 导出 ─────────────────────────────────────────────────────────────────────

__all__ = [
    # 枚举
    "RiskLevel",
    "ExecutionStatus",
    "ConflictType",
    "OptimizationStrategy",
    "FailureHandlingStrategy",
    # 数据类
    "ResourceRequirement",
    "ToolDependency",
    "ExecutionStep",
    "ParallelGroup",
    "ConflictInfo",
    "ExecutionPlan",
    "ExecutionMetrics",
    "BottleneckInfo",
    "ToolChainDefinition",
    # 核心类
    "ExecutionMonitor",
    "ToolChain",
    "ToolOrchestrator",
    # 全局实例
    "get_orchestrator",
    "get_toolchain",
    # 便捷函数
    "execute_tools",
    "execute_chain",
]
