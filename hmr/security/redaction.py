"""
写入前敏感信息脱敏。

借鉴 MemoraX 的 payload redaction 测试关注点：
- 多类敏感信息（私钥、API key、token、cookie、凭据）
- 重叠匹配：先收集区间再一次性替换，避免二次替换错位
- 幂等：脱敏占位符本身不再匹配任何规则
- 截断边界：先脱敏再截断，避免密钥残片随截断泄漏
"""

import re
from typing import List, Tuple

# (pattern, replacement)；replacement 为 None 时只替换捕获组 2（值）
SENSITIVE_PATTERNS = [
    (
        re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----[\s\S]*?-----END (?:[A-Z ]+ )?PRIVATE KEY-----"),
        "[REDACTED_PRIVATE_KEY]",
    ),
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}"), "[REDACTED_API_KEY]"),
    (re.compile(r"\bBearer\s+[A-Za-z0-9._\-]{10,}", re.I), "Bearer [REDACTED_TOKEN]"),
    (re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}"), "[REDACTED_TOKEN]"),
    (
        re.compile(
            r"\b(api[_-]?key|access[_-]?token|auth[_-]?token|secret|password|authorization|cookie)"
            r"(\s*[:=]\s*)(['\"]?)([^\s'\",;}\]]+)\3",
            re.I,
        ),
        None,
    ),
]

REDACTED = "[REDACTED]"


def redact_sensitive_text(text: str) -> str:
    """脱敏文本中的敏感片段；对已脱敏文本幂等。"""
    if not text:
        return text
    spans: List[Tuple[int, int, str]] = []
    for pattern, replacement in SENSITIVE_PATTERNS:
        for match in pattern.finditer(text):
            if replacement is None:
                start, end = match.start(4), match.end(4)
                value = REDACTED
            else:
                start, end = match.start(), match.end()
                value = replacement
            if start < end:
                spans.append((start, end, value))

    if not spans:
        return text

    # 合并重叠区间，保留更长者；避免二次替换导致偏移错乱
    spans.sort(key=lambda s: (s[0], -(s[1] - s[0])))
    merged: List[List] = []
    for start, end, value in spans:
        if merged and start < merged[-1][1]:
            if end - start > merged[-1][1] - merged[-1][0]:
                merged[-1] = [start, end, value]
        else:
            merged.append([start, end, value])

    parts: List[str] = []
    cursor = 0
    for start, end, value in merged:
        parts.append(text[cursor:start])
        parts.append(value)
        cursor = end
    parts.append(text[cursor:])
    return "".join(parts)


def redact_content(text: str, max_chars: int | None = None) -> str:
    """写入前脱敏；max_chars 存在时先脱敏再截断。"""
    if text is None:
        return ""
    redacted = redact_sensitive_text(str(text))
    if max_chars is not None and len(redacted) > max_chars:
        return redacted[:max_chars] + "[truncated]"
    return redacted
