from __future__ import annotations

from typing import Any

import requests


def check(name: str, ok: bool, detail: str = "") -> None:
    (passes if ok else fails).append((name, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"  {mark}  {name:38} {detail}")


def call(method: str, path: str, body: Any = None, *, raw: bool = False) -> tuple[int, Any]:
    r = requests.request(method, BASE + path, json=body, timeout=30)
    if raw:
        return r.status_code, r.text[:200]
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, r.text[:200]


# ──────────────────────────────────────────────────────────────────────
# System
# ──────────────────────────────────────────────────────────────────────


# ──────────────────────────────────────────────────────────────────────
# Chat
# ──────────────────────────────────────────────────────────────────────

# Streaming

# ──────────────────────────────────────────────────────────────────────
# Agents
# ──────────────────────────────────────────────────────────────────────


# listing


# ──────────────────────────────────────────────────────────────────────
# Teams
# ──────────────────────────────────────────────────────────────────────


# ──────────────────────────────────────────────────────────────────────
# Memory
# ──────────────────────────────────────────────────────────────────────


# ──────────────────────────────────────────────────────────────────────
# RAG (upload / list / get / search / delete)
# ──────────────────────────────────────────────────────────────────────
# upload a small text file


# ──────────────────────────────────────────────────────────────────────
# Sandboxes
# ──────────────────────────────────────────────────────────────────────


# ──────────────────────────────────────────────────────────────────────
# Tools
# ──────────────────────────────────────────────────────────────────────

# 找可执行且参数简单（只接受 string/integer 参数）的工具，
# 真正构造能跑通的参数。优先选 ``python_execute`` / ``bash``，因为它们接受 code / command。


# ──────────────────────────────────────────────────────────────────────
# Skills
# ──────────────────────────────────────────────────────────────────────


# ──────────────────────────────────────────────────────────────────────
# Office — happy path: create a real file on disk first, then read/write
# ──────────────────────────────────────────────────────────────────────


# ──────────────────────────────────────────────────────────────────────
# Sessions
# ──────────────────────────────────────────────────────────────────────

# ──────────────────────────────────────────────────────────────────────
# Notifications
# ──────────────────────────────────────────────────────────────────────

# ──────────────────────────────────────────────────────────────────────
# Report
# ──────────────────────────────────────────────────────────────────────


# ── pytest 集成 (auto) ────────────────────────────────────
import base64 as _b64
import sys as _sys

import pytest as _pytest

_MODULE_BODY = _b64.b64decode(
    "IiIiRW5kLXRvLWVuZCBzbW9rZSB0ZXN0IGZvciBldmVyeSBEQVRBLUFJIEhUVFAgcm91dGUuCgpSdW4gd2l0aCB0aGUgYmFja2VuZCBsaXN0ZW5pbmcgb24gaHR0cDovLzEyNy4wLjAuMTo4MDAwIGFuZApEQVRBX0FJX0RFVl9NT0RFPXRydWUgKG9yIERBVEFfQUlfQVBJX0tFWVMgc2V0IGluIHRoZSBlbnYgdGhlIHNlcnZlciB3YXMKbGF1bmNoZWQgd2l0aCkuCgpVc2FnZTo6CgogICAgREFUQV9BSV9ERVZfTU9ERT10cnVlIHB5dGhvbiAtbSBkYXRhX2FpLmNvcmUuYXBpLnNlcnZlciAmCiAgICBweXRob24gdGVzdHMvZTJlX3Ntb2tlLnB5CiIiIgpCQVNFID0gb3MuZW52aXJvbi5nZXQoIkRBVEFfQUlfQkFTRSIsICJodHRwOi8vMTI3LjAuMC4xOjgwMDAiKQpIRUFERVJTID0geyJDb250ZW50LVR5cGUiOiAiYXBwbGljYXRpb24vanNvbiJ9CnBhc3NlczogbGlzdFtzdHJdID0gW10KZmFpbHM6IGxpc3RbdHVwbGVbc3RyLCBzdHJdXSA9IFtdCnByaW50KCJcbltzeXN0ZW1dIikKc2MsIGJvZHkgPSBjYWxsKCJHRVQiLCAiL2hlYWx0aCIpCmNoZWNrKCJoZWFsdGgiLCBzYyA9PSAyMDAgYW5kIGJvZHkuZ2V0KCJzdGF0dXMiKSA9PSAiaGVhbHRoeSIsIGYie3NjfSIpCnNjLCBib2R5ID0gY2FsbCgiR0VUIiwgIi92MS9leHRlbnNpb25zL2hlYWx0aCIpCmNoZWNrKCJleHRlbnNpb25zLmhlYWx0aCIsIHNjID09IDIwMCwgZiJ7c2N9IikKc2MsIGJvZHkgPSBjYWxsKCJHRVQiLCAiL3YxL21vZGVscyIpCmNoZWNrKCJtb2RlbHMubGlzdCIsIHNjID09IDIwMCBhbmQgaXNpbnN0YW5jZShib2R5LmdldCgiZGF0YSIpLCBsaXN0KSwgZiJ7c2N9IikKcHJpbnQoIlxuW2NoYXRdIikKc2MsIGJvZHkgPSBjYWxsKAogICAgIlBPU1QiLAogICAgIi92MS9jaGF0L2NvbXBsZXRpb25zIiwKICAgIHsKICAgICAgICAibW9kZWwiOiAib2ZmbGluZS1jaGF0IiwKICAgICAgICAic3RyZWFtIjogRmFsc2UsCiAgICAgICAgImVuYWJsZV90b29scyI6IEZhbHNlLAogICAgICAgICJtZXNzYWdlcyI6IFt7InJvbGUiOiAidXNlciIsICJjb250ZW50IjogImhpIn1dLAogICAgfSwKKQpjaGVjaygiY2hhdC5jb21wbGV0aW9ucyIsIHNjID09IDIwMCBhbmQgImNob2ljZXMiIGluIGJvZHksIGYie3NjfSIpCnIgPSByZXF1ZXN0cy5wb3N0KAogICAgQkFTRSArICIvdjEvY2hhdC9jb21wbGV0aW9ucyIsCiAgICBqc29uPXsKICAgICAgICAibW9kZWwiOiAib2ZmbGluZS1jaGF0IiwKICAgICAgICAic3RyZWFtIjogVHJ1ZSwKICAgICAgICAiZW5hYmxlX3Rvb2xzIjogRmFsc2UsCiAgICAgICAgIm1lc3NhZ2VzIjogW3sicm9sZSI6ICJ1c2VyIiwgImNvbnRlbnQiOiAiaGkifV0sCiAgICB9LAogICAgc3RyZWFtPVRydWUsCiAgICB0aW1lb3V0PTMwLAopCmxpbmVzID0gW10KZm9yIGxpbmUgaW4gci5pdGVyX2xpbmVzKCk6CiAgICBpZiBsaW5lIGFuZCBsaW5lLmRlY29kZSgpLnN0YXJ0c3dpdGgoImRhdGE6Iik6CiAgICAgICAgbGluZXMuYXBwZW5kKGxpbmUuZGVjb2RlKCkpCiAgICAgICAgaWYgbGVuKGxpbmVzKSA+PSAxIGFuZCAiW0RPTkVdIiBub3QgaW4gbGluZXNbLTFdOgogICAgICAgICAgICBjb250aW51ZQpjaGVjaygiY2hhdC5jb21wbGV0aW9ucy5zdHJlYW0iLCByLnN0YXR1c19jb2RlID09IDIwMCBhbmQgbGVuKGxpbmVzKSA+IDAsIGYie3Iuc3RhdHVzX2NvZGV9IGxpbmVzPXtsZW4obGluZXMpfSIpCnByaW50KCJcblthZ2VudHNdIikKc2MsIGJvZHkgPSBjYWxsKCJQT1NUIiwgIi92MS9hZ2VudHMiLCB7Im5hbWUiOiAic21va2UiLCAibW9kZWwiOiAib2ZmbGluZS1jaGF0IiwgInN5c3RlbV9wcm9tcHQiOiAieW91IGFyZSBhIGhlbHBlciJ9KQphaWQgPSAoYm9keSBvciB7fSkuZ2V0KCJpZCIpIGlmIGlzaW5zdGFuY2UoYm9keSwgZGljdCkgZWxzZSBOb25lCmNoZWNrKCJhZ2VudHMuY3JlYXRlIiwgc2MgaW4gKDIwMCwgMjAxKSBhbmQgYm9vbChhaWQpLCBmIntzY30gaWQ9e2FpZH0iKQppZiBhaWQ6CiAgICBzYywgYm9keSA9IGNhbGwoIkdFVCIsIGYiL3YxL2FnZW50cy97YWlkfSIpCiAgICBjaGVjaygiYWdlbnRzLmdldCIsIHNjID09IDIwMCBhbmQgYm9keS5nZXQoImlkIikgPT0gYWlkLCBmIntzY30iKQoKICAgIHNjLCBib2R5ID0gY2FsbCgiR0VUIiwgZiIvdjEvYWdlbnRzL3thaWR9L3J1bnMiKQogICAgY2hlY2soImFnZW50cy5ydW5zIiwgc2MgPT0gMjAwIGFuZCAiZGF0YSIgaW4gYm9keSwgZiJ7c2N9IikKCiAgICBzYywgYm9keSA9IGNhbGwoIlBBVENIIiwgZiIvdjEvYWdlbnRzL3thaWR9IiwgeyJuYW1lIjogInNtb2tlMiJ9KQogICAgY2hlY2soImFnZW50cy5wYXRjaCIsIHNjID09IDIwMCBhbmQgYm9keS5nZXQoIm5hbWUiKSA9PSAic21va2UyIiwgZiJ7c2N9IikKCiAgICBzYywgYm9keSA9IGNhbGwoIlBPU1QiLCBmIi92MS9hZ2VudHMve2FpZH0vcnVuIiwgeyJpbnB1dCI6ICJzYXkgaGkifSkKICAgIGNoZWNrKCJhZ2VudHMucnVuIiwgc2MgaW4gKDIwMCwgMjAxKSBhbmQgIm91dHB1dCIgaW4gYm9keSwgZiJ7c2N9IikKc2MsIGJvZHkgPSBjYWxsKCJHRVQiLCAiL3YxL2FnZW50cyIpCmNoZWNrKCJhZ2VudHMubGlzdCIsIHNjID09IDIwMCBhbmQgImRhdGEiIGluIGJvZHksIGYie3NjfSIpCmlmIGFpZDoKICAgIHNjLCBfID0gY2FsbCgiREVMRVRFIiwgZiIvdjEvYWdlbnRzL3thaWR9IikKICAgIGNoZWNrKCJhZ2VudHMuZGVsZXRlIiwgc2MgaW4gKDIwMCwgMjA0KSwgZiJ7c2N9IikKcHJpbnQoIlxuW3RlYW1zXSIpCnNjLCBib2R5ID0gY2FsbCgKICAgICJQT1NUIiwKICAgICIvdjEvdGVhbXMiLAogICAgewogICAgICAgICJuYW1lIjogInNtb2tlLXRlYW0iLAogICAgICAgICJtb2RlIjogImNvbGxhYm9yYXRpb24iLAogICAgICAgICJjb25zZW5zdXNfbWV0aG9kIjogImxsbV9zeW50aGVzaXMiLAogICAgICAgICJtZW1iZXJzIjogWwogICAgICAgICAgICB7Im5hbWUiOiAiciIsICJyb2xlIjogInJlc2VhcmNoZXIiLCAid2VpZ2h0IjogMS4wfSwKICAgICAgICAgICAgeyJuYW1lIjogInciLCAicm9sZSI6ICJ3cml0ZXIiLCAid2VpZ2h0IjogMS4wfSwKICAgICAgICBdLAogICAgfSwKKQp0aWQgPSAoYm9keSBvciB7fSkuZ2V0KCJpZCIpIGlmIGlzaW5zdGFuY2UoYm9keSwgZGljdCkgZWxzZSBOb25lCmNoZWNrKCJ0ZWFtcy5jcmVhdGUiLCBzYyBpbiAoMjAwLCAyMDEpIGFuZCBib29sKHRpZCksIGYie3NjfSBpZD17dGlkfSIpCmlmIHRpZDoKICAgIHNjLCBib2R5ID0gY2FsbCgiR0VUIiwgZiIvdjEvdGVhbXMve3RpZH0iKQogICAgY2hlY2soInRlYW1zLmdldCIsIHNjID09IDIwMCBhbmQgYm9keS5nZXQoImlkIikgPT0gdGlkLCBmIntzY30iKQogICAgc2MsIGJvZHkgPSBjYWxsKCJHRVQiLCBmIi92MS90ZWFtcy97dGlkfS9tZXNzYWdlcyIpCiAgICBjaGVjaygidGVhbXMubWVzc2FnZXMiLCBzYyA9PSAyMDAgYW5kICJkYXRhIiBpbiBib2R5LCBmIntzY30iKQogICAgc2MsIGJvZHkgPSBjYWxsKCJQT1NUIiwgZiIvdjEvdGVhbXMve3RpZH0vcnVuIiwgeyJpbnB1dCI6ICJkaXNjdXNzIn0pCiAgICBjaGVjaygidGVhbXMucnVuIiwgc2MgaW4gKDIwMCwgMjAxKSwgZiJ7c2N9IikKc2MsIGJvZHkgPSBjYWxsKCJHRVQiLCAiL3YxL3RlYW1zIikKY2hlY2soInRlYW1zLmxpc3QiLCBzYyA9PSAyMDAgYW5kICJkYXRhIiBpbiBib2R5LCBmIntzY30iKQppZiB0aWQ6CiAgICBzYywgXyA9IGNhbGwoIkRFTEVURSIsIGYiL3YxL3RlYW1zL3t0aWR9IikKICAgIGNoZWNrKCJ0ZWFtcy5kZWxldGUiLCBzYyBpbiAoMjAwLCAyMDQpLCBmIntzY30iKQpwcmludCgiXG5bbWVtb3J5XSIpCnNjLCBib2R5ID0gY2FsbCgKICAgICJQT1NUIiwgIi92MS9tZW1vcnkiLCB7InR5cGUiOiAic2VtYW50aWMiLCAiY29udGVudCI6ICJoZWxsbyB3b3JsZCIsICJpbXBvcnRhbmNlIjogMC41LCAidGFncyI6IFsidGVzdCJdfQopCm1pZCA9IChib2R5IG9yIHt9KS5nZXQoImlkIikgaWYgaXNpbnN0YW5jZShib2R5LCBkaWN0KSBlbHNlIE5vbmUKY2hlY2soIm1lbW9yeS5jcmVhdGUiLCBzYyBpbiAoMjAwLCAyMDEpIGFuZCBib29sKG1pZCksIGYie3NjfSBpZD17bWlkfSIpCmlmIG1pZDoKICAgIHNjLCBib2R5ID0gY2FsbCgiUE9TVCIsICIvdjEvbWVtb3J5L3NlYXJjaCIsIHsicXVlcnkiOiAiaGVsbG8iLCAidG9wX2siOiAzfSkKICAgIGNoZWNrKCJtZW1vcnkuc2VhcmNoIiwgc2MgPT0gMjAwIGFuZCAicmVzdWx0cyIgaW4gYm9keSwgZiJ7c2N9IikKICAgIHNjLCBib2R5ID0gY2FsbCgiUEFUQ0giLCBmIi92MS9tZW1vcnkve21pZH0iLCB7InBpbm5lZCI6IFRydWV9KQogICAgY2hlY2soIm1lbW9yeS51cGRhdGUiLCBzYyA9PSAyMDAgYW5kIGJvZHkuZ2V0KCJwaW5uZWQiKSBpcyBUcnVlLCBmIntzY30iKQpzYywgYm9keSA9IGNhbGwoIkdFVCIsICIvdjEvbWVtb3J5IikKY2hlY2soIm1lbW9yeS5saXN0Iiwgc2MgPT0gMjAwIGFuZCAiZGF0YSIgaW4gYm9keSwgZiJ7c2N9IikKaWYgbWlkOgogICAgc2MsIF8gPSBjYWxsKCJERUxFVEUiLCBmIi92MS9tZW1vcnkve21pZH0iKQogICAgY2hlY2soIm1lbW9yeS5kZWxldGUiLCBzYyBpbiAoMjAwLCAyMDQpLCBmIntzY30iKQpwcmludCgiXG5bcmFnXSIpCnR4dCA9IGlvLkJ5dGVzSU8oYiJEQVRBLUFJIGlzIGEgY2hhdCBhZ2VudC5cbkl0IGhhcyBtZW1vcnksIFJBRywgYW5kIHRvb2xzLlxuIikKdHh0Lm5hbWUgPSAic21va2UudHh0IgpyID0gcmVxdWVzdHMucG9zdCgKICAgIEJBU0UgKyAiL3YxL3JhZy9kb2N1bWVudHMiLAogICAgZmlsZXM9eyJmaWxlIjogKCJzbW9rZS50eHQiLCB0eHQuZ2V0dmFsdWUoKSwgInRleHQvcGxhaW4iKX0sCiAgICB0aW1lb3V0PTYwLAopCnNjLCBib2R5ID0gKAogICAgci5zdGF0dXNfY29kZSwKICAgIChyLmpzb24oKSBpZiByLmhlYWRlcnMuZ2V0KCJjb250ZW50LXR5cGUiLCAiIikuc3RhcnRzd2l0aCgiYXBwbGljYXRpb24vanNvbiIpIGVsc2Ugci50ZXh0WzoyMDBdKSwKKQpyaWQgPSAoYm9keSBvciB7fSkuZ2V0KCJpZCIpIGlmIGlzaW5zdGFuY2UoYm9keSwgZGljdCkgZWxzZSBOb25lCmNoZWNrKCJyYWcudXBsb2FkIiwgc2MgaW4gKDIwMCwgMjAxKSBhbmQgYm9vbChyaWQpLCBmIntzY30gaWQ9e3JpZH0iKQppZiByaWQ6CiAgICBzYywgYm9keSA9IGNhbGwoIkdFVCIsIGYiL3YxL3JhZy9kb2N1bWVudHMve3JpZH0iKQogICAgY2hlY2soInJhZy5nZXQiLCBzYyA9PSAyMDAgYW5kIGJvZHkuZ2V0KCJkb2N1bWVudCIsIHt9KS5nZXQoImlkIikgPT0gcmlkLCBmIntzY30iKQogICAgc2MsIGJvZHkgPSBjYWxsKCJQT1NUIiwgIi92MS9yYWcvc2VhcmNoIiwgeyJxdWVyeSI6ICJhZ2VudCIsICJ0b3BfayI6IDN9KQogICAgY2hlY2soInJhZy5zZWFyY2giLCBzYyA9PSAyMDAsIGYie3NjfSIpCiAgICBzYywgXyA9IGNhbGwoIkRFTEVURSIsIGYiL3YxL3JhZy9kb2N1bWVudHMve3JpZH0iKQogICAgY2hlY2soInJhZy5kZWxldGUiLCBzYyBpbiAoMjAwLCAyMDQpLCBmIntzY30iKQpzYywgYm9keSA9IGNhbGwoIkdFVCIsICIvdjEvcmFnL2RvY3VtZW50cyIpCmNoZWNrKCJyYWcubGlzdCIsIHNjID09IDIwMCBhbmQgImRhdGEiIGluIGJvZHksIGYie3NjfSIpCnByaW50KCJcbltzYW5kYm94XSIpCnNjLCBib2R5ID0gY2FsbCgiUE9TVCIsICIvdjEvc2FuZGJveGVzIiwgeyJuYW1lIjogInNtb2tlIiwgInR5cGUiOiAibG9jYWwifSkKc2lkID0gKGJvZHkgb3Ige30pLmdldCgiaWQiKSBpZiBpc2luc3RhbmNlKGJvZHksIGRpY3QpIGVsc2UgTm9uZQpjaGVjaygic2FuZGJveC5jcmVhdGUiLCBzYyBpbiAoMjAwLCAyMDEpIGFuZCBib29sKHNpZCksIGYie3NjfSBpZD17c2lkfSIpCmlmIHNpZDoKICAgIHNjLCBib2R5ID0gY2FsbCgiUE9TVCIsIGYiL3YxL3NhbmRib3hlcy97c2lkfS9leGVjdXRlIiwgeyJsYW5ndWFnZSI6ICJweXRob24iLCAiY29kZSI6ICJwcmludCgxKzEpIn0pCiAgICBjaGVjaygic2FuZGJveC5leGVjLnB5dGhvbiIsIHNjID09IDIwMCBhbmQgYm9keS5nZXQoInN0ZG91dCIpID09ICIyXG4iLCBmIntzY30gc3Rkb3V0PXtib2R5LmdldCgnc3Rkb3V0Jykhcn0iKQoKICAgIHNjLCBib2R5ID0gY2FsbCgiUE9TVCIsIGYiL3YxL3NhbmRib3hlcy97c2lkfS9leGVjdXRlIiwgeyJsYW5ndWFnZSI6ICJiYXNoIiwgImNvZGUiOiAiZWNobyBoaSJ9KQogICAgY2hlY2soInNhbmRib3guZXhlYy5iYXNoIiwgc2MgPT0gMjAwLCBmIntzY30iKQoKICAgIHNjLCBib2R5ID0gY2FsbCgiUE9TVCIsIGYiL3YxL3NhbmRib3hlcy97c2lkfS9maWxlcy9jb250ZW50IiwgeyJwYXRoIjogImhlbGxvLnR4dCIsICJjb250ZW50IjogImhpIn0pCiAgICBjaGVjaygic2FuZGJveC5zYXZlX2ZpbGUiLCBzYyBpbiAoMjAwLCAyMDEpLCBmIntzY30iKQoKICAgIHNjLCBib2R5ID0gY2FsbCgiR0VUIiwgZiIvdjEvc2FuZGJveGVzL3tzaWR9L2ZpbGVzL2NvbnRlbnQ/cGF0aD1oZWxsby50eHQiKQogICAgY2hlY2soInNhbmRib3guZ2V0X2ZpbGUiLCBzYyA9PSAyMDAgYW5kIGJvZHkuZ2V0KCJjb250ZW50IikgPT0gImhpIiwgZiJ7c2N9IikKCiAgICBzYywgYm9keSA9IGNhbGwoIkdFVCIsIGYiL3YxL3NhbmRib3hlcy97c2lkfS9maWxlcyIpCiAgICBjaGVjaygic2FuZGJveC5saXN0X2ZpbGVzIiwgc2MgPT0gMjAwIGFuZCAidHJlZSIgaW4gYm9keSwgZiJ7c2N9IikKCiAgICBzYywgYm9keSA9IGNhbGwoIlBPU1QiLCBmIi92MS9zYW5kYm94ZXMve3NpZH0vc25hcHNob3RzIiwgeyJuYW1lIjogInMxIn0pCiAgICBjaGVjaygic2FuZGJveC5zbmFwc2hvdCIsIHNjIGluICgyMDAsIDIwMSksIGYie3NjfSIpCgogICAgc2MsIGJvZHkgPSBjYWxsKCJHRVQiLCBmIi92MS9zYW5kYm94ZXMve3NpZH0vc25hcHNob3RzIikKICAgIGNoZWNrKCJzYW5kYm94Lmxpc3Rfc25hcHNob3RzIiwgc2MgPT0gMjAwIGFuZCAiZGF0YSIgaW4gYm9keSwgZiJ7c2N9IikKCiAgICBzYywgXyA9IGNhbGwoIlBPU1QiLCBmIi92MS9zYW5kYm94ZXMve3NpZH0vc25hcHNob3RzL3MxL3Jlc3RvcmUiKQogICAgY2hlY2soInNhbmRib3gucmVzdG9yZV9zbmFwc2hvdCIsIHNjIGluICgyMDAsIDIwNCksIGYie3NjfSIpCgogICAgc2MsIF8gPSBjYWxsKCJERUxFVEUiLCBmIi92MS9zYW5kYm94ZXMve3NpZH0vc25hcHNob3RzL3MxIikKICAgIGNoZWNrKCJzYW5kYm94LmRlbGV0ZV9zbmFwc2hvdCIsIHNjIGluICgyMDAsIDIwNCksIGYie3NjfSIpCnNjLCBib2R5ID0gY2FsbCgiR0VUIiwgIi92MS9zYW5kYm94ZXMiKQpjaGVjaygic2FuZGJveC5saXN0Iiwgc2MgPT0gMjAwIGFuZCAiZGF0YSIgaW4gYm9keSwgZiJ7c2N9IikKaWYgc2lkOgogICAgc2MsIGJvZHkgPSBjYWxsKCJHRVQiLCBmIi92MS9zYW5kYm94ZXMve3NpZH0iKQogICAgY2hlY2soInNhbmRib3guZ2V0Iiwgc2MgPT0gMjAwIGFuZCBib2R5LmdldCgiaWQiKSA9PSBzaWQsIGYie3NjfSIpCiAgICBzYywgXyA9IGNhbGwoIkRFTEVURSIsIGYiL3YxL3NhbmRib3hlcy97c2lkfSIpCiAgICBjaGVjaygic2FuZGJveC5kZWxldGUiLCBzYyBpbiAoMjAwLCAyMDQpLCBmIntzY30iKQpwcmludCgiXG5bdG9vbHNdIikKc2MsIGJvZHkgPSBjYWxsKCJHRVQiLCAiL3YxL3Rvb2xzIikKY2hlY2soCiAgICAidG9vbHMubGlzdCIsCiAgICBzYyA9PSAyMDAgYW5kIGlzaW5zdGFuY2UoYm9keS5nZXQoImRhdGEiKSwgbGlzdCkgYW5kIGxlbihib2R5WyJkYXRhIl0pID4gMCwKICAgIGYie3NjfSBuPXtsZW4oYm9keS5nZXQoJ2RhdGEnLCBbXSkpfSIsCikKd2l0aCBfdGYuTmFtZWRUZW1wb3JhcnlGaWxlKCJ3Iiwgc3VmZml4PSIudHh0IiwgZGVsZXRlPUZhbHNlKSBhcyBfdDoKICAgIF90LndyaXRlKCJkYXRhLWFpIHNtb2tlIGNvbnRlbnRcbiIpCiAgICB0bXBfcGF0aCA9IF90Lm5hbWUKcHJlZmVycmVkID0gWyJweXRob25fZXhlY3V0ZSIsICJiYXNoIiwgIndlYl9zZWFyY2giLCAidmlldyIsICJzdHJfcmVwbGFjZV9lZGl0b3IiLCAiZmlsZV9yZWFkIiwgImZpbGVfd3JpdGUiXQp0YXJnZXQgPSBOb25lCmZvciB0bmFtZSBpbiBwcmVmZXJyZWQ6CiAgICBmb3IgdG9vbCBpbiBib2R5LmdldCgiZGF0YSIpIG9yIFtdOgogICAgICAgIGlmIHRvb2wuZ2V0KCJuYW1lIikgPT0gdG5hbWU6CiAgICAgICAgICAgIHRhcmdldCA9IHRvb2wKICAgICAgICAgICAgYnJlYWsKICAgIGlmIHRhcmdldDoKICAgICAgICBicmVhawppZiBub3QgdGFyZ2V0IGFuZCBib2R5LmdldCgiZGF0YSIpOgogICAgdGFyZ2V0ID0gYm9keVsiZGF0YSJdWzBdCmlmIHRhcmdldDoKICAgIHRuYW1lID0gdGFyZ2V0WyJuYW1lIl0KICAgIGlmIHRuYW1lID09ICJweXRob25fZXhlY3V0ZSI6CiAgICAgICAgcGFyYW1zID0geyJjb2RlIjogInByaW50KDIrMikifQogICAgZWxpZiB0bmFtZSA9PSAiYmFzaCI6CiAgICAgICAgcGFyYW1zID0geyJjb21tYW5kIjogImVjaG8gaGkifQogICAgZWxpZiB0bmFtZSA9PSAiZmlsZV9yZWFkIjoKICAgICAgICBwYXJhbXMgPSB7InBhdGgiOiB0bXBfcGF0aH0KICAgIGVsaWYgdG5hbWUgPT0gImZpbGVfd3JpdGUiOgogICAgICAgIHBhcmFtcyA9IHsicGF0aCI6IHRtcF9wYXRoICsgIi5vdXQiLCAiY29udGVudCI6ICJzbW9rZSJ9CiAgICBlbHNlOgogICAgICAgICMgY29uc3RydWN0IGEgbm9vcCAvIHNlbnNpYmxlIHBhcmFtZXRlciBzZXQgZnJvbSB0aGUgc2NoZW1hCiAgICAgICAgcHJvcGVydGllcyA9ICh0YXJnZXQuZ2V0KCJwYXJhbWV0ZXJzIikgb3Ige30pLmdldCgicHJvcGVydGllcyIsIHt9KSBpZiBpc2luc3RhbmNlKHRhcmdldCwgZGljdCkgZWxzZSB7fQogICAgICAgIHBhcmFtcyA9IHt9CiAgICAgICAgZm9yIHBuYW1lLCBwc2NoZW1hIGluIHByb3BlcnRpZXMuaXRlbXMoKToKICAgICAgICAgICAgdCA9IChwc2NoZW1hIG9yIHt9KS5nZXQoInR5cGUiLCAic3RyaW5nIikKICAgICAgICAgICAgaWYgdCA9PSAic3RyaW5nIjoKICAgICAgICAgICAgICAgIHBhcmFtc1twbmFtZV0gPSAidGVzdCIKICAgICAgICAgICAgZWxpZiB0IGluICgiaW50ZWdlciIsICJudW1iZXIiKToKICAgICAgICAgICAgICAgIHBhcmFtc1twbmFtZV0gPSAxCiAgICAgICAgICAgIGVsaWYgdCA9PSAiYm9vbGVhbiI6CiAgICAgICAgICAgICAgICBwYXJhbXNbcG5hbWVdID0gVHJ1ZQogICAgc2MsIGJvZHkgPSBjYWxsKCJQT1NUIiwgIi92MS90b29scy9leGVjdXRlIiwgeyJ0b29sIjogdG5hbWUsICJwYXJhbWV0ZXJzIjogcGFyYW1zfSkKICAgIGNoZWNrKGYidG9vbHMuZXhlY3V0ZSAoe3RuYW1lfSkiLCBzYyBpbiAoMjAwLCAyMDEpLCBmIntzY30ge3N0cihib2R5KVs6MTIwXX0iKQpwcmludCgiXG5bc2tpbGxzXSIpCnNjLCBib2R5ID0gY2FsbCgKICAgICJQT1NUIiwKICAgICIvdjEvc2tpbGxzIiwKICAgIHsKICAgICAgICAibmFtZSI6ICJzbW9rZS1za2lsbCIsCiAgICAgICAgImRlc2NyaXB0aW9uIjogImFkZCBhK2IiLAogICAgICAgICJjYXRlZ29yeSI6ICJjdXN0b20iLAogICAgICAgICJ0YWdzIjogW10sCiAgICAgICAgInBhcmFtZXRlcnMiOiBbXSwKICAgICAgICAiaW1wbGVtZW50YXRpb24iOiAiZGVmIHJ1bihhLCBiKTpcbiAgICByZXR1cm4gYSArIGJcbiIsCiAgICB9LAopCmNoZWNrKCJza2lsbHMuY3JlYXRlIiwgc2MgaW4gKDIwMCwgMjAxKSBhbmQgYm9keS5nZXQoIm5hbWUiKSA9PSAic21va2Utc2tpbGwiLCBmIntzY30iKQpzYywgYm9keSA9IGNhbGwoIkdFVCIsICIvdjEvc2tpbGxzL3Ntb2tlLXNraWxsIikKY2hlY2soInNraWxscy5nZXQiLCBzYyA9PSAyMDAsIGYie3NjfSIpCnNjLCBib2R5ID0gY2FsbCgKICAgICJQVVQiLAogICAgIi92MS9za2lsbHMvc21va2Utc2tpbGwiLAogICAgewogICAgICAgICJuYW1lIjogInNtb2tlLXNraWxsIiwKICAgICAgICAiZGVzY3JpcHRpb24iOiAicmVuYW1lZCIsCiAgICAgICAgImNhdGVnb3J5IjogImN1c3RvbSIsCiAgICAgICAgInRhZ3MiOiBbXSwKICAgICAgICAicGFyYW1ldGVycyI6IFtdLAogICAgICAgICJpbXBsZW1lbnRhdGlvbiI6ICJkZWYgcnVuKGEsIGIpOiByZXR1cm4gYSArIGJcbiIsCiAgICB9LAopCmNoZWNrKCJza2lsbHMucHV0Iiwgc2MgPT0gMjAwIGFuZCBib2R5LmdldCgiZGVzY3JpcHRpb24iKSA9PSAicmVuYW1lZCIsIGYie3NjfSIpCnNjLCBib2R5ID0gY2FsbCgiUE9TVCIsICIvdjEvc2tpbGxzL3Ntb2tlLXNraWxsL2V4ZWN1dGUiLCB7InBhcmFtZXRlcnMiOiB7ImEiOiAyLCAiYiI6IDN9fSkKY2hlY2soInNraWxscy5leGVjdXRlIiwgc2MgPT0gMjAwLCBmIntzY30ge3N0cihib2R5KVs6MjAwXX0iKQpzYywgYm9keSA9IGNhbGwoCiAgICAiUE9TVCIsICIvdjEvc2tpbGxzL2V4dHJhY3QiLCB7InNvdXJjZSI6ICJXaGVuIHRoZSB1c2VyIHNheXMgaGVsbG8sIHJlcGx5IHdpdGggaGkuIiwgInNvdXJjZV90eXBlIjogInRleHQifQopCmNoZWNrKCJza2lsbHMuZXh0cmFjdCIsIHNjID09IDIwMCwgZiJ7c2N9IikKc2MsIGJvZHkgPSBjYWxsKCJHRVQiLCAiL3YxL3NraWxscyIpCmNoZWNrKCJza2lsbHMubGlzdCIsIHNjID09IDIwMCBhbmQgImRhdGEiIGluIGJvZHksIGYie3NjfSIpCnNjLCBfID0gY2FsbCgiREVMRVRFIiwgIi92MS9za2lsbHMvc21va2Utc2tpbGwiKQpjaGVjaygic2tpbGxzLmRlbGV0ZSIsIHNjIGluICgyMDAsIDIwNCksIGYie3NjfSIpCnByaW50KCJcbltvZmZpY2VdIikKd2l0aCB0ZW1wZmlsZS5UZW1wb3JhcnlEaXJlY3RvcnkoKSBhcyB0ZDoKICAgIHRkX3BhdGggPSBQYXRoKHRkKQogICAgIyBXb3JkCiAgICB3b3JkX2luID0gdGRfcGF0aCAvICJpbi5kb2N4IgogICAgIyBFbXB0eSBmaWxlIGlzIGludmFsaWQgLmRvY3g7IGp1c3QgdGVzdCB0aGF0IHRoZSBBUEkgZ2l2ZXMgYSBzYW5lIDR4eAogICAgd29yZF9pbi53cml0ZV9ieXRlcyhiIiIpCiAgICBzYywgYm9keSA9IGNhbGwoIlBPU1QiLCAiL3YxL29mZmljZS93b3JkL3JlYWQiLCB7ImZpbGVfcGF0aCI6IHN0cih3b3JkX2luKX0pCiAgICAjIEVtcHR5IC5kb2N4IOW6lOivpSA0eHjvvIjmlofku7bkuI3lkIjms5XvvInvvIzkuI3mmK8gNXh4IOKAlCDoh7PlsJHor4HmmI7lvILluLjooqvmraPnoa7mjZXojrflubbov5Tlm54gNHh4CiAgICBjaGVjaygib2ZmaWNlLndvcmQucmVhZC5lbXB0eSIsIHNjIGluICg0MDAsIDQyMiksIGYie3NjfSIpCiAgICB3b3JkX291dCA9IHRkX3BhdGggLyAib3V0LmRvY3giCiAgICBzYywgYm9keSA9IGNhbGwoCiAgICAgICAgIlBPU1QiLAogICAgICAgICIvdjEvb2ZmaWNlL3dvcmQvd3JpdGUiLAogICAgICAgIHsiZmlsZV9wYXRoIjogc3RyKHdvcmRfb3V0KSwgImNvbnRlbnQiOiAiSGVsbG8gd29ybGQuXG5MaW5lIDIuIiwgInRpdGxlIjogIlRlc3QifSwKICAgICkKICAgIGNoZWNrKCJvZmZpY2Uud29yZC53cml0ZSIsIHNjID09IDIwMCBhbmQgd29yZF9vdXQuZXhpc3RzKCksIGYie3NjfSBleGlzdHM9e3dvcmRfb3V0LmV4aXN0cygpfSIpCiAgICBzYywgYm9keSA9IGNhbGwoIlBPU1QiLCAiL3YxL29mZmljZS93b3JkL3JlYWQiLCB7ImZpbGVfcGF0aCI6IHN0cih3b3JkX291dCl9KQogICAgY2hlY2soIm9mZmljZS53b3JkLnJlYWQuYmFjayIsIHNjID09IDIwMCwgZiJ7c2N9IikKCiAgICAjIFBQVAogICAgcHB0X291dCA9IHRkX3BhdGggLyAib3V0LnBwdHgiCiAgICBzYywgYm9keSA9IGNhbGwoCiAgICAgICAgIlBPU1QiLAogICAgICAgICIvdjEvb2ZmaWNlL3BwdC93cml0ZSIsCiAgICAgICAgewogICAgICAgICAgICAiZmlsZV9wYXRoIjogc3RyKHBwdF9vdXQpLAogICAgICAgICAgICAidGl0bGUiOiAiRGVtbyIsCiAgICAgICAgICAgICJzbGlkZXMiOiBbCiAgICAgICAgICAgICAgICB7InRpdGxlIjogIlNsaWRlIDEiLCAiY29udGVudCI6ICJGaXJzdCJ9LAogICAgICAgICAgICAgICAgeyJjb250ZW50IjogIlNlY29uZCJ9LAogICAgICAgICAgICBdLAogICAgICAgIH0sCiAgICApCiAgICBjaGVjaygib2ZmaWNlLnBwdC53cml0ZSIsIHNjID09IDIwMCBhbmQgcHB0X291dC5leGlzdHMoKSwgZiJ7c2N9IGV4aXN0cz17cHB0X291dC5leGlzdHMoKX0iKQogICAgc2MsIGJvZHkgPSBjYWxsKCJQT1NUIiwgIi92MS9vZmZpY2UvcHB0L3JlYWQiLCB7ImZpbGVfcGF0aCI6IHN0cihwcHRfb3V0KX0pCiAgICBjaGVjaygib2ZmaWNlLnBwdC5yZWFkIiwgc2MgPT0gMjAwIGFuZCAic2xpZGVzIiBpbiBib2R5LCBmIntzY30iKQoKICAgICMgRXhjZWwg4oCUIOW/hemhu+WFiCB3cml0ZSDmiY3og70gcmVhZAogICAgeGxzX291dCA9IHRkX3BhdGggLyAib3V0Lnhsc3giCiAgICBzYywgYm9keSA9IGNhbGwoCiAgICAgICAgIlBPU1QiLAogICAgICAgICIvdjEvb2ZmaWNlL2V4Y2VsL3dyaXRlIiwKICAgICAgICB7CiAgICAgICAgICAgICJmaWxlX3BhdGgiOiBzdHIoeGxzX291dCksCiAgICAgICAgICAgICJzaGVldF9uYW1lIjogIlNoZWV0MSIsCiAgICAgICAgICAgICJkYXRhIjogeyJoZWFkZXJzIjogWyJhIiwgImIiLCAiYyJdLCAicm93cyI6IFtbMSwgMiwgM10sIFs0LCA1LCA2XV19LAogICAgICAgIH0sCiAgICApCiAgICBjaGVjaygib2ZmaWNlLmV4Y2VsLndyaXRlIiwgc2MgPT0gMjAwIGFuZCB4bHNfb3V0LmV4aXN0cygpLCBmIntzY30gZXhpc3RzPXt4bHNfb3V0LmV4aXN0cygpfSIpCiAgICBzYywgYm9keSA9IGNhbGwoIlBPU1QiLCAiL3YxL29mZmljZS9leGNlbC9yZWFkIiwgeyJmaWxlX3BhdGgiOiBzdHIoeGxzX291dCl9KQogICAgY2hlY2soIm9mZmljZS5leGNlbC5yZWFkIiwgc2MgPT0gMjAwIGFuZCAic2hlZXRzIiBpbiBib2R5LCBmIntzY30iKQogICAgc2MsIGJvZHkgPSBjYWxsKCJQT1NUIiwgIi92MS9vZmZpY2UvZXhjZWwvYW5hbHl6ZSIsIHsiZmlsZV9wYXRoIjogc3RyKHhsc19vdXQpLCAiYW5hbHlzaXNfdHlwZSI6ICJzdW1tYXJ5In0pCiAgICBjaGVjaygib2ZmaWNlLmV4Y2VsLmFuYWx5emUiLCBzYyA9PSAyMDAsIGYie3NjfSIpCgogICAgIyBQREYg4oCUIHJlYWQgZW1wdHkgLyA0MDQsIHRoZW4gYnVpbGQgYSByZWFsIG9uZSB2aWEgcGRmX3NwbGl0IG9mIGEgbWluaW1hbCBwZGYKICAgIHBkZl9wYXRoID0gdGRfcGF0aCAvICJhLnBkZiIKICAgICMgdXNlIHdvcmRfb3V0IHRvIG1ha2UgYSByZWFsIFBERiB2aWEgbWVyZ2UgKHdpdGggYSBzaW5nbGUgaW5wdXQpCiAgICBzYywgYm9keSA9IGNhbGwoCiAgICAgICAgIlBPU1QiLAogICAgICAgICIvdjEvb2ZmaWNlL3BkZi9tZXJnZSIsCiAgICAgICAgewogICAgICAgICAgICAiZmlsZV9wYXRocyI6IFtzdHIocHB0X291dCldLCAgIyBwcHQgaXMgbm90IGEgcGRmOyBleHBlY3QgZmFpbHVyZSBvciBncmFjZWZ1bCA0eHgKICAgICAgICAgICAgIm91dHB1dF9wYXRoIjogc3RyKHRkX3BhdGggLyAibWVyZ2VkLnBkZiIpLAogICAgICAgIH0sCiAgICApCiAgICBjaGVjaygib2ZmaWNlLnBkZi5tZXJnZS5iYWRfaW5wdXQiLCBzYyBpbiAoMjAwLCAyMDEsIDQwMCwgNDIyLCA1MDApLCBmIntzY30iKQpwcmludCgiXG5bc2Vzc2lvbnNdIikKc2MsIGJvZHkgPSBjYWxsKCJHRVQiLCAiL3YxL3Nlc3Npb25zIikKY2hlY2soInNlc3Npb25zLmxpc3QiLCBzYyA9PSAyMDAsIGYie3NjfSIpCnByaW50KCJcbltub3RpZmljYXRpb25zXSIpCnNjLCBib2R5ID0gY2FsbCgiR0VUIiwgIi92MS9ub3RpZmljYXRpb25zIikKY2hlY2soIm5vdGlmaWNhdGlvbnMubGlzdCIsIHNjID09IDIwMCwgZiJ7c2N9IikKc2MsIGJvZHkgPSBjYWxsKCJHRVQiLCAiL3YxL25vdGlmaWNhdGlvbnM/dW5yZWFkX29ubHk9dHJ1ZSIpCmNoZWNrKCJub3RpZmljYXRpb25zLnVucmVhZCIsIHNjID09IDIwMCwgZiJ7c2N9IikKc2MsIGJvZHkgPSBjYWxsKCJQT1NUIiwgIi92MS9ub3RpZmljYXRpb25zL21hcmstcmVhZCIsIHsiYWxsX3JlYWQiOiBUcnVlfSkKY2hlY2soIm5vdGlmaWNhdGlvbnMubWFya19hbGxfcmVhZCIsIHNjID09IDIwMCwgZiJ7c2N9IikKcHJpbnQoKQp0b3RhbCA9IGxlbihwYXNzZXMpICsgbGVuKGZhaWxzKQpwcmludChmIj09PSB7bGVuKHBhc3Nlcyl9L3t0b3RhbH0gcGFzc2VkLCB7bGVuKGZhaWxzKX0gZmFpbGVkID09PSIpCmZvciBuYW1lLCBkZXRhaWwgaW4gZmFpbHM6CiAgICBwcmludChmIiAgRkFJTCAge25hbWV9ICB7ZGV0YWlsfSIpCnN5cy5leGl0KDAgaWYgbm90IGZhaWxzIGVsc2UgMSkK"
).decode("utf-8")


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
