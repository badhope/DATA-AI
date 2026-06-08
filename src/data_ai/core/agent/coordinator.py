"""
DATA-AI Agent 协调器

提供多 Agent 协作的协调功能，包括任务分配、进度监控、冲突解决和结果汇总。
参考 Hermes 和 Trae 的多 Agent 架构设计。
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from data_ai.core.llm.manager import ChatResponse

from ...utils.logging import get_logger
from .base import BaseAgent
from .collaboration import (
    AgentInfo,
    AgentRole,
    AgentTask,
    CollaborationError,
    CollaborationMode,
    CollaborationResult,
    CollaborationSession,
    TaskPriority,
    TaskStatus,
)

logger = get_logger(__name__)


class ConflictType(Enum):
    """冲突类型"""

    RESOURCE = "resource"  # 资源冲突：多个 Agent 竞争同一资源
    TASK = "task"  # 任务冲突：任务分配或执行冲突
    RESULT = "result"  # 结果冲突：不同 Agent 结果不一致
    PRIORITY = "priority"  # 优先级冲突：任务优先级冲突
    DEPENDENCY = "dependency"  # 依赖冲突：任务依赖关系冲突


class ConflictResolution(Enum):
    """冲突解决策略"""

    FIRST_WINS = "first_wins"  # 先到先得
    VOTE = "vote"  # 投票决定
    COORDINATOR_DECIDES = "coordinator_decides"  # 协调者决定
    ROLLBACK = "rollback"  # 回滚重试
    MERGE = "merge"  # 合并结果


@dataclass
class Conflict:
    """冲突记录"""

    conflict_id: str
    conflict_type: ConflictType
    description: str
    involved_agents: list[str]
    involved_tasks: list[str]
    created_at: datetime = field(default_factory=datetime.now)
    resolved: bool = False
    resolution: ConflictResolution | None = None
    resolution_detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "conflict_id": self.conflict_id,
            "conflict_type": self.conflict_type.value,
            "description": self.description,
            "involved_agents": self.involved_agents,
            "involved_tasks": self.involved_tasks,
            "created_at": self.created_at.isoformat(),
            "resolved": self.resolved,
            "resolution": self.resolution.value if self.resolution else None,
            "resolution_detail": self.resolution_detail,
        }


@dataclass
class FailureRecord:
    """失败记录"""

    record_id: str
    task_id: str
    agent_id: str
    error_message: str
    error_type: str
    timestamp: datetime = field(default_factory=datetime.now)
    retry_count: int = 0
    recovered: bool = False
    recovery_action: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "record_id": self.record_id,
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "error_message": self.error_message,
            "error_type": self.error_type,
            "timestamp": self.timestamp.isoformat(),
            "retry_count": self.retry_count,
            "recovered": self.recovered,
            "recovery_action": self.recovery_action,
        }


@dataclass
class CoordinationResult:
    """协调执行结果

    Attributes:
        result_id: 协调会话 ID
        success: 总体是否成功
        tasks: 关联的 AgentTask 列表
        task_results: task_id -> ChatResponse
        collaboration_result: 底层 CollaborationSession 的结果
        summary: 自动生成的自然语言摘要
        metadata: 附加元数据
    """

    result_id: str
    success: bool
    tasks: list[AgentTask] = field(default_factory=list)
    task_results: dict[str, ChatResponse] = field(default_factory=dict)
    collaboration_result: CollaborationResult | None = None
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "success": self.success,
            "tasks": [t.to_dict() if hasattr(t, "to_dict") else t.__dict__ for t in self.tasks],
            "task_results": {
                tid: (r.to_dict() if hasattr(r, "to_dict") else {"content": r.content, "model": r.model})
                for tid, r in self.task_results.items()
            },
            "summary": self.summary,
            "metadata": self.metadata,
        }


@dataclass
class ProgressReport:
    """进度报告"""

    total_tasks: int
    completed_tasks: int
    running_tasks: int
    pending_tasks: int
    failed_tasks: int
    progress_percent: float
    elapsed_time_ms: float
    estimated_remaining_ms: float | None = None
    agent_status: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "total_tasks": self.total_tasks,
            "completed_tasks": self.completed_tasks,
            "running_tasks": self.running_tasks,
            "pending_tasks": self.pending_tasks,
            "failed_tasks": self.failed_tasks,
            "progress_percent": self.progress_percent,
            "elapsed_time_ms": self.elapsed_time_ms,
            "estimated_remaining_ms": self.estimated_remaining_ms,
            "agent_status": self.agent_status,
        }


class AgentCoordinator:
    """
    Agent 协调器

    负责协调多个 Agent 的协作，包括：
    - 任务分配和调度
    - 进度监控和报告
    - 冲突检测和解决
    - 结果汇总和整合
    - 失败处理和恢复
    """

    def __init__(
        self,
        name: str = "coordinator",
        session: CollaborationSession | None = None,
        auto_assign: bool = True,
        max_retries: int = 3,
        conflict_resolution: ConflictResolution = ConflictResolution.COORDINATOR_DECIDES,
        progress_callback: Callable[[ProgressReport], None] | None = None,
    ):
        """
        初始化协调器

        Args:
            name: 协调器名称
            session: 协作会话，不提供则自动创建
            auto_assign: 是否自动分配任务
            max_retries: 最大重试次数
            conflict_resolution: 默认冲突解决策略
            progress_callback: 进度回调函数
        """
        self.name = name
        self.session = session or CollaborationSession()
        self.auto_assign = auto_assign
        self.max_retries = max_retries
        self.conflict_resolution = conflict_resolution
        self.progress_callback = progress_callback

        self._conflicts: dict[str, Conflict] = {}
        self._failures: dict[str, FailureRecord] = {}
        self._start_time: float | None = None
        self._running = False
        self._cancelled = False

        self.logger = get_logger(f"{__name__}.{name}")

    @property
    def agents(self) -> dict[str, AgentInfo]:
        """获取所有注册的 Agent"""
        return self.session.agents

    @property
    def tasks(self) -> dict[str, AgentTask]:
        """获取所有任务"""
        return self.session.tasks

    def register_agent(
        self,
        agent: BaseAgent,
        role: AgentRole,
        capabilities: list[str] | None = None,
        max_concurrent_tasks: int = 1,
    ) -> str:
        """
        注册 Agent

        Args:
            agent: Agent 实例
            role: Agent 角色
            capabilities: 能力列表
            max_concurrent_tasks: 最大并发任务数

        Returns:
            Agent ID
        """
        agent_id = self.session.register_agent(
            agent=agent,
            role=role,
            capabilities=capabilities,
            max_concurrent_tasks=max_concurrent_tasks,
        )

        self.logger.info(
            "Agent 已注册到协调器",
            agent_id=agent_id,
            role=role.value,
        )

        return agent_id

    def unregister_agent(self, agent_id: str) -> bool:
        """
        注销 Agent

        Args:
            agent_id: Agent ID

        Returns:
            是否成功
        """
        # 检查是否有正在执行的任务
        agent = self.session.get_agent(agent_id)
        if agent and agent.current_tasks > 0:
            self.logger.warning(
                "Agent 有正在执行的任务，无法注销",
                agent_id=agent_id,
                current_tasks=agent.current_tasks,
            )
            return False

        return self.session.unregister_agent(agent_id)

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
            创建的任务
        """
        task = self.session.create_task(
            description=description,
            assigned_agent=assigned_agent,
            role=role,
            priority=priority,
            depends_on=depends_on,
            metadata=metadata,
        )

        self.logger.debug("任务已创建", task_id=task.task_id)
        return task

    def assign_tasks(self) -> dict[str, str]:
        """
        分配任务给合适的 Agent

        根据任务需求和 Agent 能力自动分配任务

        Returns:
            任务分配映射 {task_id: agent_id}
        """
        assignments: dict[str, str] = {}

        # 获取待分配的任务
        pending_tasks = [t for t in self.tasks.values() if t.status == TaskStatus.PENDING and not t.assigned_agent]

        # 按优先级排序
        pending_tasks.sort(key=lambda t: t.priority.value, reverse=True)

        for task in pending_tasks:
            # 查找合适的 Agent
            agent = self._find_best_agent(task)

            if agent:
                if self.session.assign_task(task.task_id, agent.agent_id):
                    assignments[task.task_id] = agent.agent_id
                    self.logger.info(
                        "任务已分配",
                        task_id=task.task_id,
                        agent_id=agent.agent_id,
                    )
            else:
                self.logger.warning(
                    "未找到合适的 Agent",
                    task_id=task.task_id,
                    required_role=task.role.value if task.role else None,
                )

        return assignments

    def _find_best_agent(self, task: AgentTask) -> AgentInfo | None:
        """
        为任务找到最合适的 Agent

        Args:
            task: 任务

        Returns:
            最合适的 Agent，如果没有返回 None
        """
        candidates = self.session.get_available_agents(task.role)

        if not candidates:
            # 如果没有指定角色的可用 Agent，尝试所有可用的
            candidates = self.session.get_available_agents()

        if not candidates:
            return None

        # 计算每个候选 Agent 的得分
        scored_candidates: list[tuple] = []

        for agent in candidates:
            score = self._calculate_agent_score(agent, task)
            scored_candidates.append((score, agent))

        # 按得分排序，选择最高的
        scored_candidates.sort(key=lambda x: x[0], reverse=True)

        return scored_candidates[0][1] if scored_candidates else None

    def _calculate_agent_score(self, agent: AgentInfo, task: AgentTask) -> float:
        """
        计算 Agent 对任务的适合度得分

        Args:
            agent: Agent 信息
            task: 任务

        Returns:
            适合度得分 (0-100)
        """
        score = 50.0  # 基础分

        # 角色匹配加分
        if task.role and agent.role == task.role:
            score += 20

        # 能力匹配加分
        if task.metadata.get("required_capabilities"):
            required = set(task.metadata["required_capabilities"])
            available = set(agent.capabilities)
            if required & available:
                score += 15 * len(required & available) / len(required)

        # 成功率加分
        score += agent.success_rate * 10

        # 当前负载减分
        load_ratio = agent.current_tasks / max(agent.max_concurrent_tasks, 1)
        score -= load_ratio * 20

        return max(0, min(100, score))

    def monitor_progress(self) -> ProgressReport:
        """
        监控执行进度

        Returns:
            进度报告
        """
        total = len(self.tasks)
        completed = sum(1 for t in self.tasks.values() if t.status == TaskStatus.COMPLETED)
        running = sum(1 for t in self.tasks.values() if t.status == TaskStatus.RUNNING)
        pending = sum(1 for t in self.tasks.values() if t.status == TaskStatus.PENDING)
        failed = sum(1 for t in self.tasks.values() if t.status == TaskStatus.FAILED)

        progress_percent = (completed / total * 100) if total > 0 else 0

        elapsed_ms = 0
        estimated_remaining_ms = None

        if self._start_time:
            elapsed_ms = (time.time() - self._start_time) * 1000

            # 估算剩余时间
            if completed > 0 and running > 0:
                avg_time_per_task = elapsed_ms / completed
                remaining_tasks = pending + running
                estimated_remaining_ms = avg_time_per_task * remaining_tasks

        # Agent 状态
        agent_status = {
            aid: {
                "role": a.role.value,
                "current_tasks": a.current_tasks,
                "is_available": a.is_available,
                "success_rate": a.success_rate,
            }
            for aid, a in self.agents.items()
        }

        report = ProgressReport(
            total_tasks=total,
            completed_tasks=completed,
            running_tasks=running,
            pending_tasks=pending,
            failed_tasks=failed,
            progress_percent=progress_percent,
            elapsed_time_ms=elapsed_ms,
            estimated_remaining_ms=estimated_remaining_ms,
            agent_status=agent_status,
        )

        # 调用进度回调
        if self.progress_callback:
            try:
                self.progress_callback(report)
            except Exception as e:
                self.logger.error(f"进度回调失败: {e}")

        return report

    def detect_conflicts(self) -> list[Conflict]:
        """
        检测冲突

        Returns:
            检测到的冲突列表
        """
        conflicts: list[Conflict] = []

        # 检测任务依赖冲突
        conflicts.extend(self._detect_dependency_conflicts())

        # 检测资源冲突
        conflicts.extend(self._detect_resource_conflicts())

        # 检测结果冲突
        conflicts.extend(self._detect_result_conflicts())

        return conflicts

    def _detect_dependency_conflicts(self) -> list[Conflict]:
        """检测依赖冲突"""
        conflicts: list[Conflict] = []

        # 检查循环依赖
        visited: set[str] = set()
        rec_stack: set[str] = set()

        def has_cycle(task_id: str) -> bool:
            visited.add(task_id)
            rec_stack.add(task_id)

            task = self.tasks.get(task_id)
            if task:
                for dep_id in task.depends_on:
                    if dep_id not in visited:
                        if has_cycle(dep_id):
                            return True
                    elif dep_id in rec_stack:
                        return True

            rec_stack.remove(task_id)
            return False

        for task_id in self.tasks:
            if task_id not in visited:
                if has_cycle(task_id):
                    conflict = Conflict(
                        conflict_id=str(uuid.uuid4()),
                        conflict_type=ConflictType.DEPENDENCY,
                        description=f"检测到循环依赖，涉及任务: {task_id}",
                        involved_agents=[],
                        involved_tasks=[task_id],
                    )
                    conflicts.append(conflict)
                    self._conflicts[conflict.conflict_id] = conflict

        return conflicts

    def _detect_resource_conflicts(self) -> list[Conflict]:
        """检测资源冲突"""
        conflicts: list[Conflict] = []

        # 检查是否有多个任务竞争同一 Agent
        agent_tasks: dict[str, list[str]] = {}

        for task in self.tasks.values():
            if task.assigned_agent and task.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
                agent_tasks.setdefault(task.assigned_agent, []).append(task.task_id)

        for agent_id, task_ids in agent_tasks.items():
            agent = self.agents.get(agent_id)
            if agent and len(task_ids) > agent.max_concurrent_tasks:
                conflict = Conflict(
                    conflict_id=str(uuid.uuid4()),
                    conflict_type=ConflictType.RESOURCE,
                    description=f"Agent {agent_id} 超过最大并发任务数",
                    involved_agents=[agent_id],
                    involved_tasks=task_ids,
                )
                conflicts.append(conflict)
                self._conflicts[conflict.conflict_id] = conflict

        return conflicts

    def _detect_result_conflicts(self) -> list[Conflict]:
        """检测结果冲突"""
        conflicts: list[Conflict] = []

        # 检查是否有相同任务产生不同结果
        # 这里简化处理，实际可能需要更复杂的逻辑

        return conflicts

    def resolve_conflicts(
        self,
        conflicts: list[Conflict] | None = None,
        strategy: ConflictResolution | None = None,
    ) -> list[Conflict]:
        """
        解决冲突

        Args:
            conflicts: 要解决的冲突列表，None 表示所有未解决的冲突
            strategy: 解决策略，None 使用默认策略

        Returns:
            已解决的冲突列表
        """
        if conflicts is None:
            conflicts = [c for c in self._conflicts.values() if not c.resolved]

        resolution_strategy = strategy or self.conflict_resolution
        resolved: list[Conflict] = []

        for conflict in conflicts:
            try:
                self._resolve_single_conflict(conflict, resolution_strategy)
                resolved.append(conflict)
            except Exception as e:
                self.logger.error(
                    "解决冲突失败",
                    conflict_id=conflict.conflict_id,
                    error=str(e),
                )

        return resolved

    def _resolve_single_conflict(
        self,
        conflict: Conflict,
        strategy: ConflictResolution,
    ) -> None:
        """
        解决单个冲突

        Args:
            conflict: 冲突
            strategy: 解决策略
        """
        self.logger.info(
            "解决冲突",
            conflict_id=conflict.conflict_id,
            type=conflict.conflict_type.value,
            strategy=strategy.value,
        )

        if conflict.conflict_type == ConflictType.DEPENDENCY:
            self._resolve_dependency_conflict(conflict, strategy)
        elif conflict.conflict_type == ConflictType.RESOURCE:
            self._resolve_resource_conflict(conflict, strategy)
        elif conflict.conflict_type == ConflictType.RESULT:
            self._resolve_result_conflict(conflict, strategy)
        else:
            conflict.resolved = True
            conflict.resolution = strategy
            conflict.resolution_detail = "使用默认策略解决"

    def _resolve_dependency_conflict(
        self,
        conflict: Conflict,
        strategy: ConflictResolution,
    ) -> None:
        """解决依赖冲突"""
        # 对于循环依赖，移除部分依赖关系
        for task_id in conflict.involved_tasks:
            task = self.tasks.get(task_id)
            if task and task.depends_on:
                # 移除最后一个依赖
                removed = task.depends_on.pop()
                self.logger.info(f"移除依赖: {task_id} -> {removed}")

        conflict.resolved = True
        conflict.resolution = strategy
        conflict.resolution_detail = "移除了循环依赖"

    def _resolve_resource_conflict(
        self,
        conflict: Conflict,
        strategy: ConflictResolution,
    ) -> None:
        """解决资源冲突"""
        if strategy == ConflictResolution.FIRST_WINS:
            # 保留第一个任务，其他任务重新分配
            conflict.involved_agents[0]
            task_ids = conflict.involved_tasks

            for i, task_id in enumerate(task_ids[1:], 1):
                task = self.tasks.get(task_id)
                if task:
                    task.assigned_agent = None
                    task.status = TaskStatus.PENDING
                    self.logger.info(f"重新分配任务: {task_id}")

            conflict.resolved = True
            conflict.resolution_detail = f"保留任务 {task_ids[0]}，其他任务重新分配"

        else:
            conflict.resolved = True
            conflict.resolution_detail = "使用默认策略"

    def _resolve_result_conflict(
        self,
        conflict: Conflict,
        strategy: ConflictResolution,
    ) -> None:
        """解决结果冲突"""
        conflict.resolved = True
        conflict.resolution_detail = "结果冲突已记录"

    def aggregate_results(self) -> dict[str, Any]:
        """
        汇总所有任务结果

        Returns:
            汇总的结果字典
        """
        results: dict[str, Any] = {
            "total_tasks": len(self.tasks),
            "completed_tasks": 0,
            "failed_tasks": 0,
            "task_results": {},
            "agent_contributions": {},
            "summary": "",
        }

        completed_responses: list[ChatResponse] = []

        for task_id, task in self.tasks.items():
            if task.status == TaskStatus.COMPLETED and task.result:
                results["completed_tasks"] += 1
                results["task_results"][task_id] = {
                    "content": task.result.content,
                    "usage": task.result.usage,
                }
                completed_responses.append(task.result)

                # 记录 Agent 贡献
                if task.assigned_agent:
                    results["agent_contributions"].setdefault(task.assigned_agent, []).append(task_id)

            elif task.status == TaskStatus.FAILED:
                results["failed_tasks"] += 1
                results["task_results"][task_id] = {
                    "error": task.error,
                }

        # 生成摘要
        if completed_responses:
            summary_parts = [r.content for r in completed_responses]
            results["summary"] = "\n\n---\n\n".join(summary_parts)

        return results

    def handle_failures(self) -> list[FailureRecord]:
        """
        处理失败的任务

        Returns:
            失败记录列表
        """
        failures: list[FailureRecord] = []

        for task in self.tasks.values():
            if task.status == TaskStatus.FAILED:
                record = self._create_failure_record(task)
                failures.append(record)
                self._failures[record.record_id] = record

                # 尝试恢复
                self._attempt_recovery(task, record)

        return failures

    def _create_failure_record(self, task: AgentTask) -> FailureRecord:
        """创建失败记录"""
        return FailureRecord(
            record_id=str(uuid.uuid4()),
            task_id=task.task_id,
            agent_id=task.assigned_agent or "unknown",
            error_message=task.error or "Unknown error",
            error_type="TaskExecutionError",
            retry_count=task.retry_count,
        )

    def _attempt_recovery(self, task: AgentTask, record: FailureRecord) -> None:
        """
        尝试恢复失败的任务

        Args:
            task: 失败的任务
            record: 失败记录
        """
        if not task.can_retry():
            self.logger.warning(
                "任务已达到最大重试次数",
                task_id=task.task_id,
                retry_count=task.retry_count,
            )
            return

        # 增加重试计数
        task.increment_retry()

        # 尝试重新分配给其他 Agent
        if task.assigned_agent:
            # 查找其他可用 Agent
            self.agents.get(task.assigned_agent)
            other_agents = [a for a in self.agents.values() if a.agent_id != task.assigned_agent and a.is_available]

            if other_agents:
                new_agent = other_agents[0]
                task.assigned_agent = new_agent.agent_id
                record.recovery_action = f"重新分配给 Agent: {new_agent.agent_id}"
            else:
                record.recovery_action = "等待 Agent 可用后重试"

        record.recovered = True
        self.logger.info(
            "任务恢复计划已制定",
            task_id=task.task_id,
            recovery_action=record.recovery_action,
        )

    async def run(
        self,
        query: str | None = None,
        tasks: list[AgentTask] | None = None,
    ) -> CollaborationResult:
        """
        运行协调器

        Args:
            query: 用户查询（用于创建初始任务）
            tasks: 预定义的任务列表

        Returns:
            协作结果
        """
        self._start_time = time.time()
        self._running = True
        self._cancelled = False

        self.logger.info("协调器开始运行", total_agents=len(self.agents))

        try:
            # 如果有查询，创建初始任务
            if query:
                self.create_task(description=query)

            # 添加预定义任务
            if tasks:
                for task in tasks:
                    self.tasks[task.task_id] = task

            # 自动分配任务
            if self.auto_assign:
                self.assign_tasks()

            # 检测并解决冲突
            conflicts = self.detect_conflicts()
            if conflicts:
                self.resolve_conflicts(conflicts)

            # 执行所有任务
            result = await self.session.execute_all()

            # 处理失败
            self.handle_failures()

            return result

        except Exception as e:
            self.logger.error("协调器运行失败", error=str(e))
            raise CollaborationError(f"协调器运行失败: {e}", cause=e)

        finally:
            self._running = False

    async def coordinate(
        self,
        tasks: list[AgentTask],
        auto_assign: bool | None = None,
        mode: CollaborationMode | None = None,
    ) -> CoordinationResult:
        """
        协调一组任务：
        1. 将任务添加到 session（自动分配 agent）
        2. 检测/解决冲突
        3. 使用底层 CollaborationSession 执行
        4. 收集结果并生成摘要

        Args:
            tasks: 要协调的 AgentTask 列表
            auto_assign: 是否启用自动分配；None 时使用 self.auto_assign
            mode: 协作模式；None 时使用 session.mode

        Returns:
            CoordinationResult
        """
        result_id = f"coord_{uuid.uuid4().hex[:12]}"
        if auto_assign is not None:
            self.auto_assign = auto_assign
        if mode is not None:
            self.session.mode = mode

        # 注册任务
        for task in tasks:
            if not task.assigned_agent:
                # 由 auto_assign 决定是否后续分配
                pass
            self.tasks[task.task_id] = task
            self.session.tasks[task.task_id] = task

        self._start_time = time.time()
        self._running = True
        self._cancelled = False

        task_results: dict[str, ChatResponse] = {}
        collab_result: CollaborationResult | None = None
        success = True

        try:
            # 自动分配
            if self.auto_assign:
                self.assign_tasks()
                # 把分配结果同步到 session
                for tid, task in self.tasks.items():
                    self.session.tasks[tid] = task

            # 冲突解决
            conflicts = self.detect_conflicts()
            if conflicts:
                self.resolve_conflicts(conflicts)

            # 执行
            collab_result = await self.session.execute_all()

            # 收集结果
            for tid, resp in (collab_result.task_results or {}).items():
                task_results[tid] = resp

            # 失败处理（重试等）
            self.handle_failures()
        except Exception as e:
            self.logger.error(f"协调执行失败: {e}")
            success = False
        finally:
            self._running = False

        # 生成自然语言摘要
        summary = self._summarize(tasks, task_results, collab_result)

        return CoordinationResult(
            result_id=result_id,
            success=success and len(task_results) > 0,
            tasks=list(self.tasks.values()),
            task_results=task_results,
            collaboration_result=collab_result,
            summary=summary,
            metadata={
                "total_tasks": len(tasks),
                "successful_tasks": len(task_results),
                "mode": (mode or self.session.mode).value,
                "elapsed_ms": (time.time() - self._start_time) * 1000,
            },
        )

    def _summarize(
        self,
        tasks: list[AgentTask],
        task_results: dict[str, ChatResponse],
        collab_result: CollaborationResult | None,
    ) -> str:
        """根据执行结果生成自然语言摘要"""
        if not tasks:
            return "没有任务需要协调。"

        total = len(tasks)
        completed = len(task_results)
        if completed == 0:
            return f"协调了 {total} 个任务，但全部失败。"

        if collab_result is not None and collab_result.failed_tasks:
            return f"在 {total} 个任务中成功完成 {completed} 个（{collab_result.failed_tasks} 个失败）。"

        return f"成功协调 {completed}/{total} 个任务。"

    async def run_with_monitoring(
        self,
        query: str | None = None,
        tasks: list[AgentTask] | None = None,
        monitor_interval_seconds: float = 1.0,
    ) -> CollaborationResult:
        """
        带监控的运行协调器

        Args:
            query: 用户查询
            tasks: 预定义任务列表
            monitor_interval_seconds: 监控间隔（秒）

        Returns:
            协作结果
        """
        # 启动监控任务
        monitor_task = asyncio.create_task(self._monitor_loop(monitor_interval_seconds))

        try:
            result = await self.run(query=query, tasks=tasks)
            return result
        finally:
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass

    async def _monitor_loop(self, interval: float) -> None:
        """监控循环"""
        while self._running and not self._cancelled:
            try:
                report = self.monitor_progress()
                self.logger.debug(
                    "进度更新",
                    progress=f"{report.progress_percent:.1f}%",
                    completed=report.completed_tasks,
                    total=report.total_tasks,
                )

                # 检测冲突
                conflicts = self.detect_conflicts()
                if conflicts:
                    self.resolve_conflicts(conflicts)

                await asyncio.sleep(interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"监控循环错误: {e}")
                await asyncio.sleep(interval)

    def cancel(self) -> None:
        """取消执行"""
        self._cancelled = True
        self.logger.info("协调器已取消")

    def get_status(self) -> dict[str, Any]:
        """获取协调器状态"""
        return {
            "name": self.name,
            "running": self._running,
            "cancelled": self._cancelled,
            "session": self.session.get_status(),
            "conflicts": {
                "total": len(self._conflicts),
                "resolved": sum(1 for c in self._conflicts.values() if c.resolved),
            },
            "failures": {
                "total": len(self._failures),
                "recovered": sum(1 for f in self._failures.values() if f.recovered),
            },
        }

    def get_conflicts(self) -> list[Conflict]:
        """获取所有冲突"""
        return list(self._conflicts.values())

    def get_failures(self) -> list[FailureRecord]:
        """获取所有失败记录"""
        return list(self._failures.values())

    def clear(self) -> None:
        """清空协调器状态"""
        self.session.clear()
        self._conflicts.clear()
        self._failures.clear()
        self._start_time = None
        self._running = False
        self._cancelled = False
