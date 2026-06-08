"""
DATA-AI Agent 工作流引擎

提供多 Agent 协作的工作流定义和执行能力，支持复杂任务的编排和调度。
参考 Hermes 和 Trae 的多 Agent 架构设计。
"""

from __future__ import annotations

import asyncio
import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from data_ai.core.llm.manager import ChatResponse

from ...utils.exceptions import AgentException
from ...utils.logging import get_logger
from .base import BaseAgent
from .collaboration import (
    AgentRole,
)

logger = get_logger(__name__)


class StepStatus(Enum):
    """步骤状态"""

    PENDING = "pending"  # 待执行
    WAITING = "waiting"  # 等待依赖
    RUNNING = "running"  # 执行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败
    SKIPPED = "skipped"  # 已跳过
    PAUSED = "paused"  # 已暂停


class StepType(Enum):
    """步骤类型"""

    TASK = "task"  # 任务步骤：执行一个任务
    PARALLEL = "parallel"  # 并行步骤：并行执行多个子步骤
    SEQUENTIAL = "sequential"  # 顺序步骤：顺序执行多个子步骤
    CONDITION = "condition"  # 条件步骤：根据条件选择执行路径
    LOOP = "loop"  # 循环步骤：重复执行
    WAIT = "wait"  # 等待步骤：等待一段时间或条件
    SUBWORKFLOW = "subworkflow"  # 子工作流：嵌套执行另一个工作流
    CHECKPOINT = "checkpoint"  # 检查点：保存状态


class WorkflowStatus(Enum):
    """工作流状态"""

    CREATED = "created"  # 已创建
    RUNNING = "running"  # 运行中
    PAUSED = "paused"  # 已暂停
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败
    CANCELLED = "cancelled"  # 已取消


class WorkflowEvent(Enum):
    """工作流事件"""

    STARTED = "started"  # 工作流开始
    STEP_STARTED = "step_started"  # 步骤开始
    STEP_COMPLETED = "step_completed"  # 步骤完成
    STEP_FAILED = "step_failed"  # 步骤失败
    PAUSED = "paused"  # 工作流暂停
    RESUMED = "resumed"  # 工作流恢复
    COMPLETED = "completed"  # 工作流完成
    FAILED = "failed"  # 工作流失败
    CANCELLED = "cancelled"  # 工作流取消


@dataclass
class WorkflowStep:
    """
    工作流步骤

    表示工作流中的一个执行单元
    """

    step_id: str
    name: str
    step_type: StepType = StepType.TASK
    description: str = ""
    agent_id: str | None = None  # 执行的 Agent ID
    role: AgentRole | None = None  # 需要的角色
    task_description: str | None = None  # 任务描述
    depends_on: list[str] = field(default_factory=list)  # 依赖的步骤 ID
    condition: str | None = None  # 条件表达式
    max_retries: int = 3
    timeout_seconds: float = 300.0
    metadata: dict[str, Any] = field(default_factory=dict)

    # 子步骤（用于 PARALLEL 和 SEQUENTIAL 类型）
    sub_steps: list[WorkflowStep] = field(default_factory=list)

    # 循环配置（用于 LOOP 类型）
    loop_count: int = 1
    loop_condition: str | None = None

    # 等待配置（用于 WAIT 类型）
    wait_seconds: float = 0
    wait_condition: str | None = None

    # 子工作流（用于 SUBWORKFLOW 类型）
    sub_workflow_id: str | None = None

    # 运行时状态
    status: StepStatus = StepStatus.PENDING
    result: ChatResponse | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    retry_count: int = 0

    def __post_init__(self):
        """初始化后处理"""
        if not self.step_id:
            self.step_id = str(uuid.uuid4())

    @property
    def duration_ms(self) -> float | None:
        """计算执行时长（毫秒）"""
        if self.started_at and self.completed_at:
            delta = self.completed_at - self.started_at
            return delta.total_seconds() * 1000
        return None

    def is_ready(self, completed_steps: set[str]) -> bool:
        """
        检查步骤是否就绪（依赖已满足）

        Args:
            completed_steps: 已完成的步骤 ID 集合

        Returns:
            是否就绪
        """
        if self.status != StepStatus.PENDING:
            return False

        return all(dep_id in completed_steps for dep_id in self.depends_on)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "step_id": self.step_id,
            "name": self.name,
            "step_type": self.step_type.value,
            "description": self.description,
            "agent_id": self.agent_id,
            "role": self.role.value if self.role else None,
            "depends_on": self.depends_on,
            "status": self.status.value,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "retry_count": self.retry_count,
            "duration_ms": self.duration_ms,
        }


@dataclass
class WorkflowDefinition:
    """
    工作流定义

    定义一个完整的工作流
    """

    workflow_id: str
    name: str
    description: str = ""
    version: str = "1.0.0"
    steps: list[WorkflowStep] = field(default_factory=list)
    variables: dict[str, Any] = field(default_factory=dict)
    timeout_seconds: float = 3600.0  # 默认 1 小时
    max_retries: int = 3
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """初始化后处理"""
        if not self.workflow_id:
            self.workflow_id = str(uuid.uuid4())

    def get_step(self, step_id: str) -> WorkflowStep | None:
        """获取步骤"""
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None

    def get_entry_steps(self) -> list[WorkflowStep]:
        """获取入口步骤（无依赖的步骤）"""
        return [s for s in self.steps if not s.depends_on]

    def get_step_dependencies(self, step_id: str) -> list[str]:
        """获取步骤的依赖"""
        step = self.get_step(step_id)
        return step.depends_on if step else []

    def get_dependent_steps(self, step_id: str) -> list[str]:
        """获取依赖于指定步骤的步骤"""
        return [s.step_id for s in self.steps if step_id in s.depends_on]

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "workflow_id": self.workflow_id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "steps": [s.to_dict() for s in self.steps],
            "variables": self.variables,
            "timeout_seconds": self.timeout_seconds,
            "max_retries": self.max_retries,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkflowDefinition:
        """从字典创建"""
        steps = []
        for step_data in data.get("steps", []):
            step = WorkflowStep(
                step_id=step_data.get("step_id", str(uuid.uuid4())),
                name=step_data["name"],
                step_type=StepType(step_data.get("step_type", "task")),
                description=step_data.get("description", ""),
                depends_on=step_data.get("depends_on", []),
            )
            steps.append(step)

        return cls(
            workflow_id=data.get("workflow_id", str(uuid.uuid4())),
            name=data["name"],
            description=data.get("description", ""),
            version=data.get("version", "1.0.0"),
            steps=steps,
            variables=data.get("variables", {}),
            timeout_seconds=data.get("timeout_seconds", 3600.0),
            max_retries=data.get("max_retries", 3),
            metadata=data.get("metadata", {}),
        )


@dataclass
class WorkflowExecution:
    """
    工作流执行记录

    记录一次工作流的执行过程
    """

    execution_id: str
    workflow_id: str
    status: WorkflowStatus = WorkflowStatus.CREATED
    started_at: datetime | None = None
    completed_at: datetime | None = None
    step_results: dict[str, ChatResponse] = field(default_factory=dict)
    step_errors: dict[str, str] = field(default_factory=dict)
    variables: dict[str, Any] = field(default_factory=dict)
    current_step_id: str | None = None
    checkpoint_data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def __post_init__(self):
        """初始化后处理"""
        if not self.execution_id:
            self.execution_id = str(uuid.uuid4())

    @property
    def duration_ms(self) -> float | None:
        """计算执行时长（毫秒）"""
        if self.started_at and self.completed_at:
            delta = self.completed_at - self.started_at
            return delta.total_seconds() * 1000
        return None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "execution_id": self.execution_id,
            "workflow_id": self.workflow_id,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "current_step_id": self.current_step_id,
            "step_results": {k: {"content": v.content} for k, v in self.step_results.items()},
            "step_errors": self.step_errors,
            "variables": self.variables,
            "error": self.error,
            "duration_ms": self.duration_ms,
        }


class WorkflowEngine:
    """
    工作流引擎

    负责工作流的执行、调度、监控和管理
    """

    def __init__(
        self,
        name: str = "workflow_engine",
        max_concurrent_workflows: int = 10,
        max_concurrent_steps: int = 5,
        default_timeout_seconds: float = 3600.0,
        event_callback: Callable[[WorkflowEvent, dict[str, Any]], Awaitable[None]] | None = None,
    ):
        """
        初始化工作流引擎

        Args:
            name: 引擎名称
            max_concurrent_workflows: 最大并发工作流数
            max_concurrent_steps: 最大并发步骤数
            default_timeout_seconds: 默认超时时间
            event_callback: 事件回调函数
        """
        self.name = name
        self.max_concurrent_workflows = max_concurrent_workflows
        self.max_concurrent_steps = max_concurrent_steps
        self.default_timeout_seconds = default_timeout_seconds
        self.event_callback = event_callback

        # 工作流定义存储
        self._definitions: dict[str, WorkflowDefinition] = {}

        # 执行记录存储
        self._executions: dict[str, WorkflowExecution] = {}

        # Agent 注册表
        self._agents: dict[str, BaseAgent] = {}

        # 运行中的执行
        self._running_executions: set[str] = set()

        # 暂停信号
        self._pause_signals: dict[str, asyncio.Event] = {}

        # 取消信号
        self._cancel_signals: dict[str, bool] = {}

        self.logger = get_logger(f"{__name__}.{name}")

    def register_agent(self, agent: BaseAgent) -> None:
        """
        注册 Agent

        Args:
            agent: Agent 实例
        """
        self._agents[agent.name] = agent
        self.logger.debug("Agent 已注册", agent_id=agent.name)

    def unregister_agent(self, agent_id: str) -> None:
        """
        注销 Agent

        Args:
            agent_id: Agent ID
        """
        self._agents.pop(agent_id, None)

    def get_agent(self, agent_id: str) -> BaseAgent | None:
        """获取 Agent"""
        return self._agents.get(agent_id)

    def register_workflow(self, definition: WorkflowDefinition) -> None:
        """
        注册工作流定义

        Args:
            definition: 工作流定义
        """
        self._definitions[definition.workflow_id] = definition
        self.logger.info(
            "工作流已注册",
            workflow_id=definition.workflow_id,
            name=definition.name,
            steps=len(definition.steps),
        )

    def unregister_workflow(self, workflow_id: str) -> bool:
        """
        注销工作流定义

        Args:
            workflow_id: 工作流 ID

        Returns:
            是否成功注销
        """
        if workflow_id in self._definitions:
            del self._definitions[workflow_id]
            return True
        return False

    def get_workflow(self, workflow_id: str) -> WorkflowDefinition | None:
        """获取工作流定义"""
        return self._definitions.get(workflow_id)

    def create_workflow(
        self,
        name: str,
        description: str = "",
        steps: list[WorkflowStep] | None = None,
        variables: dict[str, Any] | None = None,
        timeout_seconds: float | None = None,
    ) -> WorkflowDefinition:
        """
        创建工作流定义

        Args:
            name: 工作流名称
            description: 描述
            steps: 步骤列表
            variables: 变量
            timeout_seconds: 超时时间

        Returns:
            工作流定义
        """
        definition = WorkflowDefinition(
            workflow_id=str(uuid.uuid4()),
            name=name,
            description=description,
            steps=steps or [],
            variables=variables or {},
            timeout_seconds=timeout_seconds or self.default_timeout_seconds,
        )

        self.register_workflow(definition)
        return definition

    async def execute(
        self,
        workflow_id: str,
        variables: dict[str, Any] | None = None,
        execution_id: str | None = None,
    ) -> WorkflowExecution:
        """
        执行工作流

        Args:
            workflow_id: 工作流 ID
            variables: 执行变量
            execution_id: 执行 ID

        Returns:
            执行记录
        """
        definition = self._definitions.get(workflow_id)
        if not definition:
            raise WorkflowError(f"工作流不存在: {workflow_id}")

        # 检查并发限制
        if len(self._running_executions) >= self.max_concurrent_workflows:
            raise WorkflowError("已达到最大并发工作流数")

        # 创建执行记录
        execution = WorkflowExecution(
            execution_id=execution_id or str(uuid.uuid4()),
            workflow_id=workflow_id,
            variables={**definition.variables, **(variables or {})},
        )

        self._executions[execution.execution_id] = execution
        self._running_executions.add(execution.execution_id)

        # 初始化暂停信号
        self._pause_signals[execution.execution_id] = asyncio.Event()
        self._pause_signals[execution.execution_id].set()  # 初始为运行状态
        self._cancel_signals[execution.execution_id] = False

        try:
            await self._emit_event(
                WorkflowEvent.STARTED,
                {
                    "execution_id": execution.execution_id,
                    "workflow_id": workflow_id,
                },
            )

            result = await self._execute_workflow(definition, execution)
            return result

        finally:
            self._running_executions.discard(execution.execution_id)
            self._pause_signals.pop(execution.execution_id, None)
            self._cancel_signals.pop(execution.execution_id, None)

    async def _execute_workflow(
        self,
        definition: WorkflowDefinition,
        execution: WorkflowExecution,
    ) -> WorkflowExecution:
        """
        执行工作流内部实现

        Args:
            definition: 工作流定义
            execution: 执行记录

        Returns:
            执行记录
        """
        execution.status = WorkflowStatus.RUNNING
        execution.started_at = datetime.now()

        self.logger.info(
            "工作流开始执行",
            execution_id=execution.execution_id,
            workflow_id=definition.workflow_id,
            steps=len(definition.steps),
        )

        try:
            # 使用超时控制
            await asyncio.wait_for(
                self._execute_steps(definition.steps, execution),
                timeout=definition.timeout_seconds,
            )

            execution.status = WorkflowStatus.COMPLETED
            execution.completed_at = datetime.now()

            await self._emit_event(
                WorkflowEvent.COMPLETED,
                {
                    "execution_id": execution.execution_id,
                    "workflow_id": definition.workflow_id,
                },
            )

            self.logger.info(
                "工作流执行完成",
                execution_id=execution.execution_id,
                duration_ms=execution.duration_ms,
            )

        except asyncio.TimeoutError:
            execution.status = WorkflowStatus.FAILED
            execution.error = f"工作流超时 ({definition.timeout_seconds}秒)"
            execution.completed_at = datetime.now()

            await self._emit_event(
                WorkflowEvent.FAILED,
                {
                    "execution_id": execution.execution_id,
                    "error": execution.error,
                },
            )

        except WorkflowCancelledError:
            execution.status = WorkflowStatus.CANCELLED
            execution.completed_at = datetime.now()

            await self._emit_event(
                WorkflowEvent.CANCELLED,
                {
                    "execution_id": execution.execution_id,
                },
            )

        except Exception as e:
            execution.status = WorkflowStatus.FAILED
            execution.error = str(e)
            execution.completed_at = datetime.now()

            await self._emit_event(
                WorkflowEvent.FAILED,
                {
                    "execution_id": execution.execution_id,
                    "error": str(e),
                },
            )

            self.logger.error(
                "工作流执行失败",
                execution_id=execution.execution_id,
                error=str(e),
            )

        return execution

    async def _execute_steps(
        self,
        steps: list[WorkflowStep],
        execution: WorkflowExecution,
    ) -> None:
        """
        执行步骤列表

        Args:
            steps: 步骤列表
            execution: 执行记录
        """
        completed_steps: set[str] = set()
        failed_steps: set[str] = set()

        while len(completed_steps) + len(failed_steps) < len(steps):
            # 检查取消信号
            if self._cancel_signals.get(execution.execution_id, False):
                raise WorkflowCancelledError()

            # 检查暂停信号
            pause_event = self._pause_signals.get(execution.execution_id)
            if pause_event:
                await pause_event.wait()

            # 找出就绪的步骤
            ready_steps = [s for s in steps if s.is_ready(completed_steps) and s.step_id not in failed_steps]

            if not ready_steps:
                # 没有就绪的步骤，检查是否有死锁
                pending_steps = [s for s in steps if s.status == StepStatus.PENDING and s.step_id not in failed_steps]

                if pending_steps:
                    # 检查依赖是否失败
                    for step in pending_steps:
                        if any(dep_id in failed_steps for dep_id in step.depends_on):
                            step.status = StepStatus.SKIPPED
                            completed_steps.add(step.step_id)

                    if not any(s.is_ready(completed_steps) for s in steps):
                        raise WorkflowError("工作流死锁：无法继续执行")
                break

            # 并行执行就绪的步骤
            batch = ready_steps[: self.max_concurrent_steps]

            tasks = [self._execute_step(step, execution) for step in batch]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for step, result in zip(batch, results):
                if isinstance(result, Exception):
                    step.status = StepStatus.FAILED
                    step.error = str(result)
                    execution.step_errors[step.step_id] = str(result)
                    failed_steps.add(step.step_id)
                else:
                    completed_steps.add(step.step_id)

    async def _execute_step(
        self,
        step: WorkflowStep,
        execution: WorkflowExecution,
    ) -> None:
        """
        执行单个步骤

        Args:
            step: 步骤
            execution: 执行记录
        """
        step.status = StepStatus.RUNNING
        step.started_at = datetime.now()
        execution.current_step_id = step.step_id

        await self._emit_event(
            WorkflowEvent.STEP_STARTED,
            {
                "execution_id": execution.execution_id,
                "step_id": step.step_id,
                "step_name": step.name,
            },
        )

        self.logger.debug(
            "步骤开始执行",
            execution_id=execution.execution_id,
            step_id=step.step_id,
            step_name=step.name,
        )

        try:
            # 根据步骤类型执行
            if step.step_type == StepType.TASK:
                await self._execute_task_step(step, execution)
            elif step.step_type == StepType.PARALLEL:
                await self._execute_parallel_step(step, execution)
            elif step.step_type == StepType.SEQUENTIAL:
                await self._execute_sequential_step(step, execution)
            elif step.step_type == StepType.CONDITION:
                await self._execute_condition_step(step, execution)
            elif step.step_type == StepType.LOOP:
                await self._execute_loop_step(step, execution)
            elif step.step_type == StepType.WAIT:
                await self._execute_wait_step(step, execution)
            elif step.step_type == StepType.CHECKPOINT:
                await self._execute_checkpoint_step(step, execution)
            else:
                raise WorkflowError(f"未知步骤类型: {step.step_type}")

            step.status = StepStatus.COMPLETED
            step.completed_at = datetime.now()

            await self._emit_event(
                WorkflowEvent.STEP_COMPLETED,
                {
                    "execution_id": execution.execution_id,
                    "step_id": step.step_id,
                },
            )

        except Exception as e:
            step.retry_count += 1

            if step.retry_count <= step.max_retries:
                self.logger.warning(
                    "步骤执行失败，准备重试",
                    execution_id=execution.execution_id,
                    step_id=step.step_id,
                    retry_count=step.retry_count,
                    error=str(e),
                )

                step.status = StepStatus.PENDING
                await self._execute_step(step, execution)
            else:
                step.status = StepStatus.FAILED
                step.error = str(e)
                step.completed_at = datetime.now()

                await self._emit_event(
                    WorkflowEvent.STEP_FAILED,
                    {
                        "execution_id": execution.execution_id,
                        "step_id": step.step_id,
                        "error": str(e),
                    },
                )

                raise

    async def _execute_task_step(
        self,
        step: WorkflowStep,
        execution: WorkflowExecution,
    ) -> None:
        """执行任务步骤"""
        agent = None

        # 查找 Agent
        if step.agent_id:
            agent = self._agents.get(step.agent_id)

        if not agent:
            # 尝试按角色查找
            for a in self._agents.values():
                # 简化：使用第一个可用的 Agent
                agent = a
                break

        if not agent:
            raise WorkflowError(f"找不到可用的 Agent 执行步骤: {step.name}")

        # 构建任务描述
        task_description = step.task_description or step.description or step.name

        # 替换变量
        for key, value in execution.variables.items():
            task_description = task_description.replace(f"${{{key}}}", str(value))

        # 执行任务
        response = await asyncio.wait_for(
            agent.run(query=task_description),
            timeout=step.timeout_seconds,
        )

        step.result = response
        execution.step_results[step.step_id] = response

        # 更新变量（如果结果包含变量更新）
        if response.content:
            # 简化：将结果存储为 last_result
            execution.variables["last_result"] = response.content

    async def _execute_parallel_step(
        self,
        step: WorkflowStep,
        execution: WorkflowExecution,
    ) -> None:
        """执行并行步骤"""
        if not step.sub_steps:
            return

        tasks = [self._execute_step(sub_step, execution) for sub_step in step.sub_steps]

        await asyncio.gather(*tasks, return_exceptions=True)

    async def _execute_sequential_step(
        self,
        step: WorkflowStep,
        execution: WorkflowExecution,
    ) -> None:
        """执行顺序步骤"""
        for sub_step in step.sub_steps:
            await self._execute_step(sub_step, execution)

    async def _execute_condition_step(
        self,
        step: WorkflowStep,
        execution: WorkflowExecution,
    ) -> None:
        """执行条件步骤"""
        # 简化实现：检查条件字符串
        condition = step.condition or "true"

        # 替换变量
        for key, value in execution.variables.items():
            condition = condition.replace(f"${{{key}}}", str(value))

        # 简化：检查是否为真值
        should_execute = condition.lower() in ("true", "1", "yes")

        if should_execute and step.sub_steps:
            for sub_step in step.sub_steps:
                await self._execute_step(sub_step, execution)

    async def _execute_loop_step(
        self,
        step: WorkflowStep,
        execution: WorkflowExecution,
    ) -> None:
        """执行循环步骤"""
        for i in range(step.loop_count):
            execution.variables["loop_index"] = i

            if step.sub_steps:
                for sub_step in step.sub_steps:
                    await self._execute_step(sub_step, execution)

    async def _execute_wait_step(
        self,
        step: WorkflowStep,
        execution: WorkflowExecution,
    ) -> None:
        """执行等待步骤"""
        if step.wait_seconds > 0:
            await asyncio.sleep(step.wait_seconds)

    async def _execute_checkpoint_step(
        self,
        step: WorkflowStep,
        execution: WorkflowExecution,
    ) -> None:
        """执行检查点步骤"""
        execution.checkpoint_data[step.step_id] = {
            "variables": execution.variables.copy(),
            "step_results": {k: v.content for k, v in execution.step_results.items()},
            "timestamp": datetime.now().isoformat(),
        }

        self.logger.debug(
            "检查点已保存",
            execution_id=execution.execution_id,
            step_id=step.step_id,
        )

    async def pause(self, execution_id: str) -> bool:
        """
        暂停工作流执行

        Args:
            execution_id: 执行 ID

        Returns:
            是否成功暂停
        """
        if execution_id not in self._running_executions:
            return False

        pause_event = self._pause_signals.get(execution_id)
        if pause_event:
            pause_event.clear()

            execution = self._executions.get(execution_id)
            if execution:
                execution.status = WorkflowStatus.PAUSED

            await self._emit_event(
                WorkflowEvent.PAUSED,
                {
                    "execution_id": execution_id,
                },
            )

            self.logger.info("工作流已暂停", execution_id=execution_id)

        return True

    async def resume(self, execution_id: str) -> bool:
        """
        恢复工作流执行

        Args:
            execution_id: 执行 ID

        Returns:
            是否成功恢复
        """
        execution = self._executions.get(execution_id)
        if not execution or execution.status != WorkflowStatus.PAUSED:
            return False

        pause_event = self._pause_signals.get(execution_id)
        if pause_event:
            pause_event.set()
            execution.status = WorkflowStatus.RUNNING

            await self._emit_event(
                WorkflowEvent.RESUMED,
                {
                    "execution_id": execution_id,
                },
            )

            self.logger.info("工作流已恢复", execution_id=execution_id)

        return True

    def cancel(self, execution_id: str) -> bool:
        """
        取消工作流执行

        Args:
            execution_id: 执行 ID

        Returns:
            是否成功取消
        """
        if execution_id not in self._running_executions:
            return False

        self._cancel_signals[execution_id] = True

        # 如果暂停中，先恢复以便能响应取消信号
        pause_event = self._pause_signals.get(execution_id)
        if pause_event:
            pause_event.set()

        self.logger.info("工作流取消请求已发送", execution_id=execution_id)

        return True

    def get_status(self, execution_id: str) -> dict[str, Any] | None:
        """
        获取工作流执行状态

        Args:
            execution_id: 执行 ID

        Returns:
            状态信息
        """
        execution = self._executions.get(execution_id)
        if not execution:
            return None

        definition = self._definitions.get(execution.workflow_id)

        return {
            "execution_id": execution.execution_id,
            "workflow_id": execution.workflow_id,
            "workflow_name": definition.name if definition else "Unknown",
            "status": execution.status.value,
            "started_at": execution.started_at.isoformat() if execution.started_at else None,
            "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
            "current_step_id": execution.current_step_id,
            "completed_steps": len(execution.step_results),
            "failed_steps": len(execution.step_errors),
            "total_steps": len(definition.steps) if definition else 0,
            "duration_ms": execution.duration_ms,
            "error": execution.error,
        }

    def get_execution(self, execution_id: str) -> WorkflowExecution | None:
        """获取执行记录"""
        return self._executions.get(execution_id)

    def get_executions(self, workflow_id: str | None = None) -> list[WorkflowExecution]:
        """
        获取执行记录列表

        Args:
            workflow_id: 可选的工作流 ID 过滤

        Returns:
            执行记录列表
        """
        executions = list(self._executions.values())

        if workflow_id:
            executions = [e for e in executions if e.workflow_id == workflow_id]

        return executions

    async def _emit_event(
        self,
        event: WorkflowEvent,
        data: dict[str, Any],
    ) -> None:
        """
        发送事件

        Args:
            event: 事件类型
            data: 事件数据
        """
        if self.event_callback:
            try:
                await self.event_callback(event, data)
            except Exception as e:
                self.logger.error(f"事件回调失败: {e}")

    def get_statistics(self) -> dict[str, Any]:
        """获取统计信息"""
        total_executions = len(self._executions)

        by_status = defaultdict(int)
        for execution in self._executions.values():
            by_status[execution.status.value] += 1

        return {
            "total_workflows": len(self._definitions),
            "total_executions": total_executions,
            "running_executions": len(self._running_executions),
            "registered_agents": len(self._agents),
            "by_status": dict(by_status),
        }

    def clear(self) -> None:
        """清空所有数据"""
        self._definitions.clear()
        self._executions.clear()
        self._running_executions.clear()
        self._pause_signals.clear()
        self._cancel_signals.clear()


class WorkflowError(AgentException):
    """工作流错误"""

    def __init__(
        self,
        message: str,
        workflow_id: str | None = None,
        execution_id: str | None = None,
        step_id: str | None = None,
        cause: Exception | None = None,
    ):
        super().__init__(message, cause=cause)
        self.workflow_id = workflow_id
        self.execution_id = execution_id
        self.step_id = step_id


class WorkflowCancelledError(WorkflowError):
    """工作流取消错误"""

    def __init__(self, message: str = "工作流已取消"):
        super().__init__(message)
