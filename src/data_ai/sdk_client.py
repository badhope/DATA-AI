"""
DATA-AI HTTP SDK Client (P1-9)

统一 Python SDK，覆盖 8 大能力 (RAG / Agent / Team / Memory / Skill /
MCP / Reasoning / Context) 的同步 HTTP 客户端。

设计目标：
1. **单类多能力** — 一个 ``DataAIClient`` 实例同时能调所有能力接口。
2. **同步优先** — 默认全部方法同步返回 dict，stream / async 用专门的
   辅助方法。
3. **错误一致** — 所有 4xx / 5xx 抛 ``DataAIClientError`` 带 ``status``/
   ``code``/``detail``/``trace_id`` 便于上层处理。
4. **可脱离后端工作** — ``_base_url`` 配错时所有方法抛清晰错误而非崩溃。

使用示例::

    from data_ai.sdk_client import DataAIClient
    client = DataAIClient(base_url="http://localhost:8000", api_key="sk-xxx")

    # Chat
    r = client.chat("hello", model="qwen-turbo")
    print(r["content"])

    # Agent
    agent = client.create_agent(name="helper", model="qwen-turbo")
    run = client.run_agent(agent["id"], "请总结 README")

    # MCP
    for s in client.list_mcp_servers()["data"]:
        print(s["id"], s["name"])

    # Streaming
    for chunk in client.chat_stream("写一首诗", model="qwen-turbo"):
        print(chunk, end="", flush=True)
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx


class DataAIClientError(RuntimeError):
    """统一的 HTTP 错误包装。

    Attributes:
        status: HTTP 状态码
        code: 业务错误码 (来自后端 error.code,或 4xx/5xx 时由 status 推断)
        detail: 错误详情 (string / dict)
        trace_id: 后端 trace_id (如有)
        method: 请求方法
        path: 请求路径
    """

    def __init__(
        self,
        status: int,
        message: str,
        *,
        code: str | None = None,
        detail: Any = None,
        trace_id: str | None = None,
        method: str = "",
        path: str = "",
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code or self._infer_code(status)
        self.detail = detail
        self.trace_id = trace_id
        self.method = method
        self.path = path

    @staticmethod
    def _infer_code(status: int) -> str:
        if status == 401:
            return "UNAUTHORIZED"
        if status == 403:
            return "FORBIDDEN"
        if status == 404:
            return "NOT_FOUND"
        if status == 409:
            return "CONFLICT"
        if status == 422:
            return "VALIDATION"
        if status == 429:
            return "RATE_LIMIT"
        if 400 <= status < 500:
            return "BAD_REQUEST"
        if status >= 500:
            return "SERVER"
        return "UNKNOWN"

    def __repr__(self) -> str:
        bits = [f"status={self.status}", f"code={self.code}"]
        if self.trace_id:
            bits.append(f"trace_id={self.trace_id}")
        if self.path:
            bits.append(f"path={self.path}")
        return f"DataAIClientError({', '.join(bits)}): {self.args[0]}"


class DataAIClient:
    """DATA-AI HTTP API 统一 SDK Client (P1-9)。

    支持能力：
    - Chat (含 streaming + thinking)
    - LLM (list providers / health)
    - Agent (CRUD + run + delegate-many + preset)
    - Team (CRUD + run + messages)
    - Memory (CRUD + search)
    - RAG (upload / list / get / delete / search)
    - Sandbox (CRUD + execute + files + snapshots)
    - Skill (CRUD + execute + extract)
    - Tool (list + execute)
    - Office (word / ppt / excel / pdf 全套)
    - MCP (server CRUD + preset + tools + invoke + health)
    - Reasoning (sequential / reflection / hypothesis / methods)
    - Notifications
    - Sessions
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: str | None = None,
        *,
        timeout: float = 60.0,
        auth_scheme: str = "x-api-key",
        headers: dict[str, str] | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.getenv("DATA_AI_API_KEY", "")
        self.timeout = timeout
        self.auth_scheme = auth_scheme
        self._extra_headers = dict(headers or {})
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=timeout)

    # ─────────────────────────────────────────────────────────────────
    # Context manager / lifecycle
    # ─────────────────────────────────────────────────────────────────

    def __enter__(self) -> DataAIClient:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_client:
            try:
                self._client.close()
            except Exception:
                pass

    # ─────────────────────────────────────────────────────────────────
    # 内部 HTTP 封装
    # ─────────────────────────────────────────────────────────────────

    def _headers(self) -> dict[str, str]:
        h: dict[str, str] = {"Accept": "application/json"}
        if self.api_key:
            if self.auth_scheme == "bearer":
                h["Authorization"] = f"Bearer {self.api_key}"
            else:
                h["x-api-key"] = self.api_key
        for k, v in self._extra_headers.items():
            h.setdefault(k, v)
        return h

    def _url(self, path: str) -> str:
        if path.startswith(("http://", "https://")):
            return path
        if not path.startswith("/"):
            path = "/" + path
        return f"{self.base_url}{path}"

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
        files: Any = None,
        data: Any = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> Any:
        merged_headers = self._headers()
        if headers:
            merged_headers.update(headers)

        # 自动重试: 短网络错误 (connection reset / closed) 重试 2 次
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                resp = self._client.request(
                    method=method,
                    url=self._url(path),
                    params=params,
                    json=json_body,
                    files=files,
                    data=data,
                    headers=merged_headers,
                    timeout=timeout or self.timeout,
                )
                return self._parse_response(resp, method, path)
            except (httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError) as exc:
                last_exc = exc
                # 第 1-2 次重试,加短退避
                if attempt < 2:
                    import time as _t

                    _t.sleep(0.2 * (attempt + 1))
                    continue
                # 失败抛错
                raise DataAIClientError(
                    0,
                    f"网络错误: {exc!r}",
                    code="NETWORK",
                    method=method,
                    path=path,
                ) from exc
            except httpx.HTTPError as exc:
                raise DataAIClientError(
                    0,
                    f"网络错误: {exc!r}",
                    code="NETWORK",
                    method=method,
                    path=path,
                ) from exc
        # 不应该到这里
        raise DataAIClientError(
            0,
            f"网络错误: {last_exc!r}",
            code="NETWORK",
            method=method,
            path=path,
        )

    def _parse_response(self, resp: httpx.Response, method: str, path: str) -> Any:
        if resp.status_code == 204:
            return None
        text = resp.text
        body: Any = None
        if text:
            try:
                body = json.loads(text)
            except json.JSONDecodeError:
                body = text
        if resp.status_code >= 400:
            err_obj: dict[str, Any] | None = None
            if isinstance(body, dict) and "error" in body and isinstance(body["error"], dict):
                err_obj = body["error"]
                detail = err_obj.get("detail", body)
                code = err_obj.get("code")
                trace_id = err_obj.get("trace_id")
                message = (
                    err_obj.get("message")
                    or (detail if isinstance(detail, str) else None)
                    or f"HTTP {resp.status_code}"
                )
            elif isinstance(body, dict) and "detail" in body:
                detail = body["detail"]
                code = None
                trace_id = None
                message = detail if isinstance(detail, str) else json.dumps(detail, ensure_ascii=False)[:300]
            else:
                detail = body
                code = None
                trace_id = None
                message = text[:300] or f"HTTP {resp.status_code}"
            raise DataAIClientError(
                resp.status_code,
                message,
                code=code,
                detail=detail,
                trace_id=trace_id,
                method=method,
                path=path,
            )
        return body

    # ─────────────────────────────────────────────────────────────────
    # 1. Health / System
    # ─────────────────────────────────────────────────────────────────

    def health(self) -> dict[str, Any]:
        """简易 /health。"""
        return self._request("GET", "/health")  # type: ignore[return-value]

    def extensions_health(self) -> dict[str, Any]:
        """详细诊断 (capabilities / 模型数 / 工具数 / endpoints 列表)。"""
        return self._request("GET", "/v1/extensions/health")  # type: ignore[return-value]

    # ─────────────────────────────────────────────────────────────────
    # 2. Chat (含 streaming + thinking)
    # ─────────────────────────────────────────────────────────────────

    def chat(
        self,
        message: str | list[dict[str, str]],
        model: str = "qwen-turbo",
        *,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        enable_thinking: bool = False,
        tools: list[dict] | None = None,
        extra_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """同步 Chat。

        Args:
            message: 单条 user 文本,或 OpenAI messages 列表
            model: 模型 id
            system: 可选 system prompt (单 message 模式时)
            temperature/max_tokens: 生成参数
            enable_thinking: 深度思考模式 (DashScope 兼容模型)
            tools: OpenAI tools schema
            extra_body: 合并到请求体(给特定 provider 的扩展)
        """
        if isinstance(message, str):
            msgs: list[dict[str, str]] = []
            if system:
                msgs.append({"role": "system", "content": system})
            msgs.append({"role": "user", "content": message})
        else:
            msgs = message
        body: dict[str, Any] = {
            "model": model,
            "messages": msgs,
            "temperature": temperature,
        }
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        if enable_thinking:
            body.setdefault("extra_body", {})["enable_thinking"] = True
        if tools:
            body["tools"] = tools
        if extra_body:
            body.setdefault("extra_body", {}).update(extra_body)
        return self._request("POST", "/v1/chat/completions", json_body=body)  # type: ignore[return-value]

    def chat_stream(
        self,
        message: str | list[dict[str, str]],
        model: str = "qwen-turbo",
        *,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        enable_thinking: bool = False,
        extra_body: dict[str, Any] | None = None,
    ) -> Iterator[str]:
        """流式 Chat, yield 增量 content 字符串。"""
        if isinstance(message, str):
            msgs: list[dict[str, str]] = []
            if system:
                msgs.append({"role": "system", "content": system})
            msgs.append({"role": "user", "content": message})
        else:
            msgs = message
        body: dict[str, Any] = {
            "model": model,
            "messages": msgs,
            "stream": True,
            "temperature": temperature,
        }
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        if enable_thinking:
            body.setdefault("extra_body", {})["enable_thinking"] = True
        if extra_body:
            body.setdefault("extra_body", {}).update(extra_body)
        headers = self._headers()
        headers["Accept"] = "text/event-stream"
        with self._client.stream(
            "POST",
            self._url("/v1/chat/completions"),
            json=body,
            headers=headers,
            timeout=self.timeout,
        ) as resp:
            if resp.status_code >= 400:
                # 收集整个 body 然后 raise
                resp.read()
                # 复用一个 _parse_response
                fake = httpx.Response(resp.status_code, content=resp.content)
                self._parse_response(fake, "POST", "/v1/chat/completions")
            for line in resp.iter_lines():
                if not line or not line.startswith("data: "):
                    continue
                payload = line[6:].strip()
                if not payload or payload == "[DONE]":
                    continue
                try:
                    obj = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                try:
                    delta = obj["choices"][0]["delta"]
                except (KeyError, IndexError):
                    continue
                content = delta.get("content")
                if content:
                    yield content

    # ─────────────────────────────────────────────────────────────────
    # 3. LLM providers
    # ─────────────────────────────────────────────────────────────────

    def list_llm_providers(self) -> dict[str, Any]:
        """列所有支持的 LLM provider + 已注册模型。"""
        return self._request("GET", "/v1/llm/providers")  # type: ignore[return-value]

    def llm_health(self, model: str) -> dict[str, Any]:
        """主动 ping 一个模型验证可用性。"""
        return self._request("POST", "/v1/llm/health", json_body={"model": model})  # type: ignore[return-value]

    def list_models(self) -> list[str]:
        """列已注册模型 id 列表。"""
        r = self._request("GET", "/v1/models") or {}
        data = r.get("data", []) if isinstance(r, dict) else []
        return [m.get("id", "") for m in data if isinstance(m, dict)]

    # ─────────────────────────────────────────────────────────────────
    # 4. Agent
    # ─────────────────────────────────────────────────────────────────

    def list_agents(self, q: str | None = None, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if q:
            params["q"] = q
        return self._request("GET", "/v1/agents", params=params)  # type: ignore[return-value]

    def list_agent_presets(self) -> dict[str, Any]:
        return self._request("GET", "/v1/agents/presets")  # type: ignore[return-value]

    def get_agent_preset(self, role: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/agents/presets/{role}")  # type: ignore[return-value]

    def get_agent(self, agent_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/agents/{agent_id}")  # type: ignore[return-value]

    def create_agent(
        self,
        name: str,
        model: str = "qwen-turbo",
        *,
        description: str = "",
        system_prompt: str = "",
        tool_names: list[str] | None = None,
        max_iterations: int = 10,
        temperature: float = 0.7,
        enable_reflection: bool = False,
        preset: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "name": name,
            "model": model,
            "description": description,
            "system_prompt": system_prompt,
            "tool_names": tool_names or [],
            "max_iterations": max_iterations,
            "temperature": temperature,
            "enable_reflection": enable_reflection,
        }
        if preset:
            body["preset"] = preset
        return self._request("POST", "/v1/agents", json_body=body)  # type: ignore[return-value]

    def update_agent(self, agent_id: str, **fields: Any) -> dict[str, Any]:
        return self._request("PATCH", f"/v1/agents/{agent_id}", json_body=fields)  # type: ignore[return-value]

    def delete_agent(self, agent_id: str) -> None:
        self._request("DELETE", f"/v1/agents/{agent_id}")

    def run_agent(
        self,
        agent_id: str,
        input: str,
        *,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"input": input}
        if session_id:
            body["session_id"] = session_id
        return self._request("POST", f"/v1/agents/{agent_id}/run", json_body=body)  # type: ignore[return-value]

    def list_agent_runs(self, agent_id: str, limit: int = 20) -> dict[str, Any]:
        return self._request("GET", f"/v1/agents/{agent_id}/runs", params={"limit": limit})  # type: ignore[return-value]

    def list_all_agent_runs(self, status: str | None = None, limit: int = 50) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit}
        if status:
            params["status"] = status
        return self._request("GET", "/v1/agents/runs", params=params)  # type: ignore[return-value]

    def get_agent_run(self, run_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/agents/runs/{run_id}")  # type: ignore[return-value]

    def resume_agent_run(
        self, run_id: str, *, approved: bool | None = None, reason: str | None = None
    ) -> dict[str, Any]:
        body: dict[str, Any] = {}
        if approved is not None:
            body["approved"] = approved
        if reason is not None:
            body["reason"] = reason
        return self._request("POST", f"/v1/agents/runs/{run_id}/resume", json_body=body)  # type: ignore[return-value]

    def approve_agent_run(self, run_id: str, reason: str = "approved by reviewer") -> dict[str, Any]:
        return self._request("POST", f"/v1/agents/runs/{run_id}/approve", json_body={"reason": reason})  # type: ignore[return-value]

    def reject_agent_run(self, run_id: str, reason: str = "rejected by reviewer") -> dict[str, Any]:
        return self._request("POST", f"/v1/agents/runs/{run_id}/reject", json_body={"reason": reason})  # type: ignore[return-value]

    def delegate_many(self, queries: list[dict[str, Any]], *, model: str | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"queries": queries}
        if model:
            body["model"] = model
        return self._request("POST", "/v1/agents/delegate-many", json_body=body)  # type: ignore[return-value]

    def get_run_tree(self, run_id: str, max_depth: int = 5) -> dict[str, Any]:
        return self._request("GET", f"/v1/agents/runs/{run_id}/tree", params={"max_depth": max_depth})  # type: ignore[return-value]

    def list_sub_runs(self, run_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/agents/runs/{run_id}/sub_runs")  # type: ignore[return-value]

    # ─────────────────────────────────────────────────────────────────
    # 5. Team
    # ─────────────────────────────────────────────────────────────────

    def list_teams(self, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        return self._request("GET", "/v1/teams", params={"limit": limit, "offset": offset})  # type: ignore[return-value]

    def get_team(self, team_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/teams/{team_id}")  # type: ignore[return-value]

    def create_team(
        self,
        name: str,
        members: list[dict[str, Any]],
        *,
        description: str = "",
        mode: str = "collaboration",
        consensus_method: str = "llm_synthesis",
    ) -> dict[str, Any]:
        body = {
            "name": name,
            "description": description,
            "mode": mode,
            "consensus_method": consensus_method,
            "members": members,
        }
        return self._request("POST", "/v1/teams", json_body=body)  # type: ignore[return-value]

    def delete_team(self, team_id: str) -> None:
        self._request("DELETE", f"/v1/teams/{team_id}")

    def run_team(
        self,
        team_id: str,
        input: str,
        *,
        consensus_method: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"input": input}
        if consensus_method:
            body["consensus_method"] = consensus_method
        return self._request("POST", f"/v1/teams/{team_id}/run", json_body=body)  # type: ignore[return-value]

    def get_team_messages(self, team_id: str, limit: int = 100) -> dict[str, Any]:
        return self._request("GET", f"/v1/teams/{team_id}/messages", params={"limit": limit})  # type: ignore[return-value]

    # ─────────────────────────────────────────────────────────────────
    # 6. Memory
    # ─────────────────────────────────────────────────────────────────

    def list_memories(
        self,
        type: str | None = None,
        q: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if type:
            params["type"] = type
        if q:
            params["q"] = q
        return self._request("GET", "/v1/memory", params=params)  # type: ignore[return-value]

    def create_memory(
        self,
        content: str,
        type: str = "note",
        *,
        importance: float = 0.5,
        tags: list[str] | None = None,
        pinned: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "type": type,
            "content": content,
            "importance": importance,
            "tags": tags or [],
            "pinned": pinned,
        }
        if metadata:
            body["metadata"] = metadata
        return self._request("POST", "/v1/memory", json_body=body)  # type: ignore[return-value]

    def get_memory(self, memory_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/memory/{memory_id}")  # type: ignore[return-value]

    def update_memory(self, memory_id: str, **fields: Any) -> dict[str, Any]:
        return self._request("PATCH", f"/v1/memory/{memory_id}", json_body=fields)  # type: ignore[return-value]

    def delete_memory(self, memory_id: str) -> None:
        self._request("DELETE", f"/v1/memory/{memory_id}")

    def search_memory(self, query: str, type: str | None = None, top_k: int = 5) -> dict[str, Any]:
        body: dict[str, Any] = {"query": query, "top_k": top_k}
        if type:
            body["type"] = type
        return self._request("POST", "/v1/memory/search", json_body=body)  # type: ignore[return-value]

    # ─────────────────────────────────────────────────────────────────
    # 7. RAG
    # ─────────────────────────────────────────────────────────────────

    def list_rag_documents(self, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        return self._request("GET", "/v1/rag/documents", params={"limit": limit, "offset": offset})  # type: ignore[return-value]

    def upload_rag_document(self, file_path: str | Path, *, name: str | None = None) -> dict[str, Any]:
        p = Path(file_path)
        with open(p, "rb") as f:
            files = {"file": (name or p.name, f, "application/octet-stream")}
            return self._request("POST", "/v1/rag/documents", files=files)  # type: ignore[return-value]

    def upload_rag_bytes(self, name: str, content: bytes, content_type: str = "text/plain") -> dict[str, Any]:
        files = {"file": (name, content, content_type)}
        return self._request("POST", "/v1/rag/documents", files=files)  # type: ignore[return-value]

    def get_rag_document(self, doc_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/rag/documents/{doc_id}")  # type: ignore[return-value]

    def delete_rag_document(self, doc_id: str) -> None:
        self._request("DELETE", f"/v1/rag/documents/{doc_id}")

    def search_rag(
        self,
        query: str,
        top_k: int = 5,
        *,
        embedder: str | None = None,
        document_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"query": query, "top_k": top_k}
        if embedder:
            body["embedder"] = embedder
        if document_ids:
            body["document_ids"] = document_ids
        return self._request("POST", "/v1/rag/search", json_body=body)  # type: ignore[return-value]

    # ─────────────────────────────────────────────────────────────────
    # 8. Sandbox
    # ─────────────────────────────────────────────────────────────────

    def list_sandboxes(self) -> dict[str, Any]:
        return self._request("GET", "/v1/sandboxes")  # type: ignore[return-value]

    def get_sandbox(self, sandbox_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/sandboxes/{sandbox_id}")  # type: ignore[return-value]

    def create_sandbox(
        self,
        name: str,
        type: str = "local",
        *,
        timeout: int = 30,
        memory: int = 512,
        cpu: int = 50,
        network: bool = True,
        image: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "name": name,
            "type": type,
            "timeout": timeout,
            "memory": memory,
            "cpu": cpu,
            "network": network,
        }
        if image:
            body["image"] = image
        return self._request("POST", "/v1/sandboxes", json_body=body)  # type: ignore[return-value]

    def delete_sandbox(self, sandbox_id: str) -> None:
        self._request("DELETE", f"/v1/sandboxes/{sandbox_id}")

    def execute_in_sandbox(
        self,
        sandbox_id: str,
        language: str,
        code: str,
        *,
        timeout: int = 30,
        stdin: str | None = None,
        env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"language": language, "code": code, "timeout": timeout}
        if stdin:
            body["stdin"] = stdin
        if env:
            body["env"] = env
        return self._request("POST", f"/v1/sandboxes/{sandbox_id}/execute", json_body=body)  # type: ignore[return-value]

    def list_sandbox_files(self, sandbox_id: str, path: str = ".") -> dict[str, Any]:
        return self._request("GET", f"/v1/sandboxes/{sandbox_id}/files", params={"path": path})  # type: ignore[return-value]

    def get_sandbox_file(self, sandbox_id: str, path: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/sandboxes/{sandbox_id}/files/content", params={"path": path})  # type: ignore[return-value]

    def save_sandbox_file(self, sandbox_id: str, path: str, content: str) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/v1/sandboxes/{sandbox_id}/files/content",
            json_body={"path": path, "content": content},
        )  # type: ignore[return-value]

    def list_snapshots(self, sandbox_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/sandboxes/{sandbox_id}/snapshots")  # type: ignore[return-value]

    def create_snapshot(self, sandbox_id: str, name: str, *, description: str = "") -> dict[str, Any]:
        return self._request(
            "POST",
            f"/v1/sandboxes/{sandbox_id}/snapshots",
            json_body={"name": name, "description": description},
        )  # type: ignore[return-value]

    def restore_snapshot(self, sandbox_id: str, name: str) -> dict[str, Any]:
        return self._request("POST", f"/v1/sandboxes/{sandbox_id}/snapshots/{name}/restore")  # type: ignore[return-value]

    def delete_snapshot(self, sandbox_id: str, name: str) -> None:
        self._request("DELETE", f"/v1/sandboxes/{sandbox_id}/snapshots/{name}")

    # ─────────────────────────────────────────────────────────────────
    # 9. Skill
    # ─────────────────────────────────────────────────────────────────

    def list_skills(
        self, category: str | None = None, q: str | None = None, limit: int = 100, offset: int = 0
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if category:
            params["category"] = category
        if q:
            params["q"] = q
        return self._request("GET", "/v1/skills", params=params)  # type: ignore[return-value]

    def get_skill(self, name: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/skills/{name}")  # type: ignore[return-value]

    def create_skill(
        self,
        name: str,
        description: str = "",
        *,
        version: str = "0.1.0",
        tags: list[str] | None = None,
        category: str = "custom",
        parameters: list[dict[str, Any]] | None = None,
        yaml: str | None = None,
        implementation: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "name": name,
            "description": description,
            "version": version,
            "tags": tags or [],
            "category": category,
            "parameters": parameters or [],
        }
        if yaml is not None:
            body["yaml"] = yaml
        if implementation is not None:
            body["implementation"] = implementation
        return self._request("POST", "/v1/skills", json_body=body)  # type: ignore[return-value]

    def save_skill(self, name: str, **fields: Any) -> dict[str, Any]:
        fields["name"] = name
        return self._request("PUT", f"/v1/skills/{name}", json_body=fields)  # type: ignore[return-value]

    def delete_skill(self, name: str) -> None:
        self._request("DELETE", f"/v1/skills/{name}")

    def execute_skill(self, name: str, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._request("POST", f"/v1/skills/{name}/execute", json_body={"parameters": parameters or {}})  # type: ignore[return-value]

    def extract_skill(self, source: str, source_type: str = "text") -> dict[str, Any]:
        return self._request("POST", "/v1/skills/extract", json_body={"source": source, "source_type": source_type})  # type: ignore[return-value]

    # ─────────────────────────────────────────────────────────────────
    # 10. Tool
    # ─────────────────────────────────────────────────────────────────

    def list_tools(self) -> dict[str, Any]:
        return self._request("GET", "/v1/tools")  # type: ignore[return-value]

    def get_tool(self, name: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/tools/{name}")  # type: ignore[return-value]

    def execute_tool(self, name: str, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._request("POST", "/v1/tools/execute", json_body={"tool": name, "parameters": parameters or {}})  # type: ignore[return-value]

    # ─────────────────────────────────────────────────────────────────
    # 11. Office — Word / PPT / Excel / PDF
    # ─────────────────────────────────────────────────────────────────

    def word_read(
        self,
        file_path: str,
        *,
        extract_tables: bool = True,
        extract_images: bool = False,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/office/word/read",
            json_body={"file_path": file_path, "extract_tables": extract_tables, "extract_images": extract_images},
        )  # type: ignore[return-value]

    def word_write(
        self,
        file_path: str,
        content: str,
        *,
        title: str = "",
        author: str = "",
        format: str = "text",
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/office/word/write",
            json_body={"file_path": file_path, "content": content, "title": title, "author": author, "format": format},
        )  # type: ignore[return-value]

    def word_edit(
        self,
        file_path: str,
        operation: str,
        *,
        find: str | None = None,
        replace: str | None = None,
        text: str | None = None,
        level: int | None = None,
        table: list[list[str]] | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"file_path": file_path, "operation": operation}
        if find is not None:
            body["find"] = find
        if replace is not None:
            body["replace"] = replace
        if text is not None:
            body["text"] = text
        if level is not None:
            body["level"] = level
        if table is not None:
            body["table"] = table
        return self._request("POST", "/v1/office/word/edit", json_body=body)  # type: ignore[return-value]

    def word_template(
        self,
        template_path: str,
        data: dict[str, Any],
        output_path: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/office/word/template",
            json_body={"template_path": template_path, "data": data, "output_path": output_path},
        )  # type: ignore[return-value]

    def ppt_read(self, file_path: str) -> dict[str, Any]:
        return self._request("POST", "/v1/office/ppt/read", json_body={"file_path": file_path})  # type: ignore[return-value]

    def ppt_write(self, file_path: str, slides: list[dict[str, Any]], *, title: str = "") -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/office/ppt/write",
            json_body={"file_path": file_path, "title": title, "slides": slides},
        )  # type: ignore[return-value]

    def excel_read(self, file_path: str, sheet_name: str | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"file_path": file_path}
        if sheet_name:
            body["sheet_name"] = sheet_name
        return self._request("POST", "/v1/office/excel/read", json_body=body)  # type: ignore[return-value]

    def excel_write(
        self,
        file_path: str,
        data: list[list[Any]] | dict[str, Any] | str,
        sheet_name: str = "Sheet1",
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/office/excel/write",
            json_body={"file_path": file_path, "data": data, "sheet_name": sheet_name},
        )  # type: ignore[return-value]

    def excel_analyze(self, file_path: str, analysis_type: str = "summary") -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/office/excel/analyze",
            json_body={"file_path": file_path, "analysis_type": analysis_type},
        )  # type: ignore[return-value]

    def excel_chart(
        self,
        file_path: str,
        chart_type: str,
        data_range: str = "",
        *,
        sheet_name: str | None = None,
        output_path: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "file_path": file_path,
            "chart_type": chart_type,
            "data_range": data_range,
        }
        if sheet_name:
            body["sheet_name"] = sheet_name
        if output_path:
            body["output_path"] = output_path
        return self._request("POST", "/v1/office/excel/chart", json_body=body)  # type: ignore[return-value]

    def pdf_read(self, file_path: str) -> dict[str, Any]:
        return self._request("POST", "/v1/office/pdf/read", json_body={"file_path": file_path})  # type: ignore[return-value]

    def pdf_merge(self, file_paths: list[str], output_path: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/office/pdf/merge",
            json_body={"file_paths": file_paths, "output_path": output_path},
        )  # type: ignore[return-value]

    def pdf_split(self, file_path: str, ranges: str, output_dir: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/office/pdf/split",
            json_body={"file_path": file_path, "ranges": ranges, "output_dir": output_dir},
        )  # type: ignore[return-value]

    # ─────────────────────────────────────────────────────────────────
    # 12. MCP (Model Context Protocol)
    # ─────────────────────────────────────────────────────────────────

    def list_mcp_servers(self, include_tools: bool = False) -> dict[str, Any]:
        return self._request("GET", "/v1/mcp/servers", params={"include_tools": str(include_tools).lower()})  # type: ignore[return-value]

    def list_mcp_presets(self) -> dict[str, Any]:
        return self._request("GET", "/v1/mcp/presets")  # type: ignore[return-value]

    def get_mcp_server(self, server_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/mcp/servers/{server_id}")  # type: ignore[return-value]

    def create_mcp_server(
        self,
        name: str,
        *,
        type: str = "stdio",
        command: str = "",
        args: list[str] | None = None,
        url: str = "",
        env: dict[str, str] | None = None,
        description: str = "",
        icon: str = "🔌",
        enabled: bool = True,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "name": name,
            "type": type,
            "command": command,
            "args": args or [],
            "url": url,
            "env": env or {},
            "description": description,
            "icon": icon,
            "enabled": enabled,
        }
        return self._request("POST", "/v1/mcp/servers", json_body=body)  # type: ignore[return-value]

    def update_mcp_server(self, server_id: str, **fields: Any) -> dict[str, Any]:
        return self._request("PATCH", f"/v1/mcp/servers/{server_id}", json_body=fields)  # type: ignore[return-value]

    def delete_mcp_server(self, server_id: str) -> None:
        self._request("DELETE", f"/v1/mcp/servers/{server_id}")

    def install_mcp_preset(self, preset_id: str) -> dict[str, Any]:
        return self._request("POST", f"/v1/mcp/servers/preset/{preset_id}")  # type: ignore[return-value]

    def list_mcp_server_tools(self, server_id: str, refresh: bool = False) -> dict[str, Any]:
        return self._request("GET", f"/v1/mcp/servers/{server_id}/tools", params={"refresh": str(refresh).lower()})  # type: ignore[return-value]

    def list_all_mcp_tools(self) -> dict[str, Any]:
        return self._request("GET", "/v1/mcp/tools")  # type: ignore[return-value]

    def invoke_mcp_tool(
        self,
        server_id: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/mcp/invoke",
            json_body={
                "server_id": server_id,
                "tool_name": tool_name,
                "arguments": arguments or {},
                "timeout": timeout,
            },
        )  # type: ignore[return-value]

    def mcp_health(self) -> dict[str, Any]:
        return self._request("GET", "/v1/mcp/health")  # type: ignore[return-value]

    # ─────────────────────────────────────────────────────────────────
    # 13. Reasoning (CoT / Reflection / Hypothesis)
    # ─────────────────────────────────────────────────────────────────

    def reasoning_methods(self) -> dict[str, Any]:
        return self._request("GET", "/v1/reasoning/methods")  # type: ignore[return-value]

    def reasoning_sequential(
        self,
        question: str,
        *,
        context: str | None = None,
        max_steps: int = 5,
        use_llm: bool = True,
        model: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"question": question, "max_steps": max_steps, "use_llm": use_llm}
        if context:
            body["context"] = context
        if model:
            body["model"] = model
        return self._request("POST", "/v1/reasoning/sequential", json_body=body)  # type: ignore[return-value]

    def reasoning_reflection(
        self,
        question: str,
        draft_answer: str,
        *,
        context: str | None = None,
        use_llm: bool = True,
        model: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "question": question,
            "draft_answer": draft_answer,
            "use_llm": use_llm,
        }
        if context:
            body["context"] = context
        if model:
            body["model"] = model
        return self._request("POST", "/v1/reasoning/reflection", json_body=body)  # type: ignore[return-value]

    def reasoning_hypothesis(
        self,
        question: str,
        observations: list[str] | None = None,
        *,
        max_hypotheses: int = 3,
        use_llm: bool = True,
        model: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "question": question,
            "observations": observations or [],
            "max_hypotheses": max_hypotheses,
            "use_llm": use_llm,
        }
        if model:
            body["model"] = model
        return self._request("POST", "/v1/reasoning/hypothesis", json_body=body)  # type: ignore[return-value]

    # ─────────────────────────────────────────────────────────────────
    # 14. Notifications
    # ─────────────────────────────────────────────────────────────────

    def list_notifications(self, unread_only: bool = False, limit: int = 50) -> dict[str, Any]:
        return self._request(
            "GET", "/v1/notifications", params={"unread_only": str(unread_only).lower(), "limit": limit}
        )  # type: ignore[return-value]

    def mark_notifications_read(
        self,
        ids: list[str] | None = None,
        all_read: bool = False,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"all_read": all_read}
        if ids:
            body["ids"] = ids
        return self._request("POST", "/v1/notifications/mark-read", json_body=body)  # type: ignore[return-value]

    # ─────────────────────────────────────────────────────────────────
    # 15. Sessions
    # ─────────────────────────────────────────────────────────────────

    def list_sessions(self, limit: int = 50) -> dict[str, Any]:
        return self._request("GET", "/v1/sessions", params={"limit": limit})  # type: ignore[return-value]

    def create_session(
        self, title: str = "新对话", model: str = "gpt-4", messages: list[dict] | None = None
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/sessions",
            json_body={"title": title, "model": model, "messages": messages or []},
        )  # type: ignore[return-value]

    def upsert_session(
        self,
        session_id: str,
        title: str = "新对话",
        model: str = "gpt-4",
        messages: list[dict] | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "PUT",
            f"/v1/sessions/{session_id}",
            json_body={"title": title, "model": model, "messages": messages or []},
        )  # type: ignore[return-value]

    def delete_session(self, session_id: str) -> None:
        self._request("DELETE", f"/v1/sessions/{session_id}")

    # ─────────────────────────────────────────────────────────────────────────
    # P1-10 企业治理: 审计 / 配额 / Webhook / 定时任务
    # ─────────────────────────────────────────────────────────────────────────

    # ---------- Audit ----------
    def list_audit(
        self,
        actor: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        status_code: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """查询审计日志 (who/what/when/result),支持多维过滤。"""
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if actor:
            params["actor"] = actor
        if action:
            params["action"] = action
        if resource_type:
            params["resource_type"] = resource_type
        if status_code is not None:
            params["status_code"] = status_code
        return self._request("GET", "/v1/audit", params=params)

    def audit_stats(self) -> dict[str, Any]:
        return self._request("GET", "/v1/audit/stats")

    def export_audit(self, fmt: str = "json", actor: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"fmt": fmt}
        if actor:
            params["actor"] = actor
        return self._request("GET", "/v1/audit/export", params=params)

    # ---------- Quota ----------
    def list_quota_policies(self) -> list[dict[str, Any]]:
        return self._request("GET", "/v1/quota/policies")["policies"]

    def create_quota_policy(
        self,
        scope: str = "key",
        scope_id: str = "",
        daily_token_limit: int | None = None,
        monthly_token_limit: int | None = None,
        daily_request_limit: int | None = None,
        qps_limit: float | None = None,
        max_concurrent: int | None = None,
        enabled: bool = True,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"scope": scope, "scope_id": scope_id, "enabled": enabled}
        if daily_token_limit is not None:
            body["daily_token_limit"] = daily_token_limit
        if monthly_token_limit is not None:
            body["monthly_token_limit"] = monthly_token_limit
        if daily_request_limit is not None:
            body["daily_request_limit"] = daily_request_limit
        if qps_limit is not None:
            body["qps_limit"] = qps_limit
        if max_concurrent is not None:
            body["max_concurrent"] = max_concurrent
        return self._request("POST", "/v1/quota/policies", json_body=body)["policy"]

    def delete_quota_policy(self, scope: str, scope_id: str) -> None:
        self._request("DELETE", f"/v1/quota/policies/{scope}/{scope_id}")

    def quota_usage(
        self,
        actor: str | None = None,
        model: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit}
        if actor:
            params["actor"] = actor
        if model:
            params["model"] = model
        return self._request("GET", "/v1/quota/usage", params=params)

    def quota_status(self, actor: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/quota/status/{actor}")

    # ---------- Webhooks ----------
    def list_webhook_events(self) -> list[str]:
        return self._request("GET", "/v1/webhooks/events")["events"]

    def list_webhooks(self) -> list[dict[str, Any]]:
        return self._request("GET", "/v1/webhooks")["subscriptions"]

    def create_webhook(
        self,
        name: str,
        url: str,
        events: list[str],
        description: str = "",
        max_retries: int = 3,
        timeout_sec: float = 10.0,
        custom_headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "name": name,
            "url": url,
            "events": events,
            "description": description,
            "max_retries": max_retries,
            "timeout_sec": timeout_sec,
        }
        if custom_headers:
            body["custom_headers"] = custom_headers
        return self._request("POST", "/v1/webhooks", json_body=body)["subscription"]

    def get_webhook(self, sub_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/webhooks/{sub_id}")["subscription"]

    def update_webhook(self, sub_id: str, **fields: Any) -> dict[str, Any]:
        return self._request("PATCH", f"/v1/webhooks/{sub_id}", json=fields)["subscription"]

    def delete_webhook(self, sub_id: str) -> None:
        self._request("DELETE", f"/v1/webhooks/{sub_id}")

    async def test_webhook(self, sub_id: str) -> dict[str, Any]:
        return await self._arequest("POST", f"/v1/webhooks/{sub_id}/test")

    def list_webhook_deliveries(
        self,
        sub_id: str | None = None,
        event: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit}
        if sub_id:
            params["sub_id"] = sub_id
        if event:
            params["event"] = event
        if status:
            params["status"] = status
        if sub_id:
            return self._request("GET", f"/v1/webhooks/{sub_id}/deliveries", params={"limit": limit})
        return self._request("GET", "/v1/webhooks/deliveries", params=params)

    # ---------- Scheduler ----------
    def list_jobs(self) -> dict[str, Any]:
        return self._request("GET", "/v1/jobs")

    def create_job(
        self,
        name: str,
        action_type: str = "http",
        action_payload: dict[str, Any] | None = None,
        schedule_kind: str = "every",
        schedule_expression: str = "3600s",
        description: str = "",
        enabled: bool = True,
        timeout_sec: float = 300.0,
    ) -> dict[str, Any]:
        body = {
            "name": name,
            "description": description,
            "action_type": action_type,
            "action_payload": action_payload or {},
            "schedule": {"kind": schedule_kind, "expression": schedule_expression},
            "enabled": enabled,
            "timeout_sec": timeout_sec,
        }
        return self._request("POST", "/v1/jobs", json_body=body)["job"]

    def get_job(self, job_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/jobs/{job_id}")["job"]

    def update_job(self, job_id: str, **fields: Any) -> dict[str, Any]:
        return self._request("PATCH", f"/v1/jobs/{job_id}", json=fields)["job"]

    def delete_job(self, job_id: str) -> None:
        self._request("DELETE", f"/v1/jobs/{job_id}")

    def trigger_job(self, job_id: str) -> dict[str, Any]:
        return self._request("POST", f"/v1/jobs/{job_id}/trigger")["execution"]

    def list_job_executions(
        self,
        job_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": limit}
        if status:
            params["status"] = status
        if job_id:
            return self._request("GET", f"/v1/jobs/{job_id}/executions", params=params)["executions"]
        return self._request("GET", "/v1/jobs/executions/all", params=params)["executions"]

    # ─────────────────────────────────────────────────────────────────────────
    # P1-11 企业治理 Tier 2: 多租户 / RBAC / 成本 / SLA / SSO / 驻留 / 审计链
    # ─────────────────────────────────────────────────────────────────────────

    # ---------- Tenants ----------
    def list_tenants(self, status: str | None = None, plan: str | None = None) -> dict:
        params: dict[str, Any] = {}
        if status:
            params["status"] = status
        if plan:
            params["plan"] = plan
        return self._request("GET", "/v1/tenants", params=params)

    def create_tenant(self, name: str, plan: str = "free", **kwargs: Any) -> dict:
        return self._request("POST", "/v1/tenants", json={"name": name, "plan": plan, **kwargs})["tenant"]

    def get_tenant(self, tenant_id: str) -> dict:
        return self._request("GET", f"/v1/tenants/{tenant_id}")

    def update_tenant(self, tenant_id: str, **kwargs: Any) -> dict:
        return self._request("PATCH", f"/v1/tenants/{tenant_id}", json=kwargs)["tenant"]

    def delete_tenant(self, tenant_id: str) -> None:
        self._request("DELETE", f"/v1/tenants/{tenant_id}")

    def suspend_tenant(self, tenant_id: str) -> dict:
        return self._request("POST", f"/v1/tenants/{tenant_id}/suspend")["tenant"]

    def activate_tenant(self, tenant_id: str) -> dict:
        return self._request("POST", f"/v1/tenants/{tenant_id}/activate")["tenant"]

    def list_tenant_members(self, tenant_id: str) -> list[dict]:
        return self._request("GET", f"/v1/tenants/{tenant_id}/members")["members"]

    def add_tenant_member(self, tenant_id: str, user_id: str, role: str = "member") -> dict:
        return self._request("POST", f"/v1/tenants/{tenant_id}/members", json={"user_id": user_id, "role": role})[
            "member"
        ]

    def remove_tenant_member(self, tenant_id: str, user_id: str) -> None:
        self._request("DELETE", f"/v1/tenants/{tenant_id}/members/{user_id}")

    # ---------- RBAC ----------
    def list_roles(self, tenant_id: str | None = None, include_system: bool = True) -> list[dict]:
        params: dict[str, Any] = {"include_system": include_system}
        if tenant_id:
            params["tenant_id"] = tenant_id
        return self._request("GET", "/v1/rbac/roles", params=params)["roles"]

    def create_role(self, name: str, permissions: list[dict] | None = None, **kwargs: Any) -> dict:
        return self._request("POST", "/v1/rbac/roles", json={"name": name, "permissions": permissions or [], **kwargs})[
            "role"
        ]

    def get_role(self, role_id: str) -> dict:
        return self._request("GET", f"/v1/rbac/roles/{role_id}")["role"]

    def delete_role(self, role_id: str) -> None:
        self._request("DELETE", f"/v1/rbac/roles/{role_id}")

    def list_rbac_policies(self, tenant_id: str = "") -> list[dict]:
        return self._request("GET", "/v1/rbac/policies", params={"tenant_id": tenant_id} if tenant_id else None)[
            "policies"
        ]

    def create_rbac_policy(self, name: str, conditions: list[dict], effect: str = "allow", **kwargs: Any) -> dict:
        return self._request(
            "POST", "/v1/rbac/policies", json={"name": name, "conditions": conditions, "effect": effect, **kwargs}
        )["policy"]

    def delete_rbac_policy(self, policy_id: str) -> None:
        self._request("DELETE", f"/v1/rbac/policies/{policy_id}")

    def list_rbac_assignments(self, user_id: str = "", tenant_id: str = "") -> list[dict]:
        params: dict[str, Any] = {}
        if user_id:
            params["user_id"] = user_id
        if tenant_id:
            params["tenant_id"] = tenant_id
        return self._request("GET", "/v1/rbac/assignments", params=params)["assignments"]

    def assign_role(
        self, user_id: str, role_id: str, tenant_id: str = "", granted_by: str = "", expires_at: float = 0.0
    ) -> dict:
        return self._request(
            "POST",
            "/v1/rbac/assignments",
            json={
                "user_id": user_id,
                "role_id": role_id,
                "tenant_id": tenant_id,
                "granted_by": granted_by,
                "expires_at": expires_at,
            },
        )["assignment"]

    def revoke_role(self, user_id: str, role_id: str, tenant_id: str = "") -> None:
        self._request(
            "DELETE", "/v1/rbac/assignments", params={"user_id": user_id, "role_id": role_id, "tenant_id": tenant_id}
        )

    def rbac_check(
        self, user_id: str, resource: str, action: str, tenant_id: str = "", env: dict | None = None
    ) -> dict:
        return self._request(
            "POST",
            "/v1/rbac/check",
            json={
                "user_id": user_id,
                "resource": resource,
                "action": action,
                "tenant_id": tenant_id,
                "env": env or {},
            },
        )["decision"]

    def rbac_delegate(
        self, from_user: str, to_user: str, role_id: str, tenant_id: str = "", expires_in: float = 3600
    ) -> dict:
        return self._request(
            "POST",
            "/v1/rbac/delegate",
            params={
                "from_user": from_user,
                "to_user": to_user,
                "role_id": role_id,
                "tenant_id": tenant_id,
                "expires_in": expires_in,
            },
        )["assignment"]

    def rbac_recent_decisions(self, limit: int = 50) -> list[dict]:
        return self._request("GET", "/v1/rbac/decisions", params={"limit": limit})["decisions"]

    # ---------- Billing ----------
    def billing_summary(self, tenant_id: str = "", since: float | None = None, until: float | None = None) -> dict:
        params: dict[str, Any] = {"tenant_id": tenant_id} if tenant_id else {}
        if since is not None:
            params["since"] = since
        if until is not None:
            params["until"] = until
        return self._request("GET", "/v1/billing/summary", params=params)["summary"]

    def billing_cost_by_day(self, tenant_id: str = "", days: int = 30) -> list[dict]:
        params: dict[str, Any] = {"days": days}
        if tenant_id:
            params["tenant_id"] = tenant_id
        return self._request("GET", "/v1/billing/cost-by-day", params=params)["series"]

    def billing_top_spenders(self, by: str = "user", tenant_id: str = "", limit: int = 10) -> list[dict]:
        params: dict[str, Any] = {"by": by, "limit": limit}
        if tenant_id:
            params["tenant_id"] = tenant_id
        return self._request("GET", "/v1/billing/top-spenders", params=params)["top"]

    def list_pricing(self) -> list[dict]:
        return self._request("GET", "/v1/billing/pricing")["pricing"]

    def set_pricing(self, model_id: str, input_per_1k: float, output_per_1k: float, **kwargs: Any) -> dict:
        return self._request(
            "POST",
            "/v1/billing/pricing",
            json={
                "model_id": model_id,
                "input_per_1k": input_per_1k,
                "output_per_1k": output_per_1k,
                **kwargs,
            },
        )["pricing"]

    def record_usage(self, **kwargs: Any) -> dict:
        return self._request("POST", "/v1/billing/usage", json=kwargs)["record"]

    def list_usage(self, **kwargs: Any) -> list[dict]:
        return self._request("GET", "/v1/billing/usage", params=kwargs)["records"]

    def list_budgets(self, scope: str | None = None, scope_id: str = "") -> list[dict]:
        params: dict[str, Any] = {}
        if scope:
            params["scope"] = scope
        if scope_id:
            params["scope_id"] = scope_id
        return self._request("GET", "/v1/billing/budgets", params=params)["budgets"]

    def set_budget(self, **kwargs: Any) -> dict:
        return self._request("POST", "/v1/billing/budgets", json=kwargs)["budget"]

    def delete_budget(self, budget_id: str) -> None:
        self._request("DELETE", f"/v1/billing/budgets/{budget_id}")

    def list_cost_centers(self, tenant_id: str = "") -> list[dict]:
        return self._request("GET", "/v1/billing/cost-centers", params={"tenant_id": tenant_id} if tenant_id else None)[
            "cost_centers"
        ]

    def add_cost_center(self, **kwargs: Any) -> dict:
        return self._request("POST", "/v1/billing/cost-centers", json=kwargs)["cost_center"]

    def budget_check(self, tenant_id: str = "", cost_center_id: str = "") -> dict:
        return self._request(
            "GET", "/v1/billing/budget-check", params={"tenant_id": tenant_id, "cost_center_id": cost_center_id}
        )

    def export_invoice(self, tenant_id: str, since: float, until: float, format: str = "json") -> str:
        return self._request(
            "GET",
            "/v1/billing/invoice",
            params={
                "tenant_id": tenant_id,
                "since": since,
                "until": until,
                "format": format,
            },
        )["invoice"]

    # ---------- SLA ----------
    def sla_status(self) -> dict:
        return self._request("GET", "/v1/sla/status")

    def list_slos(self) -> list[dict]:
        return self._request("GET", "/v1/sla/slos")["slos"]

    def create_slo(self, **kwargs: Any) -> dict:
        return self._request("POST", "/v1/sla/slos", json=kwargs)["slo"]

    def evaluate_slo(self, slo_id: str, window_sec: float = 86400) -> dict:
        return self._request("GET", f"/v1/sla/slos/{slo_id}/evaluate", params={"window_sec": window_sec})["report"]

    def evaluate_all_slos(self) -> list[dict]:
        return self._request("GET", "/v1/sla/slos/evaluate")["reports"]

    def list_sla_components(self) -> list[dict]:
        return self._request("GET", "/v1/sla/components")["components"]

    def register_sla_component(self, name: str, description: str = "") -> dict:
        return self._request("POST", "/v1/sla/components", json={"name": name, "description": description})["component"]

    def sla_record_probe(self, **kwargs: Any) -> dict:
        return self._request("POST", "/v1/sla/probe", json=kwargs)["probe"]

    def list_incidents(self, status: str | None = None, limit: int = 50) -> list[dict]:
        params: dict[str, Any] = {"limit": limit}
        if status:
            params["status"] = status
        return self._request("GET", "/v1/sla/incidents", params=params)["incidents"]

    def open_incident(
        self, title: str, severity: str = "minor", affected_components: list[str] | None = None, message: str = ""
    ) -> dict:
        return self._request(
            "POST",
            "/v1/sla/incidents",
            json={
                "title": title,
                "severity": severity,
                "affected_components": affected_components or [],
                "message": message,
            },
        )["incident"]

    def update_incident(self, incident_id: str, status: str, message: str = "", by: str = "") -> dict:
        return self._request(
            "PATCH",
            f"/v1/sla/incidents/{incident_id}",
            json={
                "status": status,
                "message": message,
                "by": by,
            },
        )["incident"]

    def sla_monthly_report(self, year: int, month: int) -> dict:
        return self._request("GET", "/v1/sla/report/monthly", params={"year": year, "month": month})["report"]

    # ---------- SSO ----------
    def list_idps(self) -> list[dict]:
        return self._request("GET", "/v1/sso/idps")["idps"]

    def register_idp(self, **kwargs: Any) -> dict:
        return self._request("POST", "/v1/sso/idps", json=kwargs)["idp"]

    def get_idp(self, idp_id: str) -> dict:
        return self._request("GET", f"/v1/sso/idps/{idp_id}")["idp"]

    def delete_idp(self, idp_id: str) -> None:
        self._request("DELETE", f"/v1/sso/idps/{idp_id}")

    def sso_auth_url(self, idp_id: str, redirect_uri: str) -> str:
        return self._request("GET", "/v1/sso/auth-url", params={"idp_id": idp_id, "redirect_uri": redirect_uri})["url"]

    def sso_login(self, idp_id: str, code: str, redirect_uri: str, tenant_id: str = "") -> dict:
        return self._request(
            "POST",
            "/v1/sso/login",
            params={"idp_id": idp_id},
            json={
                "code": code,
                "redirect_uri": redirect_uri,
                "tenant_id": tenant_id,
            },
        )

    def sso_logout(self, session_id: str) -> bool:
        return self._request("POST", "/v1/sso/logout", params={"session_id": session_id})["revoked"]

    def list_sso_sessions(self, user_id: str = "") -> list[dict]:
        return self._request("GET", "/v1/sso/sessions", params={"user_id": user_id} if user_id else None)["sessions"]

    def list_scim_users(self, active_only: bool = False) -> list[dict]:
        return self._request("GET", "/v1/sso/scim/users", params={"active_only": active_only})["users"]

    def upsert_scim_user(self, user_name: str, **kwargs: Any) -> dict:
        return self._request("POST", "/v1/sso/scim/users", json={"user_name": user_name, **kwargs})["user"]

    def deactivate_scim_user(self, user_name: str) -> None:
        self._request("DELETE", f"/v1/sso/scim/users/{user_name}")

    # ---------- Residency ----------
    def list_regions(self) -> list[dict]:
        return self._request("GET", "/v1/residency/regions")["regions"]

    def add_region(self, **kwargs: Any) -> dict:
        return self._request("POST", "/v1/residency/regions", json=kwargs)["region"]

    def set_region_status(self, region_id: str, status: str) -> dict:
        return self._request("POST", f"/v1/residency/regions/{region_id}/status", params={"status": status})["region"]

    def list_residency_policies(self) -> list[dict]:
        return self._request("GET", "/v1/residency/policies")["policies"]

    def add_residency_policy(self, **kwargs: Any) -> dict:
        return self._request("POST", "/v1/residency/policies", json=kwargs)["policy"]

    def delete_residency_policy(self, policy_id: str) -> None:
        self._request("DELETE", f"/v1/residency/policies/{policy_id}")

    def residency_route(
        self, resource_id: str, data_class: str = "user_data", tenant_id: str = "", prefer_region: str = ""
    ) -> dict:
        return self._request(
            "POST",
            "/v1/residency/route",
            json={
                "resource_id": resource_id,
                "data_class": data_class,
                "tenant_id": tenant_id,
                "prefer_region": prefer_region,
            },
        )["assignment"]

    def residency_can_transfer(self, resource_id: str, from_region: str, to_region: str) -> dict:
        return self._request(
            "POST",
            "/v1/residency/can-transfer",
            params={
                "resource_id": resource_id,
                "from_region": from_region,
                "to_region": to_region,
            },
        )

    def list_residency_assignments(
        self, tenant_id: str = "", data_class: str | None = None, limit: int = 100
    ) -> list[dict]:
        params: dict[str, Any] = {"limit": limit}
        if tenant_id:
            params["tenant_id"] = tenant_id
        if data_class:
            params["data_class"] = data_class
        return self._request("GET", "/v1/residency/assignments", params=params)["assignments"]

    def residency_stats(self) -> dict:
        return self._request("GET", "/v1/residency/stats")

    # ---------- Audit Chain ----------
    def audit_chain_integrity(self) -> dict:
        return self._request("GET", "/v1/audit-chain/integrity")

    def list_audit_blocks(self) -> list[dict]:
        return self._request("GET", "/v1/audit-chain/blocks")["blocks"]

    def audit_chain_add(self, entry: dict) -> dict:
        return self._request("POST", "/v1/audit-chain/add", json={"entry": entry})

    def audit_chain_seal(self) -> dict:
        return self._request("POST", "/v1/audit-chain/seal")["block"]

    def audit_chain_proof(self, entry_id: str) -> dict:
        return self._request("GET", "/v1/audit-chain/proof", params={"entry_id": entry_id})["proof"]

    # ─────────────────────────────────────────────────────────────────────
    # 跨区域复制 (Replication)
    # ─────────────────────────────────────────────────────────────────────

    def replication_stats(self) -> dict:
        return self._request("GET", "/v1/replication/stats")

    def replication_list_policies(
        self, source_region: str = "", target_region: str = "", enabled: bool | None = None
    ) -> list[dict]:
        params: dict[str, Any] = {}
        if source_region:
            params["source_region"] = source_region
        if target_region:
            params["target_region"] = target_region
        if enabled is not None:
            params["enabled"] = str(enabled).lower()
        return self._request("GET", "/v1/replication/policies", params=params)["policies"]

    def replication_create_policy(
        self,
        name: str,
        source_region: str,
        target_region: str,
        mode: str = "async",
        max_lag_sec: float = 30.0,
        encryption: bool = True,
        compression: bool = True,
    ) -> dict:
        return self._request(
            "POST",
            "/v1/replication/policies",
            json={
                "name": name,
                "source_region": source_region,
                "target_region": target_region,
                "mode": mode,
                "max_lag_sec": max_lag_sec,
                "encryption": encryption,
                "compression": compression,
            },
        )["policy"]

    def replication_delete_policy(self, policy_id: str) -> bool:
        return self._request("DELETE", f"/v1/replication/policies/{policy_id}", _expect_json=False) is None

    def replication_list_streams(self, policy_id: str = "", state: str = "") -> list[dict]:
        params: dict[str, Any] = {}
        if policy_id:
            params["policy_id"] = policy_id
        if state:
            params["state"] = state
        return self._request("GET", "/v1/replication/streams", params=params)["streams"]

    def replication_record_sync(self, stream_id: str, records: int, bytes_sent: int, lag_sec: float = 0.0) -> dict:
        return self._request(
            "POST",
            f"/v1/replication/streams/{stream_id}/sync",
            json={"records": records, "bytes_sent": bytes_sent, "lag_sec": lag_sec},
        )["stream"]

    def replication_record_failure(self, stream_id: str, error: str, records_lost: int = 0) -> dict:
        return self._request(
            "POST",
            f"/v1/replication/streams/{stream_id}/failure",
            json={"error": error, "records_lost": records_lost},
        )["stream"]

    def replication_pause_stream(self, stream_id: str) -> dict:
        return self._request("POST", f"/v1/replication/streams/{stream_id}/pause")["stream"]

    def replication_resume_stream(self, stream_id: str) -> dict:
        return self._request("POST", f"/v1/replication/streams/{stream_id}/resume")["stream"]

    def replication_initiate_failover(
        self, from_region: str, to_region: str, mode: str = "planned", reason: str = ""
    ) -> dict:
        return self._request(
            "POST",
            "/v1/replication/failovers",
            json={
                "from_region": from_region,
                "to_region": to_region,
                "mode": mode,
                "reason": reason,
            },
        )["failover"]

    def replication_advance_failover(self, failover_id: str, new_state: str, notes: str = "") -> dict:
        return self._request(
            "POST",
            f"/v1/replication/failovers/{failover_id}/advance",
            json={"new_state": new_state, "notes": notes},
        )["failover"]

    def replication_complete_failover(self, failover_id: str, success: bool, data_loss_records: int = 0) -> dict:
        return self._request(
            "POST",
            f"/v1/replication/failovers/{failover_id}/complete",
            json={"success": success, "data_loss_records": data_loss_records},
        )["failover"]

    def replication_quorum_check(self, region: str, total_replicas: int, reachable_replicas: int) -> dict:
        return self._request(
            "POST",
            "/v1/replication/quorum-check",
            json={
                "region": region,
                "total_replicas": total_replicas,
                "reachable_replicas": reachable_replicas,
            },
        )

    # ─────────────────────────────────────────────────────────────────────
    # 灾备恢复 (Recovery)
    # ─────────────────────────────────────────────────────────────────────

    def recovery_stats(self) -> dict:
        return self._request("GET", "/v1/recovery/stats")

    def recovery_list_schedules(self, enabled: bool | None = None) -> list[dict]:
        params: dict[str, Any] = {}
        if enabled is not None:
            params["enabled"] = str(enabled).lower()
        return self._request("GET", "/v1/recovery/schedules", params=params)["schedules"]

    def recovery_create_schedule(
        self,
        name: str,
        backup_type: str = "full",
        cron_expr: str = "0 2 * * *",
        retention_days: int = 30,
        target_regions: list[str] | None = None,
        encryption: bool = True,
    ) -> dict:
        return self._request(
            "POST",
            "/v1/recovery/schedules",
            json={
                "name": name,
                "backup_type": backup_type,
                "cron_expr": cron_expr,
                "retention_days": retention_days,
                "target_regions": target_regions or ["cn-east"],
                "encryption": encryption,
            },
        )["schedule"]

    def recovery_trigger_backup(self, schedule_id: str, record_count: int = 0) -> dict:
        return self._request(
            "POST",
            f"/v1/recovery/schedules/{schedule_id}/trigger",
            json={"schedule_id": schedule_id, "record_count": record_count},
        )["backup"]

    def recovery_list_backups(self, schedule_id: str = "", status: str = "") -> list[dict]:
        params: dict[str, Any] = {}
        if schedule_id:
            params["schedule_id"] = schedule_id
        if status:
            params["status"] = status
        return self._request("GET", "/v1/recovery/backups", params=params)["backups"]

    def recovery_verify_backup(self, backup_id: str) -> dict:
        return self._request("GET", f"/v1/recovery/backups/{backup_id}/verify")

    def recovery_create_restore(self, backup_id: str, target_region: str = "", reason: str = "") -> dict:
        return self._request(
            "POST",
            "/v1/recovery/restore",
            json={"backup_id": backup_id, "target_region": target_region, "reason": reason},
        )["restore"]

    def recovery_advance_restore(self, restore_id: str, status: str, progress_pct: float | None = None) -> dict:
        payload: dict[str, Any] = {"status": status}
        if progress_pct is not None:
            payload["progress_pct"] = progress_pct
        return self._request("POST", f"/v1/recovery/restore/{restore_id}/advance", json=payload)["restore"]

    def recovery_run_drill(
        self,
        name: str,
        schedule_id: str = "",
        rto_target_sec: float = 3600.0,
        rpo_target_sec: float = 300.0,
        conducted_by: str = "",
    ) -> dict:
        return self._request(
            "POST",
            "/v1/recovery/drill",
            json={
                "name": name,
                "schedule_id": schedule_id,
                "rto_target_sec": rto_target_sec,
                "rpo_target_sec": rpo_target_sec,
                "conducted_by": conducted_by,
            },
        )["drill"]

    def recovery_list_drills(self, result: str = "") -> list[dict]:
        params: dict[str, Any] = {}
        if result:
            params["result"] = result
        return self._request("GET", "/v1/recovery/drills", params=params)["drills"]

    def recovery_create_hold(
        self, resource_id: str, regulation: str, action: str = "preserve", reason: str = ""
    ) -> dict:
        return self._request(
            "POST",
            "/v1/recovery/holds",
            json={
                "resource_id": resource_id,
                "regulation": regulation,
                "action": action,
                "reason": reason,
            },
        )["hold"]

    def recovery_check_action(self, resource_id: str, action: str = "delete") -> dict:
        return self._request("GET", "/v1/recovery/check-action", params={"resource_id": resource_id, "action": action})

    # ─────────────────────────────────────────────────────────────────────
    # SLA 违约赔付 (Compensation)
    # ─────────────────────────────────────────────────────────────────────

    def compensation_stats(self) -> dict:
        return self._request("GET", "/v1/compensation/stats")

    def compensation_list_policies(self, plan_tier: str = "") -> list[dict]:
        params: dict[str, Any] = {}
        if plan_tier:
            params["plan_tier"] = plan_tier
        return self._request("GET", "/v1/compensation/policies", params=params)["policies"]

    def compensation_create_policy(
        self, name: str, plan_tier: str = "enterprise", target_availability_pct: float = 99.9
    ) -> dict:
        return self._request(
            "POST",
            "/v1/compensation/policies",
            json={
                "name": name,
                "plan_tier": plan_tier,
                "target_availability_pct": target_availability_pct,
            },
        )["policy"]

    def compensation_detect_breach(
        self, policy_id: str, tenant_id: str, actual_availability_pct: float, downtime_sec: float = 0.0
    ) -> dict:
        return self._request(
            "POST",
            "/v1/compensation/breach",
            json={
                "policy_id": policy_id,
                "tenant_id": tenant_id,
                "actual_availability_pct": actual_availability_pct,
                "downtime_sec": downtime_sec,
            },
        )["breach"]

    def compensation_list_breaches(self, tenant_id: str = "") -> list[dict]:
        params: dict[str, Any] = {}
        if tenant_id:
            params["tenant_id"] = tenant_id
        return self._request("GET", "/v1/compensation/breaches", params=params)["breaches"]

    def compensation_calculate_credit(self, breach_id: str, monthly_fee_usd: float) -> dict:
        return self._request(
            "POST",
            "/v1/compensation/calculate",
            json={"breach_id": breach_id, "monthly_fee_usd": monthly_fee_usd},
        )["credit"]

    def compensation_apply_credit(self, credit_id: str) -> dict:
        return self._request("POST", f"/v1/compensation/credits/{credit_id}/apply")["credit"]

    def compensation_mark_paid(self, credit_id: str) -> dict:
        return self._request("POST", f"/v1/compensation/credits/{credit_id}/pay")["credit"]

    def compensation_list_credits(self, tenant_id: str = "", status: str = "") -> list[dict]:
        params: dict[str, Any] = {}
        if tenant_id:
            params["tenant_id"] = tenant_id
        if status:
            params["status"] = status
        return self._request("GET", "/v1/compensation/credits", params=params)["credits"]

    def compensation_raise_dispute(self, credit_id: str, tenant_id: str, raised_by: str, reason: str) -> dict:
        return self._request(
            "POST",
            "/v1/compensation/dispute",
            json={
                "credit_id": credit_id,
                "tenant_id": tenant_id,
                "raised_by": raised_by,
                "reason": reason,
            },
        )["dispute"]

    def compensation_resolve_dispute(self, dispute_id: str, resolution: str, uphold_credit: bool = True) -> dict:
        return self._request(
            "POST",
            f"/v1/compensation/dispute/{dispute_id}/resolve",
            json={"resolution": resolution, "uphold_credit": uphold_credit},
        )["dispute"]

    def compensation_tenant_summary(self, tenant_id: str, period_start: float, period_end: float) -> dict:
        return self._request(
            "GET",
            "/v1/compensation/tenant-summary",
            params={
                "tenant_id": tenant_id,
                "period_start": period_start,
                "period_end": period_end,
            },
        )


# ─────────────────────────────────────────────────────────────────────────────
# 便利工厂
# ─────────────────────────────────────────────────────────────────────────────


def create_api_client(
    base_url: str | None = None,
    api_key: str | None = None,
    **kwargs: Any,
) -> DataAIClient:
    """从环境变量 / 默认值创建一个 DataAIClient。

    环境变量:
        DATA_AI_BASE  (默认 http://localhost:8000)
        DATA_AI_API_KEY
    """
    return DataAIClient(
        base_url=base_url or os.getenv("DATA_AI_BASE", "http://localhost:8000"),
        api_key=api_key or os.getenv("DATA_AI_API_KEY"),
        **kwargs,
    )


__all__ = [
    "DataAIClient",
    "DataAIClientError",
    "create_api_client",
]
