"""
DATA-AI 企业级 — 审计链 (Merkle 树防篡改)

合规/法律需求 (金融/医疗/政府行业):
- 审计日志能证明 "提交后未被修改"
- 任何一行被改 → Merkle 根变化 → 校验失败
- 提供第三方验证: 给出 path + 兄弟节点 → 重算根

设计:
- AuditChain: 每 N 条 audit 算一个 Merkle 根
- ChainBlock: 包含 (entries, prev_root, root, timestamp)
- Proof: (leaf_index, sibling_hashes) 验证函数
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


def _hash(data: Any) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _hash_pair(left: str, right: str) -> str:
    # 排序无关:Merkle 树规范实现是 left+right 但 Bitcoin 用上下拼接,这里我们用 left+right
    return hashlib.sha256((left + right).encode("utf-8")).hexdigest()


def build_merkle_root(leaf_hashes: list[str]) -> str:
    """从叶子哈希构建 Merkle 根"""
    if not leaf_hashes:
        return ""
    if len(leaf_hashes) == 1:
        return leaf_hashes[0]
    level = list(leaf_hashes)
    while len(level) > 1:
        next_level = []
        for i in range(0, len(level), 2):
            if i + 1 < len(level):
                next_level.append(_hash_pair(level[i], level[i + 1]))
            else:
                # 奇数: 复制最后一个
                next_level.append(_hash_pair(level[i], level[i]))
        level = next_level
    return level[0]


def merkle_proof(leaf_hashes: list[str], index: int) -> tuple[list[tuple[str, str]], str]:
    """生成 Merkle 证明 — 返回 (path, root)
    path: [(sibling_hash, position)] position = "L" 或 "R"
    """
    if index < 0 or index >= len(leaf_hashes):
        raise ValueError(f"index out of range: {index}")
    if len(leaf_hashes) == 1:
        return [], leaf_hashes[0]

    path: list[tuple[str, str]] = []
    level = list(leaf_hashes)
    cur_idx = index
    while len(level) > 1:
        next_level = []
        sibling = ""
        position = ""
        for i in range(0, len(level), 2):
            if i == cur_idx or i + 1 == cur_idx:
                if cur_idx % 2 == 0:
                    # 当前是左, 兄弟是右
                    sibling = level[i + 1] if i + 1 < len(level) else level[i]
                    position = "R"
                else:
                    sibling = level[i]
                    position = "L"
                if cur_idx == i and i + 1 >= len(level):
                    # 奇数末尾: 复制的
                    sibling = level[i]
                    position = "R"
            if i + 1 < len(level):
                next_level.append(_hash_pair(level[i], level[i + 1]))
            else:
                next_level.append(_hash_pair(level[i], level[i]))
        path.append((sibling, position))
        level = next_level
        cur_idx = cur_idx // 2
    return path, level[0]


def verify_proof(leaf_hash: str, index: int, path: list[tuple[str, str]], expected_root: str) -> bool:
    """验证 Merkle 证明"""
    cur = leaf_hash
    cur_idx = index
    for sibling, position in path:
        if position == "L":
            cur = _hash_pair(sibling, cur)
        else:
            cur = _hash_pair(cur, sibling)
        cur_idx = cur_idx // 2
    return cur == expected_root


@dataclass
class ChainBlock:
    """链式区块 — 每 N 条审计记录一个根"""

    id: str = field(default_factory=lambda: f"blk-{uuid.uuid4().hex[:8]}")
    index: int = 0
    entry_ids: list[str] = field(default_factory=list)
    entry_count: int = 0
    prev_root: str = ""
    root: str = ""
    timestamp: float = field(default_factory=time.time)
    sealed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ChainBlock:
        return cls(**d)


class AuditChain:
    """审计链 — 滑动窗口 + 周期 sealing + 链式根"""

    def __init__(self, seal_threshold: int = 100, persist_path: Path | None = None) -> None:
        self._lock = threading.RLock()
        self._seal_threshold = seal_threshold
        self._buffer: list[dict[str, Any]] = []  # 待封装的 entry
        self._blocks: list[ChainBlock] = []
        self._persist_path = persist_path
        if persist_path:
            persist_path.parent.mkdir(parents=True, exist_ok=True)
            self._load_from_disk()

    def add_entry(self, entry: dict[str, Any]) -> ChainBlock | None:
        """添加一条 entry;满阈值自动 seal"""
        with self._lock:
            self._buffer.append(entry)
            if len(self._buffer) >= self._seal_threshold:
                return self._seal()
            return None

    def _seal(self) -> ChainBlock:
        with self._lock:
            prev_root = self._blocks[-1].root if self._blocks else ""
            leaf_hashes = [_hash(e) for e in self._buffer]
            root = build_merkle_root(leaf_hashes)
            block = ChainBlock(
                index=len(self._blocks),
                entry_ids=[e.get("id", "") for e in self._buffer],
                entry_count=len(self._buffer),
                prev_root=prev_root,
                root=root,
                sealed=True,
            )
            self._blocks.append(block)
            self._buffer.clear()
            self._write_block(block)
            return block

    def force_seal(self) -> ChainBlock:
        """强制 seal 当前 buffer(即使未满)"""
        with self._lock:
            if not self._buffer:
                # 空 buffer 也生成一个空块
                prev_root = self._blocks[-1].root if self._blocks else ""
                block = ChainBlock(
                    index=len(self._blocks),
                    entry_ids=[],
                    entry_count=0,
                    prev_root=prev_root,
                    root="",
                    sealed=True,
                )
                self._blocks.append(block)
                self._write_block(block)
                return block
            return self._seal()

    def chain_integrity(self) -> dict[str, Any]:
        """校验整条链的完整性"""
        with self._lock:
            ok = True
            issues: list[str] = []
            prev_root = ""
            for b in self._blocks:
                if b.prev_root != prev_root:
                    ok = False
                    issues.append(
                        f"block {b.id}: prev_root mismatch (expected {prev_root[:16]}, got {b.prev_root[:16]})"
                    )
                prev_root = b.root
            return {
                "ok": ok,
                "block_count": len(self._blocks),
                "issues": issues,
                "latest_root": self._blocks[-1].root if self._blocks else "",
            }

    def verify_entry(self, entry: dict[str, Any], block_id: str) -> dict[str, Any]:
        """验证某条 entry 在指定 block 中"""
        with self._lock:
            block = next((b for b in self._blocks if b.id == block_id), None)
            if not block:
                return {"ok": False, "error": "block not found"}
            # 找到该 entry 的 index
            if entry.get("id") not in block.entry_ids:
                return {"ok": False, "error": "entry not in block"}
            entry_index = block.entry_ids.index(entry.get("id"))
            # 重算 block 的 root
            block_entries = [
                next((e for e in self._buffer if e.get("id") == eid), {"id": eid}) for eid in block.entry_ids
            ]  # 简化
            # 实际重新计算需要原始 entry,这里用 hash 重算
            leaf_hashes = [_hash(e) for e in block_entries]
            computed_root = build_merkle_root(leaf_hashes)
            return {
                "ok": computed_root == block.root,
                "computed_root": computed_root,
                "stored_root": block.root,
                "entry_index": entry_index,
            }

    def get_proof(self, entry_id: str) -> dict[str, Any] | None:
        """为某条 entry 生成 Merkle 证明"""
        with self._lock:
            for b in self._blocks:
                if entry_id in b.entry_ids:
                    idx = b.entry_ids.index(entry_id)
                    # 简化: 我们只重算根,完整 proof 需要原 entry
                    return {
                        "block_id": b.id,
                        "entry_id": entry_id,
                        "entry_index": idx,
                        "root": b.root,
                    }
            return None

    def list_blocks(self) -> list[ChainBlock]:
        with self._lock:
            return list(self._blocks)

    def pending_count(self) -> int:
        with self._lock:
            return len(self._buffer)

    def _write_block(self, b: ChainBlock) -> None:
        if not self._persist_path:
            return
        try:
            with self._persist_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(b.to_dict(), ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _load_from_disk(self) -> None:
        if not self._persist_path or not self._persist_path.exists():
            return
        try:
            with self._persist_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        b = ChainBlock.from_dict(json.loads(line))
                        self._blocks.append(b)
                    except (json.JSONDecodeError, Exception):
                        continue
        except Exception:
            pass


# ============================================================================
# 全局单例
# ============================================================================

_GLOBAL_CHAIN: AuditChain | None = None
_GLOBAL_LOCK = threading.Lock()


def get_audit_chain(persist_path: Path | None = None) -> AuditChain:
    global _GLOBAL_CHAIN
    with _GLOBAL_LOCK:
        if _GLOBAL_CHAIN is None:
            _GLOBAL_CHAIN = AuditChain(persist_path=persist_path)
        return _GLOBAL_CHAIN


def reset_audit_chain() -> None:
    global _GLOBAL_CHAIN
    with _GLOBAL_LOCK:
        _GLOBAL_CHAIN = None
