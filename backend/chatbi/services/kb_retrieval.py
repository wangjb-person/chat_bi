"""
知识库检索增强：扩大向量候选池 + 关键词重排 + 小库关键词补救。

解决长文档中「语义相近段」挤占 TopK、真正相关段（如「（二）工作时间」）进不了 Prompt 的问题。
"""

from __future__ import annotations

import re
from typing import Dict, List, Set, Tuple

# 问句中常见虚词，不参与关键词匹配
_STOP_TERMS = frozenset(
    {
        "什么",
        "怎么",
        "如何",
        "为什么",
        "哪些",
        "是否",
        "可以",
        "能否",
        "请问",
        "一下",
        "公司",
        "我们",
        "你们",
        "他们",
        "这个",
        "那个",
        "有没有",
        "是什么",
        "多少",
    }
)

_CHINESE_RUN = re.compile(r"[\u4e00-\u9fff]{2,}")
_ALNUM = re.compile(r"[A-Za-z0-9]{2,}")
# 问句切分：去掉虚词后再抽词，便于命中「的工作时间」→「工作时间」
_PARTICLE_SPLIT = re.compile(r"[的了吗呢啊呀么吧\s\?？!！,，;；、]+")


def _term_matches_text(term: str, text: str) -> bool:
    if term in text:
        return True
    if term.startswith("的") and len(term) > 1 and term[1:] in text:
        return True
    return False


def extract_query_terms(question: str, *, max_terms: int = 16) -> List[str]:
    """从问句提取检索关键词（中文片段 + 子串，去停用词）。"""
    q = (question or "").strip()
    if not q:
        return []

    terms: List[str] = []
    for segment in _PARTICLE_SPLIT.split(q):
        segment = segment.strip()
        if len(segment) >= 2 and segment not in _STOP_TERMS:
            terms.append(segment)

    for run in _CHINESE_RUN.findall(q):
        if run in _STOP_TERMS:
            continue
        if len(run) <= 6:
            terms.append(run)
            continue
        terms.append(run)
        for size in (4, 3):
            for i in range(len(run) - size + 1):
                frag = run[i : i + size]
                if frag not in _STOP_TERMS:
                    terms.append(frag)

    terms.extend(_ALNUM.findall(q))

    seen: Set[str] = set()
    ordered: List[str] = []
    for t in sorted(terms, key=len, reverse=True):
        if len(t) < 2 or t in _STOP_TERMS or t in seen:
            continue
        seen.add(t)
        ordered.append(t)
        if len(ordered) >= max_terms:
            break
    return ordered


def keyword_overlap_score(terms: List[str], text: str) -> float:
    """关键词命中率 [0, 1]；优先统计长度≥3 的词，避免子串过多稀释分数。"""
    if not terms or not text:
        return 0.0
    strong = [t for t in terms if len(t) >= 3]
    pool = strong if strong else terms
    hits = sum(1 for t in pool if _term_matches_text(t, text))
    return hits / len(pool)


def resolve_retrieve_counts(
    total_chunks: int,
    *,
    top_k: int,
    pool_max: int,
) -> Tuple[int, int]:
    """
    计算 (向量候选池大小, 最终送入 LLM 的条数)。

    切片总数较少时提高 final_k，避免长手册只带 5 段漏掉专节。
    """
    if total_chunks <= 0:
        return 0, 0

    final_k = min(total_chunks, top_k)
    if total_chunks <= 30:
        final_k = min(total_chunks, max(top_k, (total_chunks + 1) // 2))
    elif total_chunks <= 80:
        final_k = min(total_chunks, max(top_k, top_k + 2))

    pool = min(
        total_chunks,
        max(final_k * 3, top_k * 4, 20),
        pool_max,
    )
    pool = max(pool, final_k)
    return pool, final_k


def _chunk_key(hit: Dict[str, object]) -> Tuple[str, int]:
    return (str(hit.get("doc_id") or ""), int(hit.get("chunk_index") or 0))


def merge_hits(
    primary: List[Dict[str, object]],
    extra: List[Dict[str, object]],
) -> List[Dict[str, object]]:
    """按 doc_id+chunk_index 去重合并，primary 优先。"""
    seen: Set[Tuple[str, int]] = set()
    out: List[Dict[str, object]] = []
    for item in primary + extra:
        key = _chunk_key(item)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def pick_keyword_rescues(
    terms: List[str],
    all_chunks: List[Dict[str, object]],
    pool: List[Dict[str, object]],
    *,
    max_rescue: int = 4,
    min_score: float = 0.35,
) -> List[Dict[str, object]]:
    """
    从全库中捞回「关键词很匹配但向量池未包含」的切片（仅小库启用）。
    """
    if not terms or max_rescue <= 0:
        return []

    in_pool = {_chunk_key(h) for h in pool}
    candidates: List[Tuple[float, Dict[str, object]]] = []

    for hit in all_chunks:
        if _chunk_key(hit) in in_pool:
            continue
        text = str(hit.get("text") or "")
        kw = keyword_overlap_score(terms, text)
        if kw < min_score:
            continue
        # 长关键词命中加权（如「工作时间」）
        phrase_bonus = 0.0
        for t in terms:
            if len(t) >= 3 and _term_matches_text(t, text):
                phrase_bonus = max(phrase_bonus, 0.15)
        candidates.append((kw + phrase_bonus, hit))

    candidates.sort(key=lambda x: x[0], reverse=True)
    return [h for _, h in candidates[:max_rescue]]


def rerank_kb_hits(
    question: str,
    hits: List[Dict[str, object]],
    *,
    final_k: int,
    keyword_weight: float = 0.45,
) -> List[Dict[str, object]]:
    """向量分 + 关键词分加权重排，取 final_k。"""
    if not hits or final_k <= 0:
        return []

    terms = extract_query_terms(question)
    weight = min(max(0.0, keyword_weight), 0.85)
    scored: List[Tuple[float, Dict[str, object]]] = []

    for hit in hits:
        vec = float(hit.get("score") or 0.0)
        text = str(hit.get("text") or "")
        kw = keyword_overlap_score(terms, text)
        combined = (1.0 - weight) * vec + weight * kw
        for t in terms:
            if len(t) >= 3 and _term_matches_text(t, text):
                combined += 0.08
                break
        enriched = dict(hit)
        enriched["vector_score"] = round(vec, 4)
        enriched["keyword_score"] = round(kw, 4)
        enriched["score"] = round(combined, 4)
        scored.append((combined, enriched))

    scored.sort(key=lambda x: x[0], reverse=True)

    seen: Set[Tuple[str, int]] = set()
    out: List[Dict[str, object]] = []
    for _, item in scored:
        key = _chunk_key(item)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
        if len(out) >= final_k:
            break
    return out
