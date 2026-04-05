from __future__ import annotations

import re


_THINK_BLOCK_RE = re.compile(
    r"<(?P<tag>think|thought)>\s*.*?\s*</(?P=tag)>",
    flags=re.IGNORECASE | re.DOTALL,
)
_THINK_TOKEN_RE = re.compile(r"<\|[^>]*think[^>]*\|>", flags=re.IGNORECASE)
_THINK_LINE_RE = re.compile(r"^\s*(thinking|thought):.*$", flags=re.IGNORECASE)


def sanitize_model_text(text: str) -> str:
    sanitized = _THINK_BLOCK_RE.sub("", text)
    sanitized = _THINK_TOKEN_RE.sub("", sanitized)

    cleaned_lines: list[str] = []
    for line in sanitized.splitlines():
        if _THINK_LINE_RE.match(line):
            continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines).strip()


def normalize_ui_text(text: str) -> str:
    normalized = sanitize_model_text(text).strip()
    if normalized.endswith("."):
        normalized = normalized[:-1].rstrip()
    return normalized
