from __future__ import annotations

import json
import re


_THINK_BLOCK_RE = re.compile(
    r"<(?P<tag>think|thought)>\s*.*?\s*</(?P=tag)>",
    flags=re.IGNORECASE | re.DOTALL,
)
_THINK_TOKEN_RE = re.compile(r"<\|[^>]*think[^>]*\|>", flags=re.IGNORECASE)
_THINK_LINE_RE = re.compile(r"^\s*(thinking|thought):.*$", flags=re.IGNORECASE)
_FINAL_TAG_RE = re.compile(
    r"<(?P<tag>final|final_answer)>\s*(?P<text>.*?)\s*</(?P=tag)>",
    flags=re.IGNORECASE | re.DOTALL,
)
_QUOTED_BLOCK_RE = re.compile(r'["«“](?P<text>[^"»”]{20,})["»”]')
_TERMINAL_DOT_WITH_CLOSERS_RE = re.compile(r"^(?P<body>.*)\.(?P<closers>[\*\"'»”]+)$", flags=re.DOTALL)
_META_LINE_PREFIXES = (
    "role:",
    "style:",
    "tone:",
    "voice:",
    "goal:",
    "constraint:",
    "user input:",
    "persona:",
    "mission:",
    "topic:",
    "intent:",
    "method:",
    "text:",
    "draft",
    "refining",
    "acknowledge",
    "create",
    "ask ",
    "final answer:",
    "response:",
    "reply:",
    "роль:",
    "стиль:",
    "цель:",
    "ограничение:",
    "ввод пользователя:",
    "персона:",
    "миссия:",
    "тема:",
    "метод:",
    "черновик",
    "ответ:",
    "текст:",
)
_META_LINE_CONTAINS = (
    "internal monologue",
    "constraint check",
    "draft ",
    "drafting",
    "refining into",
    "role:",
    "style:",
    "goal:",
    "user input:",
    "persona:",
    "mission:",
    "method:",
)
_YES_NO_META_RE = re.compile(
    r"^\s*[*\-]?\s*[A-Za-zА-Яа-я][^?\n]{0,80}\?\s*(yes|no|да|нет)\.?\s*$",
    flags=re.IGNORECASE,
)


def sanitize_model_text(text: str) -> str:
    sanitized = _THINK_BLOCK_RE.sub("", text)
    sanitized = _THINK_TOKEN_RE.sub("", sanitized)

    cleaned_lines: list[str] = []
    for line in sanitized.splitlines():
        if _THINK_LINE_RE.match(line):
            continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines).strip()


def extract_final_model_reply(text: str) -> str:
    sanitized = sanitize_model_text(text).strip()
    if sanitized == "":
        return ""

    tagged = _extract_tagged_final(sanitized)
    if tagged:
        return tagged

    json_reply = _extract_json_final(sanitized)
    if json_reply:
        return json_reply

    filtered = _strip_meta_lines(sanitized)
    if filtered:
        quoted = _extract_last_quoted_block(filtered)
        if quoted:
            return quoted
        return filtered

    single_wrapped = _extract_single_wrapped_block(sanitized)
    if single_wrapped:
        return single_wrapped

    return sanitized


def normalize_ui_text(text: str) -> str:
    normalized = extract_final_model_reply(text).strip()
    if normalized.endswith("."):
        normalized = normalized[:-1].rstrip()
    else:
        match = _TERMINAL_DOT_WITH_CLOSERS_RE.match(normalized)
        if match is not None:
            normalized = f"{match.group('body').rstrip()}{match.group('closers')}"
    return normalized


def _extract_tagged_final(text: str) -> str:
    matches = list(_FINAL_TAG_RE.finditer(text))
    if not matches:
        return ""
    return sanitize_model_text(matches[-1].group("text")).strip()


def _extract_json_final(text: str) -> str:
    try:
        payload = json.loads(text)
    except ValueError:
        return ""
    if not isinstance(payload, dict):
        return ""
    for key in ("final_answer", "final", "reply", "text", "message"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return sanitize_model_text(value).strip()
    return ""


def _strip_meta_lines(text: str) -> str:
    candidate_lines: list[str] = []
    removed_meta = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line == "":
            if candidate_lines and candidate_lines[-1] != "":
                candidate_lines.append("")
            continue
        if _is_meta_line(line):
            removed_meta = True
            continue
        if removed_meta and _looks_like_non_user_facing_english_line(line):
            continue
        candidate_lines.append(line)

    if not removed_meta:
        return ""

    paragraphs: list[str] = []
    current: list[str] = []
    for line in candidate_lines:
        if line == "":
            if current:
                paragraphs.append(" ".join(current).strip())
                current = []
            continue
        normalized_line = _strip_wrapping_quotes(line)
        if current and current[-1].casefold() == normalized_line.casefold():
            continue
        current.append(normalized_line)
    if current:
        paragraphs.append(" ".join(current).strip())

    deduped: list[str] = []
    seen_normalized: set[str] = set()
    for paragraph in paragraphs:
        normalized_paragraph = paragraph.strip()
        if normalized_paragraph == "":
            continue
        comparable = normalized_paragraph.casefold()
        if comparable in seen_normalized:
            continue
        seen_normalized.add(comparable)
        deduped.append(normalized_paragraph)

    return "\n\n".join(deduped).strip()


def _is_meta_line(line: str) -> bool:
    lowered = line.casefold()
    plain = lowered.lstrip("*- ").strip()

    if _YES_NO_META_RE.match(line):
        return True
    if any(plain.startswith(prefix) for prefix in _META_LINE_PREFIXES):
        return True
    if any(fragment in plain for fragment in _META_LINE_CONTAINS):
        return True
    if plain.startswith("*draft") or plain.startswith("draft "):
        return True
    if plain.startswith('"') and plain.endswith('"') and _looks_like_instruction_dump(plain):
        return True
    return False


def _extract_last_quoted_block(text: str) -> str:
    matches = list(_QUOTED_BLOCK_RE.finditer(text))
    if not matches:
        return ""
    return sanitize_model_text(matches[-1].group("text")).strip()


def _extract_single_wrapped_block(text: str) -> str:
    stripped = text.strip()
    if len(stripped) < 2:
        return ""
    if (stripped[0], stripped[-1]) not in {('"', '"'), ("«", "»"), ("“", "”")}:
        return ""
    inner = _strip_wrapping_quotes(stripped)
    if inner == "":
        return ""
    return sanitize_model_text(inner).strip()


def _strip_wrapping_quotes(line: str) -> str:
    stripped = line.strip()
    if len(stripped) >= 2 and (
        (stripped[0], stripped[-1]) in {('"', '"'), ("«", "»"), ("“", "”")}
    ):
        return stripped[1:-1].strip()
    return stripped


def _looks_like_instruction_dump(text: str) -> bool:
    lowered = text.casefold()
    return any(fragment in lowered for fragment in _META_LINE_CONTAINS)


def _looks_like_non_user_facing_english_line(text: str) -> bool:
    has_cyrillic = bool(re.search(r"[А-Яа-яЁё]", text))
    has_latin = bool(re.search(r"[A-Za-z]", text))
    if has_cyrillic or not has_latin:
        return False
    return True
