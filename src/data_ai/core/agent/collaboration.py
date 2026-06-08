"""
DATA-AI 多 Agent 协作框架

提供多 Agent 协作的核心抽象和数据结构，支持多种协作模式和角色分配。
参考 Hermes 和 Trae 的多 Agent 架构设计。
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from data_ai.core.llm.manager import ChatResponse

from ...utils.exceptions import AgentException
from ...utils.logging import get_logger
from .base import BaseAgent

logger = get_logger(__name__)


class AgentRole(Enum):
    """
    Agent 角色定义

    定义 Agent 在协作中的角色和职责
    """

    COORDINATOR = "coordinator"  # 协调者：负责任务分解、分配和协调
    WORKER = "worker"  # 工作者：执行具体任务
    REVIEWER = "reviewer"  # 审核者：审查和验证结果
    SPECIALIST = "specialist"  # 专家：提供专业领域知识

    @classmethod
    def get_description(cls, role: AgentRole) -> str:
        """获取角色描述"""
        descriptions = {
            cls.COORDINATOR: "负责协调团队工作，分解任务并分配给合适的成员",
            cls.WORKER: "执行分配的具体任务，产出工作成果",
            cls.REVIEWER: "审查工作成果，确保质量和一致性",
            cls.SPECIALIST: "提供专业领域的知识和建议",
        }
        return descriptions.get(role, "未知角色")


class CollaborationMode(Enum):
    """
    协作模式定义

    定义多个 Agent 之间的协作方式
    """

    SEQUENTIAL = "sequential"  # 顺序执行：任务按顺序依次执行
    PARALLEL = "parallel"  # 并行执行：独立任务同时执行
    HIERARCHICAL = "hierarchical"  # 层级执行：协调者分配，工作者执行
    CONSENSUS = "consensus"  # 共识执行：通过投票或协商达成共识

    @classmethod
    def get_description(cls, mode: CollaborationMode) -> str:
        """获取模式描述"""
        descriptions = {
            cls.SEQUENTIAL: "任务按顺序依次执行，前一个任务完成后才开始下一个",
            cls.PARALLEL: "独立任务同时执行，提高整体效率",
            cls.HIERARCHICAL: "协调者负责任务分解和分配，工作者执行具体任务",
            cls.CONSENSUS: "多个 Agent 通过投票或协商达成共识后执行",
        }
        return descriptions.get(mode, "未知模式")


class TaskStatus(Enum):
    """任务状态"""

    PENDING = "pending"  # 待执行
    ASSIGNED = "assigned"  # 已分配
    RUNNING = "running"  # 执行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败
    CANCELLED = "cancelled"  # 已取消
    BLOCKED = "blocked"  # 被阻塞（等待依赖）


class TaskPriority(Enum):
    """任务优先级"""

    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class AgentTask:
    """
    Agent 任务定义

    表示一个需要由 Agent 执行的任务单元
    """

    task_id: str
    description: str
    assigned_agent: str | None = None
    role: AgentRole | None = None
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.NORMAL
    depends_on: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    result: ChatResponse | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    retry_count: int = 0
    max_retries: int = 3

    def __post_init__(self):
        """初始化后处理"""
        if not self.task_id:
            self.task_id = str(uuid.uuid4())

    def mark_started(self) -> None:
        """标记任务开始"""
        self.status = TaskStatus.RUNNING
        self.started_at = datetime.now()

    def mark_completed(self, result: ChatResponse) -> None:
        """标记任务完成"""
        self.status = TaskStatus.COMPLETED
        self.result = result
        self.completed_at = datetime.now()

    def mark_failed(self, error: str) -> None:
        """标记任务失败"""
        self.status = TaskStatus.FAILED
        self.error = error
        self.completed_at = datetime.now()

    def can_retry(self) -> bool:
        """检查是否可以重试"""
        return self.retry_count < self.max_retries

    def increment_retry(self) -> None:
        """增加重试计数"""
        self.retry_count += 1
        self.status = TaskStatus.PENDING

    @property
    def duration_ms(self) -> float | None:
        """计算任务执行时长（毫秒）"""
        if self.started_at and self.completed_at:
            delta = self.completed_at - self.started_at
            return delta.total_seconds() * 1000
        return None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "description": self.description,
            "assigned_agent": self.assigned_agent,
            "role": self.role.value if self.role else None,
            "status": self.status.value,
            "priority": self.priority.value,
            "depends_on": self.depends_on,
            "metadata": self.metadata,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "retry_count": self.retry_count,
            "duration_ms": self.duration_ms,
        }


@dataclass
class AgentInfo:
    """
    Agent 信息

    存储参与协作的 Agent 的基本信息和能力
    """

    agent_id: str
    name: str
    role: AgentRole
    agent: BaseAgent
    capabilities: list[str] = field(default_factory=list)
    max_concurrent_tasks: int = 1
    current_tasks: int = 0
    total_completed: int = 0
    total_failed: int = 0

    @property
    def is_available(self) -> bool:
        """检查 Agent 是否可用"""
        return self.current_tasks < self.max_concurrent_tasks

    @property
    def success_rate(self) -> float:
        """计算成功率"""
        total = self.total_completed + self.total_failed
        if total == 0:
            return 1.0
        return self.total_completed / total

    def assign_task(self) -> None:
        """分配任务"""
        self.current_tasks += 1

    def complete_task(self, success: bool = True) -> None:
        """完成任务"""
        self.current_tasks = max(0, self.current_tasks - 1)
        if success:
            self.total_completed += 1
        else:
            self.total_failed += 1

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "role": self.role.value,
            "capabilities": self.capabilities,
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "current_tasks": self.current_tasks,
            "total_completed": self.total_completed,
            "total_failed": self.total_failed,
            "is_available": self.is_available,
            "success_rate": self.success_rate,
        }


@dataclass
class CollaborationResult:
    """
    协作结果

    表示一次协作会话的最终结果
    """

    session_id: str
    success: bool
    final_output: str
    task_results: dict[str, ChatResponse] = field(default_factory=dict)
    agent_contributions: dict[str, list[str]] = field(default_factory=dict)
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    total_time_ms: float = 0.0
    collaboration_mode: CollaborationMode | None = None
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        """计算任务成功率"""
        if self.total_tasks == 0:
            return 1.0 if self.success else 0.0
        return self.completed_tasks / self.total_tasks

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "session_id": self.session_id,
            "success": self.success,
            "final_output": self.final_output,
            "total_tasks": self.total_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "total_time_ms": self.total_time_ms,
            "success_rate": self.success_rate,
            "collaboration_mode": self.collaboration_mode.value if self.collaboration_mode else None,
            "errors": self.errors,
            "metadata": self.metadata,
        }


class CollaborationSession:
    """
    协作会话

    管理一次完整的多 Agent 协作过程，包括任务管理、
    Agent 注册、进度跟踪和结果汇总。
    """

    def __init__(
        self,
        session_id: str | None = None,
        mode: CollaborationMode = CollaborationMode.HIERARCHICAL,
        max_parallel_tasks: int = 5,
        task_timeout_seconds: float = 300.0,
    ):
        """
        初始化协作会话

        Args:
            session_id: 会话ID，不提供则自动生成
            mode: 协作模式
            max_parallel_tasks: 最大并行任务数
            task_timeout_seconds: 单个任务超时时间（秒）
        """
        self.session_id = session_id or str(uuid.uuid4())
        self.mode = mode
        self.max_parallel_tasks = max_parallel_tasks
        self.task_timeout_seconds = task_timeout_seconds

        self.agents: dict[str, AgentInfo] = {}
        self.tasks: dict[str, AgentTask] = {}
        self.results: dict[str, ChatResponse] = {}

        self._task_counter = 0
        self._start_time: float | None = None
        self._end_time: float | None = None
        self._status = "initialized"

        self.logger = get_logger(f"{__name__}.session.{self.session_id[:8]}")

    def register_agent(
        self,
        agent: BaseAgent,
        role: AgentRole,
        capabilities: list[str] | None = None,
        max_concurrent_tasks: int = 1,
    ) -> str:
        """
        注册 Agent 到协作会话

        Args:
            agent: Agent 实例
            role: Agent 角色
            capabilities: Agent 能力列表
            max_concurrent_tasks: 最大并发任务数

        Returns:
            Agent ID
        """
        agent_id = agent.name or str(uuid.uuid4())

        self.agents[agent_id] = AgentInfo(
            agent_id=agent_id,
            name=agent.name,
            role=role,
            agent=agent,
            capabilities=capabilities or [],
            max_concurrent_tasks=max_concurrent_tasks,
        )

        self.logger.info(
            "Agent 已注册",
            agent_id=agent_id,
            role=role.value,
            capabilities=capabilities,
        )

        return agent_id

    def unregister_agent(self, agent_id: str) -> bool:
        """
        注销 Agent

        Args:
            agent_id: Agent ID

        Returns:
            是否成功注销
        """
        if agent_id in self.agents:
            del self.agents[agent_id]
            self.logger.info("Agent 已注销", agent_id=agent_id)
            return True
        return False

    def get_agent(self, agent_id: str) -> AgentInfo | None:
        """获取 Agent 信息"""
        return self.agents.get(agent_id)

    def get_agents_by_role(self, role: AgentRole) -> list[AgentInfo]:
        """按角色获取 Agent 列表"""
        return [a for a in self.agents.values() if a.role == role]

    def get_available_agents(self, role: AgentRole | None = None) -> list[AgentInfo]:
        """
        获取可用的 Agent 列表

        Args:
            role: 可选的角色过滤

        Returns:
            可用的 Agent 列表
        """
        agents = [a for a in self.agents.values() if a.is_available]
        if role:
            agents = [a for a in agents if a.role == role]
        return agents

    def create_task(
        self,
        description: str,
        assigned_agent: str | None = None,
        role: AgentRole | None = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        depends_on: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentTask:
        """
        创建任务

        Args:
            description: 任务描述
            assigned_agent: 分配的 Agent ID
            role: 需要的角色
            priority: 任务优先级
            depends_on: 依赖的任务 ID 列表
            metadata: 任务元数据

        Returns:
            创建的任务对象
        """
        self._task_counter += 1
        task_id = f"task_{self._task_counter}"

        task = AgentTask(
            task_id=task_id,
            description=description,
            assigned_agent=assigned_agent,
            role=role,
            priority=priority,
            depends_on=depends_on or [],
            metadata=metadata or {},
        )

        self.tasks[task_id] = task
        self.logger.debug("任务已创建", task_id=task_id, description=description[:50])

        return task

    def get_task(self, task_id: str) -> AgentTask | None:
        """获取任务"""
        return self.tasks.get(task_id)

    def get_pending_tasks(self) -> list[AgentTask]:
        """获取待执行的任务"""
        return [t for t in self.tasks.values() if t.status == TaskStatus.PENDING]

    def get_ready_tasks(self) -> list[AgentTask]:
        """
        获取就绪的任务（依赖已满足）

        Returns:
            就绪的任务列表，按优先级排序
        """
        ready = []
        for task in self.tasks.values():
            if task.status != TaskStatus.PENDING:
                continue

            # 检查依赖是否完成
            deps_satisfied = all(
                self.tasks.get(dep_id, AgentTask(task_id="", description="")).status == TaskStatus.COMPLETED
                for dep_id in task.depends_on
            )

            if deps_satisfied:
                ready.append(task)

        # 按优先级排序
        ready.sort(key=lambda t: t.priority.value, reverse=True)
        return ready

    def assign_task(self, task_id: str, agent_id: str) -> bool:
        """
        分配任务给 Agent

        Args:
            task_id: 任务 ID
            agent_id: Agent ID

        Returns:
            是否成功分配
        """
        task = self.tasks.get(task_id)
        agent = self.agents.get(agent_id)

        if not task or not agent:
            return False

        if not agent.is_available:
            return False

        task.assigned_agent = agent_id
        task.status = TaskStatus.ASSIGNED
        agent.assign_task()

        self.logger.info("任务已分配", task_id=task_id, agent_id=agent_id)
        return True

    async def execute_task(self, task: AgentTask) -> ChatResponse:
        """
        执行单个任务

        Args:
            task: 要执行的任务

        Returns:
            Agent 响应
        """
        agent_info = self.agents.get(task.assigned_agent)
        if not agent_info:
            raise CollaborationError(f"Agent 不存在: {task.assigned_agent}")

        task.mark_started()
        self.logger.info("开始执行任务", task_id=task.task_id, agent=task.assigned_agent)

        try:
            # 使用超时控制；优先使用 user_input= 关键字（与 BaseAgent.run 签名一致），
            # 回退到 query= 关键字（兼容自定义 Agent）
            try:
                coro = agent_info.agent.run(user_input=task.description)
            except TypeError:
                coro = agent_info.agent.run(query=task.description)

            response = await asyncio.wait_for(
                coro,
                timeout=self.task_timeout_seconds,
            )

            # 标准化响应为 ChatResponse（BaseAgent.run 返回 Dict[str, Any]）
            response = self._normalize_response(response, task)

            task.mark_completed(response)
            agent_info.complete_task(success=True)
            self.results[task.task_id] = response

            self.logger.info(
                "任务完成",
                task_id=task.task_id,
                duration_ms=task.duration_ms,
            )

            return response

        except asyncio.TimeoutError:
            error = f"任务超时 ({self.task_timeout_seconds}秒)"
            task.mark_failed(error)
            agent_info.complete_task(success=False)
            raise CollaborationError(error, task_id=task.task_id)

        except Exception as e:
            task.mark_failed(str(e))
            agent_info.complete_task(success=False)
            raise CollaborationError(f"任务执行失败: {e}", task_id=task.task_id, cause=e)

    @staticmethod
    def _normalize_response(response: Any, task: AgentTask) -> ChatResponse:
        """把 Agent 的返回值统一归一为 ChatResponse"""
        if isinstance(response, ChatResponse):
            return response

        if isinstance(response, dict):
            content = (
                response.get("content")
                or response.get("output")
                or response.get("text")
                or response.get("response")
                or ""
            )
            if not content and response.get("messages"):
                # 从 messages 中取出最后一条 assistant
                msgs = response.get("messages") or []
                for m in reversed(msgs):
                    if isinstance(m, dict) and m.get("role") == "assistant":
                        content = m.get("content", "")
                        break
            return ChatResponse(
                content=str(content or ""),
                model=response.get("model", "agent"),
                usage=response.get("usage", {}) or {},
                finish_reason=response.get("finish_reason", "stop"),
                metadata={"task_id": task.task_id, "agent": task.assigned_agent},
            )

        # 其他类型（str / BaseModel / 自定义对象）都强转为字符串
        return ChatResponse(
            content=str(response) if response is not None else "",
            model="agent",
            finish_reason="stop",
            metadata={"task_id": task.task_id, "agent": task.assigned_agent},
        )

    async def run_all(
        self,
        tasks: list[AgentTask],
        mode: CollaborationMode | None = None,
    ) -> CollaborationResult:
        """
        运行一组任务，按指定协作模式执行。

        Args:
            tasks: 任务列表（如果任务尚未在 session 中注册，会先注册）
            mode: 协作模式；为 None 时使用 session 默认模式

        Returns:
            协作结果
        """
        # 注册/覆盖传入的任务（保持 task_id 唯一性）
        for task in tasks:
            if not task.assigned_agent:
                # 自动选择第一个可用 agent
                if self.agents:
                    task.assigned_agent = next(iter(self.agents))
                else:
                    raise CollaborationError("无可用 Agent 来执行任务")
            self.tasks[task.task_id] = task

        if mode is not None:
            self.mode = mode

        # 根据模式给出明确的行为
        if self.mode == CollaborationMode.SEQUENTIAL:
            return await self._run_sequential_mode()
        if self.mode == CollaborationMode.PARALLEL:
            return await self._run_parallel_mode()
        if self.mode == CollaborationMode.HIERARCHICAL:
            return await self._run_hierarchical_mode()
        if self.mode == CollaborationMode.CONSENSUS:
            return await self._run_consensus_mode()
        # 未知模式：走通用执行
        return await self.execute_all()

    async def _run_sequential_mode(self) -> CollaborationResult:
        """SEQUENTIAL 模式：按顺序逐个运行任务"""
        self._start_time = time.time()
        self._status = "running"
        errors: list[str] = []

        ordered = sorted(
            self.tasks.values(),
            key=lambda t: t.priority.value,
            reverse=True,
        )
        for task in ordered:
            try:
                self.results[task.task_id] = await self.execute_task(task)
            except CollaborationError as e:
                errors.append(str(e))
                self.logger.warning(f"任务 {task.task_id} 失败: {e}")

        self._end_time = time.time()
        self._status = "completed"
        return self._build_result(errors)

    async def _run_parallel_mode(self) -> CollaborationResult:
        """PARALLEL 模式：使用 asyncio.gather 并发执行"""
        self._start_time = time.time()
        self._status = "running"
        errors: list[str] = []

        tasks_to_run = [
            task for task in self.tasks.values() if task.status not in (TaskStatus.RUNNING, TaskStatus.COMPLETED)
        ]

        async def _safe_run(t: AgentTask) -> ChatResponse | None:
            try:
                return await self.execute_task(t)
            except CollaborationError as e:
                errors.append(str(e))
                self.logger.warning(f"并行任务 {t.task_id} 失败: {e}")
                return None

        results = await asyncio.gather(
            *[_safe_run(t) for t in tasks_to_run],
            return_exceptions=False,
        )
        for task, res in zip(tasks_to_run, results):
            if res is not None:
                self.results[task.task_id] = res

        self._end_time = time.time()
        self._status = "completed"
        return self._build_result(errors)

    async def _run_hierarchical_mode(self) -> CollaborationResult:
        """HIERARCHICAL 模式：先由协调者分派子任务，然后工作者执行"""
        self._start_time = time.time()
        self._status = "running"
        errors: list[str] = []

        # 找协调者
        coordinators = self.get_agents_by_role(AgentRole.COORDINATOR)
        if not coordinators:
            self.logger.warning("HIERARCHICAL 模式但没有协调者，降级为 SEQUENTIAL")
            return await self._run_sequential_mode()

        coordinator_agent = coordinators[0].agent
        # 让协调者分解任务
        decomposition_prompt = "请将以下任务分解为子任务列表:\n"
        for t in self.tasks.values():
            decomposition_prompt += f"- {t.task_id}: {t.description}\n"
        decomposition_prompt += "\n请用 JSON 数组返回 [{'task_id': ..., 'subtask': ...}, ...]"

        try:
            try:
                result = await coordinator_agent.run(user_input=decomposition_prompt)
            except TypeError:
                result = await coordinator_agent.run(query=decomposition_prompt)
            sub_assignments = self._parse_decomposition(result, list(self.tasks.values()))
        except Exception as e:
            self.logger.warning(f"协调者分解任务失败: {e}")
            sub_assignments = []

        # 把分解出的子任务按 worker 分配
        workers = self.get_agents_by_role(AgentRole.WORKER)
        if not workers:
            workers = list(self.agents.values())

        if sub_assignments:
            for sub in sub_assignments:
                sub_task = AgentTask(
                    task_id=f"{sub.get('parent_task_id', 'sub')}_{sub.get('id', 'x')}",
                    description=sub.get("subtask", sub.get("description", "")),
                    assigned_agent=workers[len(sub_assignments) % len(workers)].agent_id,
                    priority=TaskPriority.NORMAL,
                )
                self.tasks[sub_task.task_id] = sub_task

        # 执行所有任务（原始 + 子任务）
        for task in self.tasks.values():
            try:
                self.results[task.task_id] = await self.execute_task(task)
            except CollaborationError as e:
                errors.append(str(e))
                self.logger.warning(f"层级任务 {task.task_id} 失败: {e}")

        self._end_time = time.time()
        self._status = "completed"
        return self._build_result(errors)

    async def _run_consensus_mode(self) -> CollaborationResult:
        """CONSENSUS 模式：所有 agent 同时跑相同任务，然后选最佳"""
        self._start_time = time.time()
        self._status = "running"
        errors: list[str] = []

        # 找 worker
        workers = self.get_agents_by_role(AgentRole.WORKER)
        if not workers:
            workers = list(self.agents.values())
        if not workers:
            return self._build_result(["没有 worker 可用"])

        # 用第一个任务作为基础，复制到所有 worker
        base_task = next(iter(self.tasks.values()))
        consensus_tasks: list[AgentTask] = []
        for idx, w in enumerate(workers):
            ct = AgentTask(
                task_id=f"{base_task.task_id}_consensus_{idx}",
                description=base_task.description,
                assigned_agent=w.agent_id,
                priority=base_task.priority,
            )
            consensus_tasks.append(ct)
            self.tasks[ct.task_id] = ct

        responses: list[ChatResponse] = []

        async def _run_one(t: AgentTask) -> ChatResponse | None:
            try:
                return await self.execute_task(t)
            except CollaborationError as e:
                errors.append(str(e))
                return None

        gathered = await asyncio.gather(*[_run_one(t) for t in consensus_tasks])
        responses = [r for r in gathered if r is not None]

        # 用 ConsensusBuilder 投票
        from .consensus import ConsensusBuilder

        builder = ConsensusBuilder(method="majority_vote")
        final = builder.build_consensus(
            responses,
            original_query=base_task.description,
        )
        self.results["__consensus_final__"] = final

        self._end_time = time.time()
        self._status = "completed"
        return self._build_result(errors)

    @staticmethod
    def _parse_decomposition(result: Any, original_tasks: list[AgentTask]) -> list[dict[str, str]]:
        """解析协调者的分解结果"""
        text = ""
        if isinstance(result, dict):
            text = result.get("content") or result.get("output") or result.get("text") or ""
        else:
            text = str(result or "")

        import json
        import re

        m = re.search(r"\[[\s\S]*\]", text)
        if not m:
            return []
        try:
            data = json.loads(m.group())
        except json.JSONDecodeError:
            return []

        out: list[dict[str, str]] = []
        if not isinstance(data, list):
            return out
        for i, item in enumerate(data):
            if not isinstance(item, dict):
                continue
            parent = item.get("parent_task_id") or item.get("task_id")
            if parent not in {t.task_id for t in original_tasks}:
                parent = original_tasks[0].task_id if original_tasks else f"task_{i}"
            out.append(
                {
                    "parent_task_id": str(parent),
                    "id": str(item.get("id", f"sub_{i}")),
                    "subtask": str(item.get("subtask") or item.get("description") or ""),
                }
            )
        return out

    async def run(self) -> CollaborationResult:
        """运行所有任务（execute_all 的别名）"""
        return await self.execute_all()

    async def execute_all(self) -> CollaborationResult:
        """
        执行所有任务

        根据协作模式执行所有任务

        Returns:
            协作结果
        """
        self._start_time = time.time()
        self._status = "running"

        self.logger.info(
            "开始协作执行",
            mode=self.mode.value,
            total_tasks=len(self.tasks),
        )

        errors: list[str] = []

        try:
            if self.mode == CollaborationMode.SEQUENTIAL:
                await self._execute_sequential(errors)
            elif self.mode == CollaborationMode.PARALLEL:
                await self._execute_parallel(errors)
            elif self.mode == CollaborationMode.HIERARCHICAL:
                await self._execute_hierarchical(errors)
            elif self.mode == CollaborationMode.CONSENSUS:
                await self._execute_consensus(errors)
            else:
                raise CollaborationError(f"未知的协作模式: {self.mode}")

        except Exception as e:
            errors.append(str(e))
            self.logger.error("协作执行失败", error=str(e))

        self._end_time = time.time()
        self._status = "completed"

        # 构建结果
        return self._build_result(errors)

    async def _execute_sequential(self, errors: list[str]) -> None:
        """顺序执行所有任务"""
        tasks = list(self.tasks.values())
        tasks.sort(key=lambda t: t.priority.value, reverse=True)

        for task in tasks:
            if task.status == TaskStatus.COMPLETED:
                continue

            try:
                await self._prepare_and_execute_task(task)
            except Exception as e:
                errors.append(f"任务 {task.task_id} 失败: {e}")

    async def _execute_parallel(self, errors: list[str]) -> None:
        """并行执行所有任务"""
        while True:
            ready_tasks = self.get_ready_tasks()
            if not ready_tasks:
                break

            # 限制并发数
            batch = ready_tasks[: self.max_parallel_tasks]

            # 并行执行
            coroutines = []
            for task in batch:
                coroutines.append(self._safe_execute_task(task, errors))

            await asyncio.gather(*coroutines)

    async def _execute_hierarchical(self, errors: list[str]) -> None:
        """层级执行（协调者分配任务）"""
        # 协调者先分解任务
        coordinators = self.get_agents_by_role(AgentRole.COORDINATOR)
        if coordinators:
            coord = coordinators[0]
            plan_response = await coord.agent.run(
                query="请分析以下任务并制定执行计划，分配给合适的团队成员。\n\n"
                "任务列表:\n" + "\n".join(f"- {t.task_id}: {t.description}" for t in self.tasks.values()) + "\n\n"
                "团队成员:\n"
                + "\n".join(
                    f"- {a.name}: {a.role.value} ({', '.join(a.capabilities) if a.capabilities else '无特殊能力'})"
                    for a in self.agents.values()
                ),
            )
            self.results["planning"] = plan_response

        # 执行任务
        await self._execute_parallel(errors)

        # 审核者审查结果
        reviewers = self.get_agents_by_role(AgentRole.REVIEWER)
        if reviewers and self.results:
            reviewer = reviewers[0]
            results_summary = "\n\n".join(
                f"[{tid}]\n{r.content[:500]}" for tid, r in self.results.items() if tid != "planning"
            )

            review_response = await reviewer.agent.run(
                query=f"请审查以下执行结果并给出最终总结:\n\n{results_summary}",
            )
            self.results["review"] = review_response

    async def _execute_consensus(self, errors: list[str]) -> None:
        """共识执行（需要达成共识）"""
        # 简化实现：让所有工作者执行相同任务，然后选择最佳结果
        workers = self.get_agents_by_role(AgentRole.WORKER)

        for task in self.tasks.values():
            if task.status == TaskStatus.COMPLETED:
                continue

            if not workers:
                # 没有工作者，使用其他可用 Agent
                workers = list(self.agents.values())

            # 让多个 Agent 执行同一任务
            responses: list[ChatResponse] = []
            for worker in workers[:3]:  # 最多 3 个
                try:
                    response = await worker.agent.run(query=task.description)
                    responses.append(response)
                except Exception as e:
                    errors.append(f"Agent {worker.name} 执行失败: {e}")

            if responses:
                # 选择最长的响应作为最佳结果（简单策略）
                best = max(responses, key=lambda r: len(r.content))
                task.mark_completed(best)
                self.results[task.task_id] = best

    async def _prepare_and_execute_task(self, task: AgentTask) -> ChatResponse:
        """准备并执行任务"""
        # 如果没有分配 Agent，自动选择
        if not task.assigned_agent:
            available = self.get_available_agents(task.role)
            if not available:
                available = self.get_available_agents()
            if not available:
                raise CollaborationError(f"没有可用的 Agent 执行任务: {task.task_id}")

            self.assign_task(task.task_id, available[0].agent_id)

        return await self.execute_task(task)

    async def _safe_execute_task(self, task: AgentTask, errors: list[str]) -> None:
        """安全执行任务（捕获异常）"""
        try:
            await self._prepare_and_execute_task(task)
        except Exception as e:
            errors.append(f"任务 {task.task_id} 失败: {e}")

    def _build_result(self, errors: list[str]) -> CollaborationResult:
        """构建协作结果"""
        completed = sum(1 for t in self.tasks.values() if t.status == TaskStatus.COMPLETED)
        failed = sum(1 for t in self.tasks.values() if t.status == TaskStatus.FAILED)

        # 构建最终输出
        final_parts = []
        for task_id, response in self.results.items():
            final_parts.append(f"[{task_id}]\n{response.content}")

        final_output = "\n\n---\n\n".join(final_parts) if final_parts else "无输出"

        # 构建 Agent 贡献记录
        agent_contributions: dict[str, list[str]] = {}
        for task in self.tasks.values():
            if task.assigned_agent and task.status == TaskStatus.COMPLETED:
                agent_contributions.setdefault(task.assigned_agent, []).append(task.task_id)

        total_time = (self._end_time - self._start_time) * 1000 if self._end_time and self._start_time else 0

        return CollaborationResult(
            session_id=self.session_id,
            success=failed == 0 and completed > 0,
            final_output=final_output,
            task_results=self.results.copy(),
            agent_contributions=agent_contributions,
            total_tasks=len(self.tasks),
            completed_tasks=completed,
            failed_tasks=failed,
            total_time_ms=total_time,
            collaboration_mode=self.mode,
            errors=errors,
        )

    def get_status(self) -> dict[str, Any]:
        """获取会话状态"""
        return {
            "session_id": self.session_id,
            "status": self._status,
            "mode": self.mode.value,
            "agents": {aid: a.to_dict() for aid, a in self.agents.items()},
            "tasks": {tid: t.to_dict() for tid, t in self.tasks.items()},
            "total_agents": len(self.agents),
            "total_tasks": len(self.tasks),
            "completed_tasks": sum(1 for t in self.tasks.values() if t.status == TaskStatus.COMPLETED),
            "failed_tasks": sum(1 for t in self.tasks.values() if t.status == TaskStatus.FAILED),
        }

    def clear(self) -> None:
        """清空会话"""
        self.tasks.clear()
        self.results.clear()
        self._task_counter = 0
        self._start_time = None
        self._end_time = None
        self._status = "initialized"


class CollaborationError(AgentException):
    """协作错误"""

    def __init__(
        self,
        message: str,
        task_id: str | None = None,
        agent_id: str | None = None,
        cause: Exception | None = None,
    ):
        super().__init__(message, cause=cause)
        self.task_id = task_id
        self.agent_id = agent_id
