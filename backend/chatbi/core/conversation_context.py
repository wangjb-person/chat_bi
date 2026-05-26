"""
多轮对话上下文：截断、历史裁剪、分析上下文拼装。

问句补全由 application.query_understanding.QueryUnderstandingService（LLM）负责。
"""

from __future__ import annotations

from typing import Dict, List, Optional

MAX_CONTEXT_MESSAGES = 20
MAX_MESSAGE_CHARS = 2000
MAX_ANALYSIS_CONTEXT_CHARS = 3000

_ROLE_LABELS: Dict[str, str] = {"user": "用户", "assistant": "助手"}
_VALID_ROLES = frozenset(_ROLE_LABELS)


def truncate_text(text: str, *, max_len: int = MAX_MESSAGE_CHARS) -> str:
    t = (text or "").strip()
    return t if len(t) <= max_len else f"{t[: max_len - 1]}…"


def trim_messages(
    messages: Optional[List[Dict[str, str]]],
    *,
    max_messages: int = MAX_CONTEXT_MESSAGES,
    max_chars: int = MAX_MESSAGE_CHARS,
) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for item in messages or []:
        role = item.get("role")
        content = truncate_text(item.get("content") or "", max_len=max_chars)
        if role in _VALID_ROLES and content:
            out.append({"role": role, "content": content})
    return out[-max_messages:]


def prior_history(
    messages: Optional[List[Dict[str, str]]], current_question: str
) -> Optional[List[Dict[str, str]]]:
    """去掉与当前问题重复的末尾 user，供 LLM 理解/对话 prompt 使用。"""
    trimmed = trim_messages(messages)
    if not trimmed:
        return None
    last = trimmed[-1]
    q = current_question.strip()
    trimmed = (
        trimmed[:-1]
        if last["role"] == "user" and last["content"] == q
        else trimmed
    )
    return trimmed or None


def format_dialogue_block(prior: List[Dict[str, str]]) -> str:
    return "\n".join(
        f"{_ROLE_LABELS[m['role']]}：{m['content']}"
        for m in prior
        if m["role"] in _VALID_ROLES
    )


def format_history_for_llm_classifier(
    messages: Optional[List[Dict[str, str]]], current_question: str
) -> str:
    prior = prior_history(messages, current_question)
    return format_dialogue_block(prior[-6:]) if prior else ""


def build_analysis_context(
    messages: Optional[List[Dict[str, str]]], current_question: str
) -> str:
    prior = prior_history(messages, current_question)
    if not prior:
        return ""
    return truncate_text(
        format_dialogue_block(prior[-8:]), max_len=MAX_ANALYSIS_CONTEXT_CHARS
    )
