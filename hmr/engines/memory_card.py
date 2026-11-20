"""
CODE_AGENT_MEMORY 结构化记忆卡引擎。

借鉴 MemoraX Code 的紧凑记忆卡（11 字段）与「已验证才存正面经验」门槛：
- 正面经验（status=verified）必须带 validation，且 signal 不能是 unknown
- 失败教训（status=failed_attempt）必须写清 failed_shape
- 卡片保留原文本入库，同时拆成结构化 metadata 供检索/过滤

不依赖 LLM、不依赖外部服务，纯文本解析。
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MemoryCard:
    repo: str = ""
    scope: str = ""
    status: str = "candidate"
    signal: str = ""
    problem: str = ""
    technical_context: str = ""
    surfaces: str = ""
    failed_shape: str = ""
    validation: str = ""
    principle: str = ""
    anchors: str = ""


@dataclass
class CardValidationResult:
    ok: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class MemoryCardEngine:
    """解析、校验与渲染 CODE_AGENT_MEMORY 卡片。"""

    PREFIX = "CODE_AGENT_MEMORY"
    FIELDS = (
        "repo", "scope", "status", "signal", "problem",
        "technical_context", "surfaces", "failed_shape",
        "validation", "principle", "anchors",
    )
    VALID_STATUSES = ("verified", "failed_attempt", "candidate")
    MAX_CARD_CHARS = 1100

    def is_card(self, text: str) -> bool:
        if not text:
            return False
        first = text.lstrip().splitlines()[0].strip()
        return first == self.PREFIX

    def parse(self, text: str) -> Optional[MemoryCard]:
        """解析卡片文本；非卡片或语法错误返回 None。"""
        if not self.is_card(text):
            return None
        values: Dict[str, str] = {}
        for line in text.lstrip().splitlines()[1:]:
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip()
            if key in self.FIELDS:
                values[key] = value.strip()
        if not any(values.values()):
            return None
        return MemoryCard(**{k: values.get(k, "") for k in self.FIELDS})

    def render(self, card: MemoryCard) -> str:
        lines = [self.PREFIX]
        for key in self.FIELDS:
            lines.append(f"{key}: {getattr(card, key, '')}")
        return "\n".join(lines)

    def validate(self, card: MemoryCard) -> CardValidationResult:
        """应用 MemoraX 验证门槛：未验证的正面经验不得入库。"""
        errors: List[str] = []
        warnings: List[str] = []

        if card.status not in self.VALID_STATUSES:
            errors.append(
                f"status 必须是 {', '.join(self.VALID_STATUSES)} 之一，当前={card.status!r}"
            )

        if card.status == "verified":
            if not card.validation:
                errors.append("status=verified 必须填写 validation（已验证门槛）")
            signal = card.signal.strip().lower()
            if not signal or "unknown" in signal:
                errors.append("status=verified 必须填写明确的 signal（不能是 unknown）")

        if card.status == "failed_attempt" and not card.failed_shape:
            errors.append("status=failed_attempt 必须填写 failed_shape（错在哪）")

        if not card.problem:
            errors.append("problem 不能为空")
        if not card.principle:
            warnings.append("principle 为空，后续检索的可迁移性较弱")
        if not card.anchors:
            warnings.append("anchors 为空，缺少可核对的源码/测试锚点")

        if len(self.render(card)) > self.MAX_CARD_CHARS:
            warnings.append(f"卡片超过 {self.MAX_CARD_CHARS} 字符，建议精简")

        return CardValidationResult(ok=not errors, errors=errors, warnings=warnings)

    def to_memory_kwargs(self, card: MemoryCard) -> Dict[str, Any]:
        """把卡片转换为 HMR.ingest 的参数。

        注意：卡片里的 scope 是技术范围（module::symbol），与 HMR 的
        project/user/global 作用域语义不同，因此放到 metadata['card_scope']。
        """
        evidence = [
            v for v in (card.validation, card.anchors, card.signal)
            if v and v.lower() != "none"
        ]
        title = (card.problem or card.principle or card.technical_context or "coding memory")[:80]
        return {
            "content": self.render(card),
            "title": title,
            "memory_type": "reflection" if card.status != "candidate" else "concept",
            "boundary": "coding",
            "metadata": {
                "source": "code_agent_card",
                "status": card.status,
                "evidence": evidence,
                "card": asdict(card),
                "card_scope": card.scope,
                "repo": card.repo,
            },
        }
