"""
Pending 写入状态存储（阶段三）。

借鉴 MemoraX 的交付状态语义：accepted → persisted / failed。
失败后保留原始内容与来源身份，允许同一 Turn 重试；
重启通过扫描未完成项恢复，不依赖内存态。
"""

import json
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4


@dataclass
class PendingWrite:
    pending_id: str
    content: str
    memory_type: str
    title: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    idem_key: str = ""
    status: str = "accepted"       # accepted / persisted / failed
    attempts: int = 0
    created_at: str = ""
    last_error: str = ""
    next_retry_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PendingWrite":
        fields = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in data.items() if k in fields})


def is_retryable_error(exc: Exception) -> bool:
    """区分可重试的传输/临时故障与不可重试的参数/校验错误。"""
    if isinstance(exc, (OSError, ConnectionError, TimeoutError)):
        return True
    if isinstance(exc, (ValueError, TypeError, KeyError)):
        return False
    message = str(exc).lower()
    return any(
        token in message
        for token in ("503", "502", "504", "timeout", "temporarily", "unavailable")
    )


class PendingStore:
    """<storage_path>/pending.json 的线程安全持久化存储。"""

    def __init__(self, storage_path: str):
        self.path = Path(storage_path) / "pending.json"
        self._lock = threading.Lock()
        self._items: Dict[str, PendingWrite] = self._load()

    def add(
        self,
        content: str,
        memory_type: str,
        title: str,
        metadata: Dict[str, Any] | None = None,
        idem_key: str = "",
    ) -> str:
        pid = f"pending_{uuid4().hex[:12]}"
        item = PendingWrite(
            pending_id=pid,
            content=content,
            memory_type=memory_type,
            title=title,
            metadata=dict(metadata or {}),
            idem_key=idem_key,
            created_at=datetime.utcnow().isoformat(),
        )
        with self._lock:
            self._items[pid] = item
            self._save_locked()
        return pid

    def get(self, pending_id: str) -> PendingWrite | None:
        return self._items.get(pending_id)

    def mark_persisted(self, pending_id: str) -> None:
        with self._lock:
            item = self._items.get(pending_id)
            if item:
                item.status = "persisted"
                self._save_locked()

    def mark_failed(self, pending_id: str, error: str, next_retry_at: float) -> None:
        with self._lock:
            item = self._items.get(pending_id)
            if item:
                item.status = "failed"
                item.attempts += 1
                item.last_error = str(error)[:500]
                item.next_retry_at = next_retry_at
                self._save_locked()

    def list_retryable(self, now: float | None = None) -> List[PendingWrite]:
        now = time.time() if now is None else now
        return [
            item for item in self._items.values()
            if item.status in ("accepted", "failed")
            and item.next_retry_at <= now
        ]

    def all(self) -> List[PendingWrite]:
        return list(self._items.values())

    def remove(self, pending_id: str) -> None:
        with self._lock:
            if pending_id in self._items:
                del self._items[pending_id]
                self._save_locked()

    def _load(self) -> Dict[str, PendingWrite]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return {
                key: PendingWrite.from_dict(value)
                for key, value in data.items()
            }
        except (OSError, ValueError, TypeError):
            return {}

    def _save_locked(self) -> None:
        # 只保留未完成项，persisted 项无需长期占用文件
        active = {
            k: v.to_dict() for k, v in self._items.items()
            if v.status != "persisted"
        }
        self._items = {
            k: v for k, v in self._items.items() if v.status != "persisted"
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(active, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)
