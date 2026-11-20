"""
本地 Trace 存储 - JSONL 事件、event_id 去重、脱敏与保留期。

借鉴 MemoraX Code 的 trace 设计，但完全本地、零依赖：
- 事件按天分文件 events-YYYY-MM-DD.jsonl
- event_id 去重（内存有界集合 + 文件内查重）
- metadata-only 模式去掉内容；敏感键（token/secret/authorization...）脱敏
- 超过保留期的文件自动清理
- 所有写入失败由调用方吞掉，绝不影响记忆主链路
"""

import json
import os
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

SCHEMA_VERSION = "hmr_trace.v1"
SENSITIVE_KEYS = (
    "authorization", "api-key", "api_key", "apikey",
    "token", "secret", "password", "credential",
)
DEFAULT_MAX_EVENT_CHARS = 20000
DEFAULT_RETENTION_DAYS = 7
DEFAULT_MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_SEEN_IDS = 4096


@dataclass
class TraceEvent:
    schema_version: str = SCHEMA_VERSION
    event_id: str = ""
    type: str = "memory"
    timestamp: str = ""
    trace: str = ""
    source: str = "hmr"
    operation: str = ""
    ok: bool = True
    outcome: str = ""
    related_turns: List[str] = field(default_factory=list)
    activities: List[str] = field(default_factory=list)
    usage: Dict[str, Any] = field(default_factory=dict)
    request: Any = None
    response: Any = None
    error: Any = None


def sanitize_trace_value(value: Any, capture_content: bool = True, max_chars: int = DEFAULT_MAX_EVENT_CHARS):
    """脱敏并截断 trace 值。"""
    if not capture_content:
        return "[redacted]"
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if any(s in str(key).lower() for s in SENSITIVE_KEYS):
                out[key] = "[redacted]"
            else:
                out[key] = sanitize_trace_value(item, True, max_chars)
        return out
    if isinstance(value, (list, tuple)):
        return [sanitize_trace_value(v, True, max_chars) for v in value]
    if isinstance(value, str) and len(value) > max_chars:
        return value[:max_chars] + "[truncated]"
    return value


class TraceStore:
    """把 trace 事件写入本地 JSONL 文件。"""

    def __init__(
        self,
        base_path: str,
        enabled: bool = True,
        capture_content: bool = True,
        retention_days: int = DEFAULT_RETENTION_DAYS,
        max_event_chars: int = DEFAULT_MAX_EVENT_CHARS,
        max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    ):
        self.base_path = Path(base_path)
        self.enabled = enabled
        self.capture_content = capture_content
        self.retention_days = retention_days
        self.max_event_chars = max_event_chars
        self.max_file_bytes = max_file_bytes
        self._lock = threading.Lock()
        self._seen = set()
        if self.enabled:
            self.base_path.mkdir(parents=True, exist_ok=True)

    def emit(
        self,
        operation: str,
        *,
        event_id: Optional[str] = None,
        ok: bool = True,
        outcome: str = "",
        trace: str = "",
        source: str = "hmr",
        event_type: str = "memory",
        related_turns: Optional[List[str]] = None,
        activities: Optional[List[str]] = None,
        usage: Optional[Dict[str, Any]] = None,
        request: Any = None,
        response: Any = None,
        error: Any = None,
    ) -> Optional[str]:
        """写一条事件；返回 event_id。去重命中或禁用时返回 None。"""
        if not self.enabled:
            return None
        eid = event_id or uuid4().hex
        with self._lock:
            if eid in self._seen:
                return None
            self._seen.add(eid)
            if len(self._seen) > MAX_SEEN_IDS:
                self._seen = set(list(self._seen)[-MAX_SEEN_IDS // 2:])
            event = TraceEvent(
                event_id=eid,
                type=event_type,
                timestamp=datetime.utcnow().isoformat(),
                trace=trace,
                source=source,
                operation=operation,
                ok=ok,
                outcome=outcome,
                related_turns=related_turns or [],
                activities=activities or [],
                usage=usage or {},
                request=sanitize_trace_value(request, self.capture_content, self.max_event_chars),
                response=sanitize_trace_value(response, self.capture_content, self.max_event_chars),
                error=sanitize_trace_value(error, self.capture_content, self.max_event_chars),
            )
            line = json.dumps(asdict(event), ensure_ascii=False, default=str)
            if len(line) > self.max_event_chars:
                event.request = "[truncated]"
                event.response = "[truncated]"
                line = json.dumps(asdict(event), ensure_ascii=False, default=str)[:self.max_event_chars]
            self._prune_locked()
            target = self.base_path / f"events-{datetime.utcnow().strftime('%Y-%m-%d')}.jsonl"
            if target.exists() and target.stat().st_size > self.max_file_bytes:
                target = self.base_path / f"events-{datetime.utcnow().strftime('%Y-%m-%d')}-{uuid4().hex[:6]}.jsonl"
            with open(target, "a", encoding="utf-8") as handle:
                handle.write(line + "\n")
            return eid

    def read_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        """按时间倒序读取最近事件（用于诊断）。"""
        events: List[Dict[str, Any]] = []
        for path in sorted(self.base_path.glob("events*.jsonl"), reverse=True):
            if not path.exists():
                continue
            with open(path, "r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        events.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
        return events[:limit]

    def stats(self) -> Dict[str, Any]:
        events = self.read_events(limit=10000)
        by_operation: Dict[str, int] = {}
        failures = 0
        for event in events:
            op = event.get("operation", "unknown")
            by_operation[op] = by_operation.get(op, 0) + 1
            if not event.get("ok", True):
                failures += 1
        return {
            "enabled": self.enabled,
            "capture_content": self.capture_content,
            "retention_days": self.retention_days,
            "events": len(events),
            "failures": failures,
            "by_operation": by_operation,
        }

    def _prune_locked(self):
        cutoff = datetime.utcnow() - timedelta(days=self.retention_days)
        for path in self.base_path.glob("events*.jsonl"):
            try:
                mtime = datetime.fromtimestamp(path.stat().st_mtime)
                if mtime < cutoff:
                    path.unlink()
            except OSError:
                pass
