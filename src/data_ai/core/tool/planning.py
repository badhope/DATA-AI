"""
DATA-AI 规划工具和人工介入工具

提供任务规划、分解和人工介入能力。支持：
- 智能 planning()：基于目标生成步骤（启发式 + LLM 可选）
- 任务分解：基于任务内容生成子任务
- 人工介入：通过 input() 提示用户
- 终止：结构化终止信号
- 思考：将思考写入记忆系统
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from typing import Any

from ...utils.logging import get_logger

logger = get_logger(__name__)


# ----------------------------------------------------------------------
# 共享工具
# ----------------------------------------------------------------------


def _get_llm_manager() -> Any | None:
    """懒加载获取 LLMManager，避免循环导入"""
    try:
        from data_ai.core.llm.manager import get_llm_manager

        mgr = get_llm_manager()
        if mgr is not None and mgr.get_default_model() is not None:
            return mgr
    except Exception:
        pass
    return None


def _get_memory_store() -> Any | None:
    """懒加载获取全局 memory store"""
    try:
        from data_ai.core.memory.manager import _memory_store  # type: ignore

        return _memory_store
    except Exception:
        return None


# ----------------------------------------------------------------------
# 关键词驱动的能力模板
# ----------------------------------------------------------------------

_GOAL_KEYWORD_TEMPLATES: dict[str, list[dict[str, str]]] = {
    "code": [
        {"step": 1, "action": "分析需求并确定技术栈", "deliverable": "技术方案文档"},
        {"step": 2, "action": "搭建项目骨架与目录结构", "deliverable": "项目脚手架"},
        {"step": 3, "action": "实现核心功能模块", "deliverable": "可运行代码"},
        {"step": 4, "action": "编写单元测试与边界用例", "deliverable": "测试套件"},
        {"step": 5, "action": "集成调试与文档补充", "deliverable": "完成项目"},
    ],
    "data": [
        {"step": 1, "action": "明确数据源与采集方式", "deliverable": "数据源清单"},
        {"step": 2, "action": "搭建数据管道（ETL/ELT）", "deliverable": "管道代码"},
        {"step": 3, "action": "数据清洗与质量校验", "deliverable": "清洗规则"},
        {"step": 4, "action": "数据分析与建模", "deliverable": "分析报告"},
        {"step": 5, "action": "可视化与结果展示", "deliverable": "可视化产物"},
    ],
    "web": [
        {"step": 1, "action": "需求拆解与信息架构", "deliverable": "PRD 草稿"},
        {"step": 2, "action": "UI/UX 设计稿", "deliverable": "设计稿"},
        {"step": 3, "action": "前端实现", "deliverable": "前端代码"},
        {"step": 4, "action": "后端 API 与数据库", "deliverable": "后端代码"},
        {"step": 5, "action": "联调、测试与部署", "deliverable": "线上版本"},
    ],
    "research": [
        {"step": 1, "action": "界定研究问题与边界", "deliverable": "问题定义"},
        {"step": 2, "action": "检索并收集相关资料", "deliverable": "资料库"},
        {"step": 3, "action": "批判性阅读与信息整理", "deliverable": "读书笔记"},
        {"step": 4, "action": "综合分析形成洞察", "deliverable": "分析报告"},
        {"step": 5, "action": "撰写并交付研究产出", "deliverable": "研究文档"},
    ],
    "general": [
        {"step": 1, "action": "理解任务背景与目标", "deliverable": "目标说明"},
        {"step": 2, "action": "收集必要信息与资源", "deliverable": "信息汇总"},
        {"step": 3, "action": "制定执行策略", "deliverable": "策略文档"},
        {"step": 4, "action": "执行主要任务", "deliverable": "执行结果"},
        {"step": 5, "action": "验证和总结", "deliverable": "总结报告"},
    ],
}


def _classify_goal(goal: str) -> str:
    """根据目标关键词分类，决定使用哪个模板"""
    g = (goal or "").lower()
    code_kw = ["代码", "code", "函数", "class", "脚本", "script", "实现", "develop", "写", "编程"]
    data_kw = ["数据", "data", "分析", "analysis", "统计", "报表", "dataset", "csv", "etl"]
    web_kw = ["网站", "web", "前端", "frontend", "页面", "app", "应用", "网页"]
    research_kw = ["研究", "research", "调研", "论文", "report", "调查", "综述"]

    if any(k in g for k in code_kw):
        return "code"
    if any(k in g for k in data_kw):
        return "data"
    if any(k in g for k in web_kw):
        return "web"
    if any(k in g for k in research_kw):
        return "research"
    return "general"


def _heuristic_plan(goal: str, steps: int) -> list[dict[str, Any]]:
    """基于模板的启发式规划"""
    cat = _classify_goal(goal)
    template = _GOAL_KEYWORD_TEMPLATES[cat]
    if steps < 1:
        steps = 1
    picked = template[:steps]
    if len(picked) < steps:
        # 不足时用 general 模板补齐
        for extra in _GOAL_KEYWORD_TEMPLATES["general"]:
            if len(picked) >= steps:
                break
            if extra not in picked:
                picked.append(extra)

    result: list[dict[str, Any]] = []
    for i, item in enumerate(picked[:steps], start=1):
        result.append(
            {
                "step": i,
                "action": f"[{cat.upper()}] {item['action']}（目标: {goal[:60]}）",
                "deliverable": item["deliverable"],
                "status": "pending",
                "estimated_time_min": max(5, 30 // steps),
            }
        )
    return result


async def _llm_plan(goal: str, steps: int, llm_manager: Any) -> list[dict[str, Any]] | None:
    """调用 LLM 生成计划"""
    try:
        from data_ai.core.llm.manager import ChatMessage

        prompt = (
            f"请为以下目标制定一个 {steps} 步的执行计划。\n"
            f"目标: {goal}\n\n"
            f"严格用以下 JSON 格式返回（不要额外文字）:\n"
            f'[{{"step": 1, "action": "...", "deliverable": "..."}}, ...]'
        )
        messages = [
            ChatMessage(
                role="system",
                content="你是一个项目经理，负责把目标拆解为可执行步骤。始终用 JSON 输出。",
            ),
            ChatMessage(role="user", content=prompt),
        ]
        response = await llm_manager.chat(
            messages=messages,
            temperature=0.3,
        )
        content = response.content or ""
        # 提取 JSON 数组
        m = re.search(r"\[[\s\S]*\]", content)
        if not m:
            return None
        data = json.loads(m.group())
        if not isinstance(data, list):
            return None
        plan: list[dict[str, Any]] = []
        for i, item in enumerate(data[:steps], start=1):
            if isinstance(item, dict):
                plan.append(
                    {
                        "step": i,
                        "action": str(item.get("action", "")) or f"步骤 {i}",
                        "deliverable": str(item.get("deliverable", "")),
                        "status": "pending",
                        "estimated_time_min": max(5, 30 // steps),
                    }
                )
        return plan if plan else None
    except Exception as e:
        logger.warning(f"LLM planning 失败，使用启发式: {e}")
        return None


# ----------------------------------------------------------------------
# 公开工具函数
# ----------------------------------------------------------------------


async def planning(task: str = "", goal: str | None = None, steps: int = 5) -> dict:
    """
    为目标/任务生成结构化计划

    Args:
        task: 任务描述（兼容旧签名）
        goal: 目标描述（推荐使用）
        steps: 计划步骤数量

    Returns:
        {"success": True, "plan": {...}, "total_steps": N}
    """
    final_goal = (goal or task or "").strip()
    if not final_goal:
        return {
            "success": False,
            "error": "缺少目标或任务描述",
            "plan": {"task": "", "steps": [], "status": "failed"},
            "total_steps": 0,
        }

    steps = max(1, min(int(steps or 5), 20))

    # 优先尝试 LLM
    plan_steps: list[dict[str, Any]] | None = None
    llm_manager = _get_llm_manager()
    if llm_manager is not None:
        try:
            plan_steps = await _llm_plan(final_goal, steps, llm_manager)
        except Exception as e:
            logger.warning(f"LLM plan 异常: {e}")

    if not plan_steps:
        plan_steps = _heuristic_plan(final_goal, steps)

    plan = {
        "task": final_goal,
        "goal": final_goal,
        "steps": plan_steps,
        "status": "ready",
        "created_at": _now_iso(),
    }

    return {
        "success": True,
        "plan": plan,
        "total_steps": len(plan_steps),
    }


async def task_decomposition(task: str, depth: int = 2) -> dict:
    """
    将复杂任务分解为更小的子任务。

    Args:
        task: 任务描述
        depth: 分解深度

    Returns:
        {"success": True, "subtasks": [...], "total_subtasks": N, ...}
    """
    task = (task or "").strip()
    if not task:
        return {
            "success": False,
            "error": "缺少任务描述",
            "subtasks": [],
            "total_subtasks": 0,
        }

    # 1. 尝试 LLM 分解
    llm_manager = _get_llm_manager()
    if llm_manager is not None:
        try:
            from data_ai.core.llm.manager import ChatMessage

            prompt = (
                f"请将以下任务分解为 5 个可执行的子任务，按依赖顺序排列：\n"
                f"任务: {task}\n\n"
                f"用以下 JSON 数组返回（不要额外文字）:\n"
                f'[{{"id": "1", "task": "...", "priority": "high|medium|low", '
                f'"dependencies": ["<id>", ...]}}, ...]'
            )
            response = await llm_manager.chat(
                messages=[
                    ChatMessage(
                        role="system",
                        content="你是任务分解助手，总是用 JSON 输出。",
                    ),
                    ChatMessage(role="user", content=prompt),
                ],
                temperature=0.2,
            )
            content = response.content or ""
            m = re.search(r"\[[\s\S]*\]", content)
            if m:
                parsed = json.loads(m.group())
                if isinstance(parsed, list) and parsed:
                    subtasks = []
                    for i, item in enumerate(parsed, start=1):
                        if not isinstance(item, dict):
                            continue
                        subtasks.append(
                            {
                                "id": str(item.get("id", str(i))),
                                "task": str(item.get("task", f"子任务 {i}: {task}")),
                                "priority": str(item.get("priority", "medium")),
                                "dependencies": list(item.get("dependencies", []) or []),
                                "status": "pending",
                            }
                        )
                    if subtasks:
                        return {
                            "success": True,
                            "original_task": task,
                            "subtasks": subtasks,
                            "total_subtasks": len(subtasks),
                        }
        except Exception as e:
            logger.warning(f"LLM 任务分解失败，使用启发式: {e}")

    # 2. 启发式分解
    cat = _classify_goal(task)
    templates = {
        "code": [
            ("分析需求并设计接口", "high", []),
            ("搭建项目骨架", "high", ["1"]),
            ("实现核心模块", "high", ["2"]),
            ("编写单元测试", "medium", ["3"]),
            ("集成测试与文档", "medium", ["4"]),
        ],
        "data": [
            ("确定数据源与采集方式", "high", []),
            ("搭建数据管道", "high", ["1"]),
            ("数据清洗与质量校验", "high", ["2"]),
            ("数据分析与建模", "high", ["3"]),
            ("可视化与报告输出", "medium", ["4"]),
        ],
        "web": [
            ("需求拆解与信息架构", "high", []),
            ("UI 设计稿", "high", ["1"]),
            ("前端实现", "high", ["2"]),
            ("后端 API 与数据库", "high", ["2"]),
            ("联调、测试与部署", "medium", ["3", "4"]),
        ],
        "research": [
            ("界定研究问题", "high", []),
            ("收集资料", "high", ["1"]),
            ("分析整理", "high", ["2"]),
            ("形成洞察", "medium", ["3"]),
            ("撰写报告", "medium", ["4"]),
        ],
        "general": [
            (f"分析任务: {task}", "high", []),
            ("收集必要资源和信息", "high", ["1"]),
            ("执行核心任务", "high", ["2"]),
            ("验证结果", "medium", ["3"]),
            ("输出最终结果", "medium", ["4"]),
        ],
    }

    chosen = templates.get(cat, templates["general"])
    subtasks = []
    for i, (action, prio, deps) in enumerate(chosen, start=1):
        subtasks.append(
            {
                "id": str(i),
                "task": action,
                "priority": prio,
                "dependencies": deps,
                "status": "pending",
            }
        )

    return {
        "success": True,
        "original_task": task,
        "subtasks": subtasks,
        "total_subtasks": len(subtasks),
    }


async def ask_human(
    question: str,
    type: str = "text",
    options: list[str] | None = None,
    default: str | None = None,
) -> dict:
    """
    向用户提问并收集回答。

    Args:
        question: 要问的问题
        type: 输入类型 (text/confirm/choice)
        options: choice 类型的选项
        default: 默认值

    Returns:
        {"success": True, "requires_input": True, "answer": "...", ...}
    """
    payload = {
        "success": True,
        "requires_input": True,
        "question": question,
        "input_type": type,
        "options": options or [],
        "default": default,
        "message": f"[需要用户输入] {question}",
        "answer": None,
        "answered": False,
    }

    # 在非交互式环境（CI、批处理）下不阻塞，直接返回
    if not _is_interactive() or os.environ.get("DATA_AI_NON_INTERACTIVE") == "1":
        payload["interactive"] = False
        payload["note"] = "非交互式环境，未实际获取用户输入"
        return payload

    payload["interactive"] = True

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 已在事件循环中：使用 run_in_executor 把 input() 放到线程
            answer = await loop.run_in_executor(None, lambda: _prompt_user(question, type, options, default))
        else:
            answer = await asyncio.to_thread(_prompt_user, question, type, options, default)
    except Exception as e:
        logger.warning(f"ask_human 提示失败: {e}")
        answer = default

    payload["answer"] = answer
    payload["answered"] = answer is not None
    return payload


def _is_interactive() -> bool:
    """检测是否在交互式终端"""
    try:
        return sys.stdin is not None and sys.stdin.isatty()
    except Exception:
        return False


def _prompt_user(question: str, type_: str, options: list[str] | None, default: str | None) -> str | None:
    """同步提示用户"""
    suffix = ""
    if type_ == "confirm":
        suffix = " (y/n)"
    elif type_ == "choice" and options:
        suffix = f" [{'/'.join(options)}]"

    if default is not None:
        suffix += f" (默认: {default})"

    try:
        raw = input(f"{question}{suffix}: ").strip()
    except EOFError:
        return default
    except KeyboardInterrupt:
        return default

    if not raw and default is not None:
        return default
    if not raw:
        return None

    if type_ == "confirm":
        return raw.lower() in ("y", "yes", "是", "true", "1")
    if type_ == "choice" and options:
        if raw in options:
            return raw
        # 尝试按序号选择
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(options):
                return options[idx]
        except ValueError:
            pass
        return raw

    return raw


async def terminate(reason: str = "Task completed", status: str = "success") -> dict:
    """
    终止当前任务执行

    Args:
        reason: 终止原因
        status: 终止状态（success/failure/cancelled）

    Returns:
        {"success": True, "terminated": True, "reason": ..., "status": ...}
    """
    normalized_status = status.lower() if status else "success"
    if normalized_status not in ("success", "failure", "cancelled", "timeout"):
        normalized_status = "success"

    payload = {
        "success": True,
        "terminated": True,
        "reason": reason,
        "status": normalized_status,
        "timestamp": _now_iso(),
    }

    logger.info(f"[终止] status={normalized_status}, reason={reason}")
    return payload


async def think(thought: str) -> dict:
    """
    记录思考过程，并尝试写入 memory store

    Args:
        thought: 思考内容

    Returns:
        {"success": True, "thought": ..., "stored": bool, ...}
    """
    thought = thought or ""
    stored = False
    try:
        store = _get_memory_store()
        if store is not None:
            store.add_short_term(
                content=f"[think] {thought}",
                importance=0.6,
                source="planning.think",
            )
            stored = True
    except Exception as e:
        logger.debug(f"think 写入 memory 失败: {e}")

    logger.info(f"[思考] {thought}")
    return {
        "success": True,
        "thought": thought,
        "stored": stored,
        "timestamp": _now_iso(),
    }


# ----------------------------------------------------------------------
# 工具注册
# ----------------------------------------------------------------------


def _now_iso() -> str:
    from datetime import datetime

    return datetime.now().isoformat()


def register_planning_tools() -> None:
    from data_ai.core.tool.registry import get_tool_registry

    registry = get_tool_registry()

    registry.register_function(
        name="planning",
        func=planning,
        description="Create a structured plan for a task",
        parameters={
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "The task to plan"},
                "goal": {"type": "string", "description": "Goal description (alias of task)"},
                "steps": {"type": "integer", "description": "Number of steps to break down into"},
            },
            "required": ["task"],
        },
    )

    registry.register_function(
        name="task_decomposition",
        func=task_decomposition,
        description="Decompose a complex task into smaller subtasks",
        parameters={
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "The task to decompose"},
                "depth": {"type": "integer", "description": "Decomposition depth (1-3)"},
            },
            "required": ["task"],
        },
    )

    registry.register_function(
        name="ask_human",
        func=ask_human,
        description="Ask the user for input or confirmation",
        parameters={
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "The question to ask the user"},
                "type": {"type": "string", "description": "Type of input expected (text, confirm, choice)"},
                "options": {"type": "array", "description": "Options for choice type"},
                "default": {"type": "string", "description": "Default value if user provides no input"},
            },
            "required": ["question"],
        },
    )

    registry.register_function(
        name="terminate",
        func=terminate,
        description="Terminate the current task execution",
        parameters={
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "Reason for termination"},
                "status": {"type": "string", "description": "Termination status (success, failure, cancelled)"},
            },
            "required": [],
        },
    )

    registry.register_function(
        name="think",
        func=think,
        description="Internal reasoning and thought process",
        parameters={
            "type": "object",
            "properties": {
                "thought": {"type": "string", "description": "The thought or reasoning"},
            },
            "required": ["thought"],
        },
    )

    logger.info("已注册 5 个规划工具")
