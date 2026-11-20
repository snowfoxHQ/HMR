"""
User Profile Memory - 用户画像与协作偏好。

借鉴 MemoraX Code 的严格 frontmatter schema、精确去重、状态过滤与原子写：
- 条目数不符时抛错，而不是静默加载残缺画像
- 等价内容不重复写；细化/冲突由调用方判断后更新同一条目
- 不写 tombstone、backup 或 history
"""

import os
import re
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from uuid import uuid4


SCHEMA = "user_profile_memory.v0.1"
OWNER = "user-profile-memory"
TRUST_STATE = "user_stated"
PREFERENCE_TYPES = ("communication", "workflow", "environment", "profile")
MAX_PREFERENCES_BYTES = 64 * 1024


class ProfileStorageError(ValueError):
    """用户画像文件结构不合法。"""


@dataclass
class Preference:
    id: str
    type: str
    description: str
    applies_when: str = "-"
    do_not_apply_when: str = "-"
    created: str = ""
    updated: str = ""
    confidence: str = "user_stated"
    status: str = "active"


def _normalize(value: str) -> str:
    return " ".join((value or "").split()).casefold()


def _scope_key(value: str) -> str:
    key = _normalize(value)
    return "" if key in ("", "-") else key


class UserProfileStore:
    """管理 <home>/personal-memory/user-profile/preferences.md。"""

    def __init__(self, home: str):
        self.home = Path(home)
        self.path = self.home / "personal-memory" / "user-profile" / "preferences.md"
        self._lock = threading.Lock()

    # ── 读取 ────────────────────────────────────────────────────────────────

    def read(self) -> List[Preference]:
        if not self.path.exists():
            return []
        if self.path.stat().st_size > MAX_PREFERENCES_BYTES:
            raise ProfileStorageError("preferences.md 超过大小上限")
        text = self.path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
        meta = self._parse_frontmatter(text)
        expected = {
            "schema": SCHEMA, "scope": "user",
            "owner": OWNER, "trust_state": TRUST_STATE,
        }
        for key, value in expected.items():
            if meta.get(key) != value:
                raise ProfileStorageError(f"frontmatter {key} 不匹配：{meta.get(key)!r}")
        try:
            total = int(meta["total_count"])
            active = int(meta["active_count"])
        except (KeyError, ValueError) as exc:
            raise ProfileStorageError("active_count/total_count 缺失或非法") from exc

        matches = list(re.finditer(r"^## Preference (pref_[^\s]+)\s*$", text, re.M))
        if len(matches) != total:
            raise ProfileStorageError(
                f"total_count={total} 与实际条目数 {len(matches)} 不符"
            )

        entries: List[Preference] = []
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            block = text[match.end():end]
            status = self._field(block, "Status")
            ptype = self._field(block, "Type")
            if status not in ("active", "superseded", "deleted"):
                raise ProfileStorageError(f"未知 status: {status!r}")
            if ptype not in PREFERENCE_TYPES:
                raise ProfileStorageError(f"未知 type: {ptype!r}")
            if status != "active":
                continue
            description = self._normalize_field(self._field(block, "Description"))
            if not description:
                raise ProfileStorageError("active 偏好缺少 Description")
            entries.append(Preference(
                id=match.group(1),
                type=ptype,
                description=description,
                applies_when=self._normalize_field(self._field(block, "Applies when")),
                do_not_apply_when=self._normalize_field(self._field(block, "Do not apply when")),
                created=self._field(block, "Created"),
                updated=self._field(block, "Updated"),
                confidence=self._field(block, "Confidence") or "user_stated",
                status=status,
            ))

        if len(entries) != active:
            raise ProfileStorageError(
                f"active_count={active} 与实际 active 条目数 {len(entries)} 不符"
            )
        return entries

    @staticmethod
    def _parse_frontmatter(text: str) -> Dict[str, str]:
        match = re.match(r"^---\n([\s\S]*?)\n---(?:\n|$)", text)
        if not match:
            raise ProfileStorageError("缺少 frontmatter")
        meta: Dict[str, str] = {}
        for line in match.group(1).splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" not in line:
                raise ProfileStorageError(f"frontmatter 行非法: {line!r}")
            key, value = line.split(":", 1)
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
                value = value[1:-1]
            meta[key.strip()] = value
        return meta

    @staticmethod
    def _field(block: str, name: str) -> str:
        escaped = re.escape(name)
        match = re.search(rf"^- {escaped}: ?(.*)$", block, re.M)
        return match.group(1).strip().strip("`") if match else ""

    @staticmethod
    def _normalize_field(value: str) -> str:
        value = (value or "").strip()
        return "" if value == "-" else value

    # ── 写入 ────────────────────────────────────────────────────────────────

    def add(
        self,
        ptype: str,
        description: str,
        applies_when: str = "-",
        do_not_apply_when: str = "-",
    ) -> Tuple[str, str]:
        """返回 (status, id)，status ∈ added/duplicate。"""
        if ptype not in PREFERENCE_TYPES:
            raise ProfileStorageError(f"未知 type: {ptype!r}")
        if not _normalize(description):
            raise ProfileStorageError("description 不能为空")
        with self._lock:
            entries = self.read()
            key = (
                _normalize(description),
                _scope_key(applies_when),
                _scope_key(do_not_apply_when),
            )
            for entry in entries:
                existing = (
                    _normalize(entry.description),
                    _scope_key(entry.applies_when),
                    _scope_key(entry.do_not_apply_when),
                )
                if existing == key:
                    return "duplicate", entry.id
            now = datetime.utcnow().isoformat()
            pid = self._make_id(entries, ptype, now)
            entries.append(Preference(
                id=pid, type=ptype,
                description=" ".join(description.split()),
                applies_when=applies_when.strip() or "-",
                do_not_apply_when=do_not_apply_when.strip() or "-",
                created=now, updated=now,
            ))
            self._write(entries)
            return "added", pid

    def update(
        self,
        pid: str,
        description: Optional[str] = None,
        applies_when: Optional[str] = None,
        do_not_apply_when: Optional[str] = None,
    ) -> str:
        """细化或冲突替换：更新同一 id，不留旧文本。"""
        with self._lock:
            entries = self.read()
            found = False
            for entry in entries:
                if entry.id != pid:
                    continue
                found = True
                if description is not None:
                    if not _normalize(description):
                        raise ProfileStorageError("description 不能为空")
                    entry.description = " ".join(description.split())
                if applies_when is not None:
                    entry.applies_when = applies_when.strip() or "-"
                if do_not_apply_when is not None:
                    entry.do_not_apply_when = do_not_apply_when.strip() or "-"
                entry.updated = datetime.utcnow().isoformat()
            if not found:
                raise ProfileStorageError(f"偏好不存在: {pid}")
            self._write(entries)
            return "updated"

    def delete(self, pid: str) -> str:
        with self._lock:
            entries = self.read()
            remaining = [e for e in entries if e.id != pid]
            if len(remaining) == len(entries):
                raise ProfileStorageError(f"偏好不存在: {pid}")
            self._write(remaining)
            return "deleted"

    @staticmethod
    def _make_id(entries: List[Preference], ptype: str, timestamp: str) -> str:
        base = f"pref_{timestamp[:10].replace('-', '')}_{ptype}"
        existing = {e.id for e in entries}
        if base not in existing:
            return base
        counter = 2
        while f"{base}-{counter}" in existing:
            counter += 1
        return f"{base}-{counter}"

    def _write(self, entries: List[Preference]) -> None:
        lines = [
            "---",
            f'schema: "{SCHEMA}"',
            'scope: "user"',
            f'owner: "{OWNER}"',
            f'trust_state: "{TRUST_STATE}"',
            f'updated_at: "{datetime.utcnow().isoformat()}"',
            f"active_count: {len(entries)}",
            f"total_count: {len(entries)}",
            "---", "",
            "# User Profile And Preferences", "",
            "These preferences are global to the user. Current instructions override stored preferences.",
            "", "## Active Preferences", "",
        ]
        for entry in sorted(entries, key=lambda e: e.updated, reverse=True):
            lines.extend([
                f"## Preference {entry.id}", "",
                f"- Type: `{entry.type}`",
                "- Status: `active`",
                f"- Confidence: `{entry.confidence}`",
                f"- Created: `{entry.created}`",
                f"- Updated: `{entry.updated}`",
                f"- Description: {entry.description}",
                f"- Applies when: {entry.applies_when}",
                f"- Do not apply when: {entry.do_not_apply_when}",
                f"- Raw lookup: `preferenceId={entry.id}`", "",
            ])
        text = "\n".join(lines).rstrip() + "\n"
        if len(text.encode("utf-8")) > MAX_PREFERENCES_BYTES:
            raise ProfileStorageError("渲染后的 preferences.md 超过大小上限")

        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(f".{self.path.name}.{uuid4().hex}.tmp")
        try:
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, self.path)
        finally:
            if tmp.exists():
                tmp.unlink()
