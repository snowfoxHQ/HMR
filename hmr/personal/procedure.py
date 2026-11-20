"""
Procedure Memory - 可复用流程与检查清单。

借鉴 MemoraX Code 的逐主题 Markdown 文件模型：
- 每个主题一个 kebab-case 文件，无全局索引/语义索引/事件日志
- 直接读文件 + 字符预算截断，不做 embedding 或 rerank
"""

import re
from pathlib import Path
from typing import List

MAX_TOPIC_FILES = 20
MAX_TOPIC_CHARS = 16 * 1024
DEFAULT_CONTEXT_CHARS = 4000


class ProcedureStore:
    """管理 <home>/personal-memory/procedure-memory/<topic>.md。"""

    def __init__(self, home: str):
        self.dir = Path(home) / "personal-memory" / "procedure-memory"

    @staticmethod
    def _valid_topic(topic: str) -> str:
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", topic):
            raise ValueError("topic 必须是 kebab-case（小写字母、数字、连字符）")
        return topic

    def list_topics(self, max_files: int = MAX_TOPIC_FILES) -> List[str]:
        if not self.dir.exists():
            return []
        return sorted(
            p.stem for p in self.dir.glob("*.md") if p.is_file()
        )[:max_files]

    def read_topic(self, topic: str, max_chars: int = MAX_TOPIC_CHARS) -> str:
        self._valid_topic(topic)
        path = self.dir / f"{topic}.md"
        if not path.exists():
            return ""
        text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        if len(text) > max_chars:
            text = text[:max_chars] + "\n[truncated]"
        return text

    def write_topic(
        self,
        topic: str,
        title: str,
        use_when: str,
        steps: List[str],
        exceptions: List[str] | None = None,
    ) -> Path:
        self._valid_topic(topic)
        self.dir.mkdir(parents=True, exist_ok=True)
        lines = [f"# {title.strip()}", "", f"Use when: {use_when.strip()}", "", "## Procedure", ""]
        lines.extend(f"{i}. {step.strip()}" for i, step in enumerate(steps, 1))
        lines.extend(["", "## Exceptions", ""])
        lines.extend(f"- {item.strip()}" for item in (exceptions or []))
        if not exceptions:
            lines.append("- None")
        path = self.dir / f"{topic}.md"
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        return path

    def build_context(self, max_chars: int = DEFAULT_CONTEXT_CHARS) -> str:
        """拼接全部可信主题文件，按总字符预算截断。"""
        parts: List[str] = []
        used = 0
        for topic in self.list_topics():
            text = self.read_topic(topic).strip()
            if not text:
                continue
            if used + len(text) > max_chars:
                remaining = max_chars - used
                if remaining > 40:
                    parts.append(text[:remaining] + "\n[truncated]")
                break
            parts.append(text)
            used += len(text)
        return "\n\n---\n\n".join(parts)
