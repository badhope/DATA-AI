from __future__ import annotations

import sys
import tempfile
from pathlib import Path


# ── file_read 修复 ──────────────────────────────────────────
from data_ai.core.tool.tools import FileReadTool  # noqa: E402


# 准备测试文件

import asyncio


async def _test_file_read():
    # 1) 走 max_lines
    r1 = await tool.execute(path=tmp_path, max_lines=5)
    assert r1["read_lines"] == 5, f"max_lines=5 应读 5 行,得 {r1['read_lines']}"
    assert "line-001" in r1["content"]
    assert "line-005" in r1["content"]
    assert r1.get("truncated") is True, f"应被截断,得 {r1.get('truncated')}"
    print("  ✓ max_lines=5 读 5 行 + truncated=True")

    # 2) 走 limit
    r2 = await tool.execute(path=tmp_path, limit=3)
    assert r2["read_lines"] == 3, f"limit=3 应读 3 行,得 {r2['read_lines']}"
    print("  ✓ limit=3 读 3 行")

    # 3) max_lines 优先于 limit
    r3 = await tool.execute(path=tmp_path, limit=10, max_lines=2)
    assert r3["read_lines"] == 2, f"max_lines=2 应胜出,得 {r3['read_lines']}"
    print("  ✓ max_lines 优先于 limit")

    # 4) offset 配合
    r4 = await tool.execute(path=tmp_path, offset=100, max_lines=3)
    assert r4["read_lines"] == 3
    assert "line-100" in r4["content"]
    assert "line-102" in r4["content"]
    print("  ✓ offset=100 + max_lines=3 读第 100-102 行")

    # 5) truncated 字段
    r5 = await tool.execute(path=tmp_path, max_lines=1000)
    assert r5.get("truncated") is False, f"读全文件不应 truncated,得 {r5.get('truncated')}"
    print("  ✓ 读全文件 truncated=False")



# 6) 端到端:通过 ToolRegistry 传 max_lines 也能工作

# 通过 /v1/tools/execute 真实 HTTP 测试(更接近用户)
import json
import urllib.error
import urllib.request



def _http(method: str, path: str, payload: dict | None = None, timeout: int = 30):
    url = API + path
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8") or "null")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")



# ── RAG retriever 修复 ─────────────────────────────────────
from data_ai.core.rag.retriever import MMRRetriever, SimilarityRetriever  # noqa: E402


class _MockStore:
    """模拟 store,返回乱序的 (doc_id, score, metadata)"""

    def __init__(self):
        self.docs = {
            "a": ("Alpha content", [1.0, 0.0, 0.0]),
            "b": ("Beta content", [0.8, 0.6, 0.0]),
            "c": ("Gamma content", [0.5, 0.5, 0.7]),
            "d": ("Delta content", [0.0, 1.0, 0.0]),
        }
        # 故意打乱顺序,模拟 store.search 的乱序返回
        self._order = ["b", "d", "a", "c"]
        self._scores = {"a": 0.5, "b": 0.9, "c": 0.2, "d": 0.7}

    def search(self, query_embedding, top_k):
        return [(did, self._scores[did], {}) for did in self._order[:top_k]]

    def get(self, doc_id):
        c, e = self.docs[doc_id]
        from types import SimpleNamespace

        return SimpleNamespace(content=c, embedding=e)


# 期望顺序: b(0.9) > d(0.7) > a(0.5)

# 透传 _score

# top_k 限制


# ── MMRRetriever 修复 ─────────────────────────────────────

# 造一个更受控的 MMR 测试场景
class _MMRStore:
    def __init__(self):
        # 4 个文档,其中 a 和 b 几乎重复(query 应当挑 a 然后再挑 c/d 避开 b)
        self.docs = {
            "a": ("first relevant", [1.0, 0.1, 0.0]),
            "b": ("first relevant (dup)", [0.99, 0.1, 0.0]),  # 跟 a 极相似
            "c": ("second relevant", [0.7, 0.7, 0.0]),
            "d": ("third relevant", [0.0, 1.0, 0.0]),
        }
        self._order = ["a", "b", "c", "d"]
        self._scores = {"a": 0.95, "b": 0.94, "c": 0.70, "d": 0.30}

    def search(self, query_embedding, top_k):
        return [(did, self._scores[did], {}) for did in self._order[:top_k]]

    def get(self, doc_id):
        c, e = self.docs[doc_id]
        from types import SimpleNamespace

        return SimpleNamespace(content=c, embedding=e)


# top_k=2 时,应挑 a(高分) + c 或 d(避免跟 a 重复)
# 验证 _mmr_score 真被赋值

# 验证入参 top_k 真的生效(用 self.top_k=2 但入参 top_k=4)


# ── score_threshold 默认 -1.0 ────────────────────────────
import inspect





# ── pytest 集成 (auto) ────────────────────────────────────
import base64 as _b64
import sys as _sys
import pytest as _pytest
_MODULE_BODY = _b64.b64decode('IiIiClAwLTQg5rWL6K+VOlJBRyByZXRyaWV2ZXIg5L+u5aSNICsgZmlsZV9yZWFkIG1heF9saW5lcyDliKvlkI0KCuimhuebljoKMS4gZmlsZV9yZWFkIOaOpeWPlyBtYXhfbGluZXMg5Y+C5pWwCjIuIGZpbGVfcmVhZCDmjqXlj5cgbGltaXQg5Y+C5pWwCjMuIG1heF9saW5lcyDkvJjlhYjkuo4gbGltaXQKNC4gZmlsZV9yZWFkIOi/lOWbniB0cnVuY2F0ZWQg5a2X5q61CjUuIFNpbWlsYXJpdHlSZXRyaWV2ZXIg5qOA57Si5ZCO5oyJIHNjb3JlIOmZjeW6jwo2LiBTaW1pbGFyaXR5UmV0cmlldmVyIOi/lOWbniBfc2NvcmUg6YCP5LygCjcuIE1NUlJldHJpZXZlciDnnJ/nlKggTU1SIHNjb3JlIOaOkuW6jwo4LiBNTVJSZXRyaWV2ZXIg55So5YWl5Y+CIHRvcF9rKOS4jeaYryBzZWxmLnRvcF9rKQo5LiBzY29yZV90aHJlc2hvbGQg6buY6K6kIC0xLjAo5o6l5Y+X6LSfIGNvc2luZSDnm7jkvLzluqYpCiIiIgpST09UID0gUGF0aChfX2ZpbGVfXykucmVzb2x2ZSgpLnBhcmVudHNbMV0Kc3lzLnBhdGguaW5zZXJ0KDAsIHN0cihST09UIC8gInNyYyIpKQpwcmludCgiWzFdIEZpbGVSZWFkVG9vbC5tYXhfbGluZXMg5Yir5ZCNIikKdG9vbCA9IEZpbGVSZWFkVG9vbCgpCndpdGggdGVtcGZpbGUuTmFtZWRUZW1wb3JhcnlGaWxlKG1vZGU9InciLCBzdWZmaXg9Ii50eHQiLCBkZWxldGU9RmFsc2UsIGVuY29kaW5nPSJ1dGYtOCIpIGFzIGY6CiAgICBmb3IgaSBpbiByYW5nZSgxLCAyMDEpOgogICAgICAgIGYud3JpdGUoZiJsaW5lLXtpOjAzZH1cbiIpCiAgICB0bXBfcGF0aCA9IGYubmFtZQphc3luY2lvLnJ1bihfdGVzdF9maWxlX3JlYWQoKSkKcHJpbnQoIlxuWzJdIFRvb2xSZWdpc3RyeS5leGVjdXRlIOaOpeWPlyBtYXhfbGluZXMiKQpBUEkgPSAiaHR0cDovL2xvY2FsaG9zdDo4MDAwIgpBUElfS0VZID0gInNrLVJFREFDVEVEX0RBU0hTQ09QRV9LRVlfUkVQTEFDRV9NRSIKY29kZSwgYm9keSA9IF9odHRwKAogICAgIlBPU1QiLAogICAgIi92MS90b29scy9leGVjdXRlIiwKICAgIHsidG9vbCI6ICJmaWxlX3JlYWQiLCAicGFyYW1ldGVycyI6IHsicGF0aCI6IHRtcF9wYXRoLCAibWF4X2xpbmVzIjogN319LAopCmFzc2VydCBjb2RlID09IDIwMCwgZiJIVFRQIHtjb2RlfSBib2R5PXtib2R5fSIKcmVzdWx0ID0gKGJvZHkgb3Ige30pLmdldCgicmVzdWx0IikgaWYgaXNpbnN0YW5jZShib2R5LCBkaWN0KSBlbHNlIE5vbmUKaWYgaXNpbnN0YW5jZShyZXN1bHQsIHN0cik6CiAgICByZXN1bHQgPSBqc29uLmxvYWRzKHJlc3VsdCkKYXNzZXJ0IGlzaW5zdGFuY2UocmVzdWx0LCBkaWN0KSwgZiJyZXN1bHQg57G75Z6L6ZSZOiB7dHlwZShyZXN1bHQpfSIKYXNzZXJ0IHJlc3VsdC5nZXQoInJlYWRfbGluZXMiKSA9PSA3LCBmInJlYWRfbGluZXMg5bqUPTcs5b6XIHtyZXN1bHQuZ2V0KCdyZWFkX2xpbmVzJyl9IgpwcmludCgiICDinJMgL3YxL3Rvb2xzL2V4ZWN1dGUg5LygIG1heF9saW5lcz03IOivuyA3IOihjCIpCnByaW50KCJcblszXSBTaW1pbGFyaXR5UmV0cmlldmVyIOaOkuW6j+S/ruWkjSIpCm1vY2sgPSBfTW9ja1N0b3JlKCkKc2ltID0gU2ltaWxhcml0eVJldHJpZXZlcihzdG9yZT1tb2NrKQpkb2NzID0gc2ltLnJldHJpZXZlKCJ0ZXN0IiwgWzEuMCwgMC4wLCAwLjBdLCB0b3Bfaz0zKQppZHNfaW5fb3JkZXIgPSBbCiAgICAiYiIgaWYgIkJldGEiIGluIGQuY29udGVudCBlbHNlICJkIiBpZiAiRGVsdGEiIGluIGQuY29udGVudCBlbHNlICJhIiBpZiAiQWxwaGEiIGluIGQuY29udGVudCBlbHNlICJjIgogICAgZm9yIGQgaW4gZG9jcwpdCmFzc2VydCBpZHNfaW5fb3JkZXIgPT0gWyJiIiwgImQiLCAiYSJdLCBmIuaOkuW6j+mUmTp7aWRzX2luX29yZGVyfSIKcHJpbnQoIiAg4pyTIFNpbWlsYXJpdHlSZXRyaWV2ZXIg5oyJIHNjb3JlIOmZjeW6jzpiKDAuOSkgPiBkKDAuNykgPiBhKDAuNSkiKQphc3NlcnQgZG9jc1swXS5tZXRhZGF0YS5nZXQoIl9zY29yZSIpID09IDAuOSwgZiJfc2NvcmUg6YCP5Lyg6ZSZOntkb2NzWzBdLm1ldGFkYXRhfSIKYXNzZXJ0IGRvY3NbMV0ubWV0YWRhdGEuZ2V0KCJfc2NvcmUiKSA9PSAwLjcKcHJpbnQoIiAg4pyTIF9zY29yZSDpgI/kvKDliLAgbWV0YWRhdGEiKQpkb2NzMiA9IHNpbS5yZXRyaWV2ZSgidGVzdCIsIFsxLjAsIDAuMCwgMC4wXSwgdG9wX2s9MikKYXNzZXJ0IGxlbihkb2NzMikgPT0gMiwgZiJ0b3Bfaz0yIOW6lOi/lCAyIOadoSzlvpcge2xlbihkb2NzMil9IgpwcmludCgiICDinJMgdG9wX2s9MiDkuKXmoLzpmZDliLbov5Tlm57mlbAiKQpwcmludCgiXG5bNF0gTU1SUmV0cmlldmVyIOS/ruWkjSIpCm1tcl9zdG9yZSA9IF9NTVJTdG9yZSgpCm1tciA9IE1NUlJldHJpZXZlcihzdG9yZT1tbXJfc3RvcmUsIGxhbWJkYV9tdWx0PTAuNSwgdG9wX2s9MikKZG9jcyA9IG1tci5yZXRyaWV2ZSgidGVzdCIsIFsxLjAsIDAuMSwgMC4wXSwgdG9wX2s9MikKYXNzZXJ0IGxlbihkb2NzKSA9PSAyLCBmInRvcF9rPTIg5bqU6L+UIDIg5p2hLOW+lyB7bGVuKGRvY3MpfSIKY29udGVudHMgPSBbZC5jb250ZW50IGZvciBkIGluIGRvY3NdCmFzc2VydCBhbnkoImZpcnN0IHJlbGV2YW50IiA9PSBjIGZvciBjIGluIGNvbnRlbnRzKSwgZiLlupTpgIkgYTonZmlyc3QgcmVsZXZhbnQnLOW+lyB7Y29udGVudHN9Igphc3NlcnQgYWxsKCJfbW1yX3Njb3JlIiBpbiBkLm1ldGFkYXRhIGZvciBkIGluIGRvY3MpLCAi5bqU5pyJIF9tbXJfc2NvcmUg5a2X5q61Igphc3NlcnQgYWxsKGlzaW5zdGFuY2UoZC5tZXRhZGF0YVsiX21tcl9zY29yZSJdLCBmbG9hdCkgZm9yIGQgaW4gZG9jcykKcHJpbnQoZiIgIOKckyBNTVJSZXRyaWV2ZXIg6YCJIHtsZW4oZG9jcyl9IOadoSzlkKsgX21tcl9zY29yZSDlrZfmrrUs6aaW5p2hIGE6J2ZpcnN0IHJlbGV2YW50JyIpCm1tcjIgPSBNTVJSZXRyaWV2ZXIoc3RvcmU9bW1yX3N0b3JlLCBsYW1iZGFfbXVsdD0wLjUsIHRvcF9rPTIpCmRvY3NfNCA9IG1tcjIucmV0cmlldmUoInRlc3QiLCBbMS4wLCAwLjEsIDAuMF0sIHRvcF9rPTQpCmFzc2VydCBsZW4oZG9jc180KSA9PSA0LCBmIuWFpeWPgiB0b3Bfaz00IOW6lOi/lCA0IOadoSjkuYvliY3nlKggc2VsZi50b3Bfaz0yIOS8mui/lCAyIOadoSks5b6XIHtsZW4oZG9jc180KX0iCnByaW50KGYiICDinJMg5YWl5Y+CIHRvcF9rPTQg55yf5q2j55Sf5pWIKOS/ruS6hiBzZWxmLnRvcF9rIGJ1Zyks6L+UIHtsZW4oZG9jc180KX0g5p2hIikKcHJpbnQoIlxuWzVdIHNjb3JlX3RocmVzaG9sZCDpu5jorqTlgLwiKQpzaWcgPSBpbnNwZWN0LnNpZ25hdHVyZShTaW1pbGFyaXR5UmV0cmlldmVyLl9faW5pdF9fKQpkZWZhdWx0X3RocmVzaG9sZCA9IHNpZy5wYXJhbWV0ZXJzWyJzY29yZV90aHJlc2hvbGQiXS5kZWZhdWx0CmFzc2VydCBkZWZhdWx0X3RocmVzaG9sZCA9PSAtMS4wLCBmInNjb3JlX3RocmVzaG9sZCDpu5jorqTlupQgLTEuMCzlvpcge2RlZmF1bHRfdGhyZXNob2xkfSIKcHJpbnQoZiIgIOKckyBzY29yZV90aHJlc2hvbGQg6buY6K6kIHtkZWZhdWx0X3RocmVzaG9sZH0gKGNvc2luZSDojIPlm7QgWy0xLDFdKSIpCnByaW50KCJcbiIgKyAiPSIgKiA2MCkKcHJpbnQoIuKchSBQMC00IOa1i+ivleWFqOmDqOmAmui/hyIpCnByaW50KCI9IiAqIDYwKQo=').decode("utf-8")

def _run_module_body() -> None:
    """执行原顶层可执行代码, 把 ``sys.exit()`` 转成 ``SystemExit`` 异常."""
    _orig_exit = _sys.exit
    def _safe_exit(code=0):
        raise SystemExit(code)
    _sys.exit = _safe_exit
    try:
        exec(compile(_MODULE_BODY, __file__, "exec"), globals())
    finally:
        _sys.exit = _orig_exit

if __name__ == "__main__":
    _run_module_body()


def test_run_module_body() -> None:
    """原模块顶层可执行代码跑一遍, sys.exit(0) 视作通过, 非 0 视作失败."""
    try:
        _run_module_body()
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 1
        if code != 0:
            _pytest.fail(f"module body exit code {code}")
