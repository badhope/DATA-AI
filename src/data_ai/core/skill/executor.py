"""
技能执行器

执行技能定义的任务步骤。
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ...utils.logging import get_logger
from .skill import Skill, SkillStep

logger = get_logger(__name__)


@dataclass
class ExecutionResult:
    """执行结果"""

    skill_id: str
    success: bool
    steps_completed: int
    steps_total: int
    outputs: list[dict[str, Any]]
    errors: list[str]
    execution_time_ms: float
    final_result: Any = None


class SkillExecutor:
    """
    技能执行器

    按步骤执行技能，支持：
    1. 步骤验证
    2. 错误处理
    3. 回滚机制
    4. 进度追踪
    """

    def __init__(self, tool_registry: Any = None):
        self._tool_registry = tool_registry
        self._execution_history: list[ExecutionResult] = []

    async def execute(
        self,
        skill: Skill,
        parameters: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        progress_callback: Callable | None = None,
    ) -> ExecutionResult:
        """
        执行技能

        Args:
            skill: 要执行的技能
            parameters: 技能参数
            context: 执行上下文
            progress_callback: 进度回调

        Returns:
            执行结果
        """
        start_time = time.time()
        parameters = parameters or {}
        context = context or {}

        outputs = []
        errors = []
        steps_completed = 0

        # 合并参数
        merged_params = {**skill.parameters, **parameters}

        # 执行步骤
        for step in skill.steps:
            try:
                # 执行步骤
                output = await self._execute_step(step, merged_params, context)
                outputs.append(
                    {
                        "step": step.step_number,
                        "output": output,
                        "success": True,
                    }
                )
                steps_completed += 1

                # 进度回调
                if progress_callback:
                    progress_callback(steps_completed, len(skill.steps))

            except Exception as e:
                error_msg = f"步骤 {step.step_number} 失败: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)

                # 错误处理
                if step.on_failure == "abort":
                    break
                elif step.on_failure == "skip":
                    outputs.append(
                        {
                            "step": step.step_number,
                            "error": str(e),
                            "success": False,
                            "skipped": True,
                        }
                    )
                    steps_completed += 1
                # retry: 继续尝试

        elapsed = (time.time() - start_time) * 1000

        result = ExecutionResult(
            skill_id=skill.id,
            success=len(errors) == 0,
            steps_completed=steps_completed,
            steps_total=len(skill.steps),
            outputs=outputs,
            errors=errors,
            execution_time_ms=elapsed,
            final_result=outputs[-1].get("output") if outputs else None,
        )

        self._execution_history.append(result)

        return result

    async def _execute_step(
        self,
        step: SkillStep,
        parameters: dict[str, Any],
        context: dict[str, Any],
    ) -> Any:
        """执行单个步骤"""
        if not step.tool_name:
            # 无工具步骤，返回描述
            return {"description": step.description}

        # 获取工具
        if self._tool_registry:
            tool = self._tool_registry.get(step.tool_name)
            if tool:
                # 合并参数
                tool_params = {**step.tool_params}

                # 替换参数中的占位符
                for key, value in tool_params.items():
                    if isinstance(value, str) and value.startswith("$"):
                        param_key = value[1:]
                        if param_key in parameters:
                            tool_params[key] = parameters[param_key]

                # 执行工具
                if asyncio.iscoroutinefunction(tool.execute):
                    result = await tool.execute(**tool_params)
                else:
                    result = tool.execute(**tool_params)

                return result

        # 工具不可用
        raise RuntimeError(f"工具不可用: {step.tool_name}")

    def get_execution_history(self, skill_id: str | None = None) -> list[ExecutionResult]:
        """获取执行历史"""
        if skill_id:
            return [r for r in self._execution_history if r.skill_id == skill_id]
        return self._execution_history.copy()

    def get_stats(self) -> dict[str, Any]:
        """获取执行统计"""
        total = len(self._execution_history)
        successful = sum(1 for r in self._execution_history if r.success)

        return {
            "total_executions": total,
            "successful_executions": successful,
            "success_rate": successful / total if total > 0 else 0,
            "avg_execution_time_ms": (
                sum(r.execution_time_ms for r in self._execution_history) / total if total > 0 else 0
            ),
        }
