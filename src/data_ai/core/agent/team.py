"""
DATA-AI 多 Agent 协作系统

提供多 Agent 团队协作能力，支持任务分解、角色分配、结果汇总。
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from data_ai.core.llm.manager import ChatResponse

from ...utils.logging import get_logger
from .base import BaseAgent

logger = get_logger(__name__)


class TeamRole(Enum):
    """Agent 团队角色"""

    COORDINATOR = "coordinator"  # 协调者：分解任务、分配角色
    EXECUTOR = "executor"  # 执行者：执行具体任务
    REVIEWER = "reviewer"  # 评审者：审查执行结果
    TESTER = "tester"  # 测试者：编写和运行测试
    RESEARCHER = "researcher"  # 研究者：搜索和收集信息
    CODER = "coder"  # 编码者：编写代码
    ANALYST = "analyst"  # 分析者：数据分析


@dataclass
class TeamMember:
    """团队成员"""

    agent: BaseAgent
    role: TeamRole
    name: str
    description: str = ""
    max_retries: int = 2

    def __post_init__(self):
        if not self.description:
            self.description = f"{self.role.value} agent: {self.name}"


@dataclass
class TaskAssignment:
    """任务分配"""

    task_id: str
    description: str
    assigned_to: str  # member name
    role: TeamRole
    depends_on: list[str] = field(default_factory=list)  # 依赖的 task_id
    status: str = "pending"  # pending, running, completed, failed
    result: ChatResponse | None = None
    error: str | None = None
    retry_count: int = 0


@dataclass
class TeamResult:
    """团队执行结果"""

    success: bool
    final_answer: str
    task_results: dict[str, ChatResponse]  # task_id -> response
    total_steps: int
    total_time_ms: float
    member_results: dict[str, list[ChatResponse]] = field(default_factory=dict)  # member_name -> responses
    member_responses: dict[str, ChatResponse] = field(default_factory=dict)  # member_name -> 最终响应
    execution_mode: str = "hierarchical"
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentTeam:
    """
    多 Agent 协作团队

    支持多种协作模式：
    - sequential: 按顺序执行任务
    - parallel: 并行执行独立任务
    - hierarchical: 层级式（协调者分配任务）
    """

    def __init__(
        self,
        name: str = "team",
        mode: str = "hierarchical",
        max_parallel: int = 3,
    ):
        self.name = name
        self.mode = mode
        self.max_parallel = max_parallel
        self.members: dict[str, TeamMember] = {}
        self.tasks: dict[str, TaskAssignment] = {}
        self._task_counter = 0
        self.logger = get_logger(f"{__name__}.{name}")

    def add_member(self, agent: BaseAgent, role: TeamRole, name: str | None = None) -> None:
        """添加团队成员"""
        member_name = name or agent.name
        self.members[member_name] = TeamMember(
            agent=agent,
            role=role,
            name=member_name,
        )
        self.logger.info(f"团队成员已添加: {member_name} ({role.value})")

    def remove_member(self, name: str) -> None:
        """移除团队成员"""
        if name in self.members:
            del self.members[name]
            self.logger.info(f"团队成员已移除: {name}")

    def get_member(self, name: str) -> TeamMember | None:
        """获取团队成员"""
        return self.members.get(name)

    def get_member_by_role(self, role: TeamRole) -> list[TeamMember]:
        """按角色获取成员"""
        return [m for m in self.members.values() if m.role == role]

    def _generate_task_id(self) -> str:
        """生成任务 ID"""
        self._task_counter += 1
        return f"task_{self._task_counter}"

    async def _run_agent(self, agent: BaseAgent, user_input: str, **kwargs) -> ChatResponse:
        """
        包装 agent.run：兼容 user_input= 和 query= 两种调用风格，
        并把 Dict 返回归一为 ChatResponse。
        """
        try:
            coro = agent.run(user_input=user_input, **kwargs)
        except TypeError:
            # 自定义 Agent 可能用 query= 参数
            query = kwargs.pop("query", user_input)
            try:
                coro = agent.run(query=query, **kwargs)
            except TypeError:
                coro = agent.run(**kwargs)  # 最后兜底

        result = await coro
        return self._normalize_agent_response(result)

    @staticmethod
    def _normalize_agent_response(result: Any) -> ChatResponse:
        """把 Agent 的返回值统一归一为 ChatResponse"""
        if isinstance(result, ChatResponse):
            return result
        if isinstance(result, dict):
            content = (
                result.get("content") or result.get("output") or result.get("text") or result.get("response") or ""
            )
            if not content and result.get("messages"):
                for m in reversed(result.get("messages") or []):
                    if isinstance(m, dict) and m.get("role") == "assistant":
                        content = m.get("content", "")
                        break
            return ChatResponse(
                content=str(content or ""),
                model=result.get("model", "agent"),
                usage=result.get("usage", {}) or {},
                finish_reason=result.get("finish_reason", "stop"),
            )
        return ChatResponse(
            content=str(result) if result is not None else "",
            model="agent",
            finish_reason="stop",
        )

    def assign_task(
        self,
        description: str,
        assigned_to: str,
        role: TeamRole = TeamRole.EXECUTOR,
        depends_on: list[str] | None = None,
    ) -> str:
        """分配任务"""
        task_id = self._generate_task_id()
        self.tasks[task_id] = TaskAssignment(
            task_id=task_id,
            description=description,
            assigned_to=assigned_to,
            role=role,
            depends_on=depends_on or [],
        )
        self.logger.info(f"任务已分配: {task_id} -> {assigned_to}: {description[:50]}...")
        return task_id

    async def _execute_task(self, task: TaskAssignment) -> None:
        """执行单个任务"""
        member = self.members.get(task.assigned_to)
        if not member:
            task.status = "failed"
            task.error = f"成员不存在: {task.assigned_to}"
            return

        # 检查依赖
        for dep_id in task.depends_on:
            dep = self.tasks.get(dep_id)
            if dep and dep.status != "completed":
                task.status = "failed"
                task.error = f"依赖任务未完成: {dep_id}"
                return

        task.status = "running"
        self.logger.info(f"开始执行任务: {task.task_id}")

        try:
            response = await self._run_agent(member.agent, task.description)
            task.result = response
            task.status = "completed"
            self.logger.info(f"任务完成: {task.task_id}")

        except Exception as e:
            task.retry_count += 1
            if task.retry_count <= member.max_retries:
                self.logger.warning(f"任务失败，重试 {task.retry_count}/{member.max_retries}: {task.task_id}")
                await self._execute_task(task)
            else:
                task.status = "failed"
                task.error = str(e)
                self.logger.error(f"任务最终失败: {task.task_id}: {e}")

    async def run_sequential(self, query: str) -> TeamResult:
        """顺序执行模式"""
        start_time = time.time()
        self.logger.info(f"[顺序模式] 开始执行: {query[:80]}...")

        # 先用协调者分解任务（如果有）
        coordinators = self.get_member_by_role(TeamRole.COORDINATOR)
        if coordinators:
            coord = coordinators[0]
            plan_response = await self._run_agent(
                coord.agent,
                f"请将以下任务分解为具体的子任务步骤，每步指派给合适的角色。任务：{query}\n\n"
                f"可用角色: {', '.join(m.role.value for m in self.members.values())}\n"
                f"可用成员: {', '.join(self.members.keys())}\n\n"
                f"请用 JSON 格式返回任务列表，每个任务包含: description, assigned_to, role",
                stream=False,
            )
            # 尝试解析协调者的输出为任务
            self._parse_coordinator_output(plan_response.content)

        # 如果没有任务，创建一个默认任务分配给第一个执行者
        if not self.tasks:
            executors = self.get_member_by_role(TeamRole.EXECUTOR)
            if executors:
                self.assign_task(query, executors[0].name, TeamRole.EXECUTOR)
            elif self.members:
                first_member = list(self.members.values())[0]
                self.assign_task(query, first_member.name, first_member.role)

        # 按顺序执行
        total_steps = 0
        task_results = {}
        member_results: dict[str, list[ChatResponse]] = {}

        for task in self.tasks.values():
            await self._execute_task(task)
            total_steps += 1

            if task.result:
                task_results[task.task_id] = task.result
                member_results.setdefault(task.assigned_to, []).append(task.result)

        # 汇总结果
        final_answer = self._summarize_results(task_results)
        elapsed = (time.time() - start_time) * 1000

        return TeamResult(
            success=all(t.status == "completed" for t in self.tasks.values()),
            final_answer=final_answer,
            task_results=task_results,
            total_steps=total_steps,
            total_time_ms=elapsed,
            member_results=member_results,
        )

    async def run_parallel(self, query: str) -> TeamResult:
        """并行执行模式"""
        start_time = time.time()
        self.logger.info(f"[并行模式] 开始执行: {query[:80]}...")

        # 先用协调者分解任务
        coordinators = self.get_member_by_role(TeamRole.COORDINATOR)
        if coordinators:
            coord = coordinators[0]
            plan_response = await self._run_agent(
                coord.agent,
                f"请将以下任务分解为可以并行执行的独立子任务。任务：{query}\n\n"
                f"可用角色: {', '.join(m.role.value for m in self.members.values())}\n"
                f"可用成员: {', '.join(self.members.keys())}",
                stream=False,
            )
            self._parse_coordinator_output(plan_response.content)

        if not self.tasks:
            executors = self.get_member_by_role(TeamRole.EXECUTOR)
            if executors:
                self.assign_task(query, executors[0].name, TeamRole.EXECUTOR)

        # 找出无依赖的任务并行执行
        total_steps = 0
        task_results = {}
        member_results: dict[str, list[ChatResponse]] = {}

        # 分批并行执行
        completed = set()
        while len(completed) < len(self.tasks):
            # 找出可执行的任务（依赖已完成）
            ready = [
                t
                for t in self.tasks.values()
                if t.task_id not in completed
                and t.status == "pending"
                and all(dep in completed for dep in t.depends_on)
            ]

            if not ready:
                break

            # 限制并发数
            batch = ready[: self.max_parallel]
            coroutines = [self._execute_task(t) for t in batch]
            await asyncio.gather(*coroutines)

            for t in batch:
                completed.add(t.task_id)
                total_steps += 1
                if t.result:
                    task_results[t.task_id] = t.result
                    member_results.setdefault(t.assigned_to, []).append(t.result)

        final_answer = self._summarize_results(task_results)
        elapsed = (time.time() - start_time) * 1000

        return TeamResult(
            success=all(t.status == "completed" for t in self.tasks.values()),
            final_answer=final_answer,
            task_results=task_results,
            total_steps=total_steps,
            total_time_ms=elapsed,
            member_results=member_results,
        )

    async def run_hierarchical(self, query: str) -> TeamResult:
        """层级执行模式（协调者分配 + 执行者执行 + 评审者审查）"""
        start_time = time.time()
        self.logger.info(f"[层级模式] 开始执行: {query[:80]}...")

        total_steps = 0
        task_results = {}
        member_results: dict[str, list[ChatResponse]] = {}

        # 阶段1: 协调者分解任务
        coordinators = self.get_member_by_role(TeamRole.COORDINATOR)
        if coordinators:
            coord = coordinators[0]
            plan_response = await self._run_agent(
                coord.agent,
                f"作为团队协调者，请分析以下任务并制定执行计划。\n\n"
                f"任务: {query}\n\n"
                f"团队成员:\n"
                + "\n".join(f"  - {m.name}: {m.role.value} - {m.description}" for m in self.members.values())
                + "\n\n"
                "请输出执行计划，包含具体的子任务和分配方案。",
                stream=False,
            )
            task_results["planning"] = plan_response
            member_results.setdefault(coord.name, []).append(plan_response)
            total_steps += 1

            self._parse_coordinator_output(plan_response.content)

        # 阶段2: 执行者执行任务
        if self.tasks:
            exec_tasks = [t for t in self.tasks.values() if t.status == "pending"]
            for task in exec_tasks[: self.max_parallel]:
                await self._execute_task(task)
                total_steps += 1
                if task.result:
                    task_results[task.task_id] = task.result
                    member_results.setdefault(task.assigned_to, []).append(task.result)
        else:
            # 没有分解出子任务，直接让执行者处理
            executors = self.get_member_by_role(TeamRole.EXECUTOR)
            coders = self.get_member_by_role(TeamRole.CODER)
            doers = executors or coders or list(self.members.values())

            for member in doers[:1]:  # 只让第一个执行
                response = await self._run_agent(member.agent, query)
                task_results["direct"] = response
                member_results.setdefault(member.name, []).append(response)
                total_steps += 1

        # 阶段3: 评审者审查结果
        reviewers = self.get_member_by_role(TeamRole.REVIEWER)
        if reviewers and task_results:
            reviewer = reviewers[0]
            results_summary = "\n\n".join(
                f"任务 {tid}:\n{r.content[:500]}" for tid, r in task_results.items() if tid != "planning"
            )

            review_response = await self._run_agent(
                reviewer.agent,
                f"请审查以下执行结果，给出改进建议和最终总结。\n\n{results_summary}",
            )
            task_results["review"] = review_response
            member_results.setdefault(reviewer.name, []).append(review_response)
            total_steps += 1

        # 汇总
        final_answer = self._summarize_results(task_results)
        elapsed = (time.time() - start_time) * 1000

        return TeamResult(
            success=all(t.status == "completed" for t in self.tasks.values()) if self.tasks else bool(task_results),
            final_answer=final_answer,
            task_results=task_results,
            total_steps=total_steps,
            total_time_ms=elapsed,
            member_results=member_results,
        )

    async def run(self, query: str) -> TeamResult:
        """执行团队任务（根据模式自动选择）"""
        if self.mode == "sequential":
            return await self.run_sequential(query)
        elif self.mode == "parallel":
            return await self.run_parallel(query)
        elif self.mode == "hierarchical":
            return await self.run_hierarchical(query)
        else:
            raise ValueError(f"未知协作模式: {self.mode}")

    def _parse_coordinator_output(self, output: str) -> None:
        """解析协调者的输出为任务分配"""
        import json
        import re

        # 尝试从输出中提取 JSON 格式的任务列表
        try:
            # 查找 JSON 数组
            json_match = re.search(r"\[.*\]", output, re.DOTALL)
            if json_match:
                tasks = json.loads(json_match.group())
                for task in tasks:
                    if isinstance(task, dict):
                        desc = task.get("description", "")
                        assigned = task.get("assigned_to", "")
                        role_str = task.get("role", "executor")
                        try:
                            role = TeamRole(role_str)
                        except ValueError:
                            role = TeamRole.EXECUTOR

                        if desc and assigned:
                            self.assign_task(desc, assigned, role)
        except (json.JSONDecodeError, KeyError):
            self.logger.debug("协调者输出解析失败，使用默认任务分配")

    async def execute(self, query: str) -> TeamResult:
        """
        按当前 mode 执行查询（聚合所有成员的回答）

        Args:
            query: 用户查询

        Returns:
            TeamResult
        """
        if not query or not query.strip():
            return TeamResult(
                success=False,
                final_answer="",
                member_responses={},
                member_results={},
                task_results={},
                total_steps=0,
                execution_mode=self.mode,
                total_time_ms=0.0,
                metadata={"error": "empty_query"},
            )

        if not self.members:
            return TeamResult(
                success=False,
                final_answer="",
                member_responses={},
                member_results={},
                task_results={},
                total_steps=0,
                execution_mode=self.mode,
                total_time_ms=0.0,
                metadata={"error": "no_members"},
            )

        if self.mode == "sequential":
            return await self.run_sequential(query)
        if self.mode == "parallel":
            return await self.run_parallel(query)
        if self.mode == "hierarchical":
            return await self.run_hierarchical(query)
        # 默认：聚合所有成员的回答
        return await self._run_aggregated(query)

    async def _run_aggregated(self, query: str) -> TeamResult:
        """默认模式：让所有成员独立回答查询并合并"""
        start_time = time.time()
        member_responses: dict[str, ChatResponse] = {}
        member_results: dict[str, list[ChatResponse]] = {}
        total_steps = 0

        async def _ask(m: TeamMember) -> tuple:
            try:
                resp = await self._run_agent(m.agent, query)
                return (m.name, resp)
            except Exception as e:
                self.logger.warning(f"成员 {m.name} 回答失败: {e}")
                return (
                    m.name,
                    ChatResponse(
                        content=f"成员 {m.name} 回答失败: {e}",
                        model="error",
                        finish_reason="error",
                    ),
                )

        results = await asyncio.gather(*[_ask(m) for m in self.members.values()])
        for name, resp in results:
            member_responses[name] = resp
            member_results.setdefault(name, []).append(resp)
            total_steps += 1

        # 用 ConsensusBuilder 合成最终答案
        try:
            from .consensus import ConsensusBuilder

            builder = ConsensusBuilder(method="majority_vote")
            final = builder.build_consensus(
                list(member_responses.values()),
                original_query=query,
            )
            final_answer = final.content
        except Exception:
            final_answer = self._summarize_results({f"member_{name}": r for name, r in member_responses.items()})

        elapsed = (time.time() - start_time) * 1000
        return TeamResult(
            success=len(member_responses) > 0,
            final_answer=final_answer,
            member_responses=member_responses,
            member_results=member_results,
            task_results={f"member_{name}": r for name, r in member_responses.items()},
            total_steps=total_steps,
            execution_mode=self.mode,
            total_time_ms=elapsed,
        )

    def _summarize_results(self, task_results: dict[str, ChatResponse]) -> str:
        """汇总所有任务结果"""
        if not task_results:
            return "没有执行结果"

        parts = []
        for task_id, response in task_results.items():
            parts.append(f"[{task_id}]\n{response.content}")

        return "\n\n---\n\n".join(parts)

    def get_status(self) -> dict[str, Any]:
        """获取团队状态"""
        return {
            "name": self.name,
            "mode": self.mode,
            "members": {name: {"role": m.role.value, "description": m.description} for name, m in self.members.items()},
            "tasks": {tid: {"status": t.status, "assigned_to": t.assigned_to} for tid, t in self.tasks.items()},
            "total_tasks": len(self.tasks),
            "completed_tasks": sum(1 for t in self.tasks.values() if t.status == "completed"),
        }

    def clear_tasks(self) -> None:
        """清空所有任务"""
        self.tasks.clear()
        self._task_counter = 0

    def list_members(self) -> list[dict[str, str]]:
        """列出所有成员"""
        return [{"name": m.name, "role": m.role.value, "description": m.description} for m in self.members.values()]
