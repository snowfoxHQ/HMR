"""
写入幂等去重（阶段二）。

边界：单 Runtime / 单 Backend 进程。多进程与远端全局幂等不在本层。
键由「来源 Turn 身份 + 入库内容指纹」构成，不按正文相同判重——
同一事实在不同 Turn 被再次确认时应当分别保留。
"""

import hashlib
import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


@dataclass
class IdempotencyRecord:
    key: str
    memory_id: str
    created_at: float


class IdempotencyStore:
    """带 TTL 与容量上限的幂等占位存储。"""

    def __init__(self, storage_path: str, ttl_seconds: int = 300, max_entries: int = 1024):
        self.path = Path(storage_path) / "idempotency.json"
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._lock = threading.Lock()
        self._records: Dict[str, IdempotencyRecord] = self._load()

    @staticmethod
    def make_key(source_turn_id: str, content: str) -> str:
        """无来源身份时不启用幂等，返回空串。"""
        if not source_turn_id:
            return ""
        payload = f"{source_turn_id}\0{content}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()[:32]

    def check_and_reserve(self, key: str) -> Optional[str]:
        """返回 None 表示首次（已占位）；返回 memory_id 表示重复提交。"""
        if not key:
            return None
        with self._lock:
            self._prune_locked()
            record = self._records.get(key)
            if record:
                return record.memory_id
            self._records[key] = IdempotencyRecord(key, "", time.time())
            self._prune_locked()
            self._save_locked()
            return None

    def mark(self, key: str, memory_id: str) -> None:
        """写入成功后绑定 memory_id。"""
        if not key:
            return
        with self._lock:
            record = self._records.get(key)
            if record:
                record.memory_id = memory_id
                self._save_locked()

    def release(self, key: str) -> None:
        """写入失败后释放占位，允许同一 Turn 重试。"""
        if not key:
            return
        with self._lock:
            if key in self._records:
                del self._records[key]
                self._save_locked()

    def _prune_locked(self) -> None:
        now = time.time()
        expired = [k for k, v in self._records.items() if now - v.created_at > self.ttl_seconds]
        for key in expired:
            del self._records[key]
        if len(self._records) > self.max_entries:
            newest = sorted(
                self._records.values(), key=lambda r: r.created_at, reverse=True
            )[:self.max_entries]
            self._records = {r.key: r for r in newest}

    def _load(self) -> Dict[str, IdempotencyRecord]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return {
                key: IdempotencyRecord(
                    key=key,
                    memory_id=str(value.get("memory_id", "")),
                    created_at=float(value.get("created_at", 0)),
                )
                for key, value in data.items()
            }
        except (OSError, ValueError, TypeError):
            return {}

    def _save_locked(self) -> None:
        data = {
            key: {"memory_id": r.memory_id, "created_at": r.created_at}
            for key, r in self._records.items()
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)
