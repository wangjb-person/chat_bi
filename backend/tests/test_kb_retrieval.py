"""知识库混合检索：关键词重排与补救。"""

from chatbi.services.kb_retrieval import (
    extract_query_terms,
    pick_keyword_rescues,
    rerank_kb_hits,
    resolve_retrieve_counts,
)


def test_extract_query_terms_finds_working_hours():
    terms = extract_query_terms("公司的工作时间是什么")
    assert any("工作时间" in t for t in terms)


def test_resolve_retrieve_counts_scales_for_small_doc():
    pool, final_k = resolve_retrieve_counts(17, top_k=8, pool_max=40)
    assert final_k >= 9
    assert pool >= final_k


def test_rerank_promotes_keyword_match():
    hits = [
        {
            "text": "请假制度与旷工处理",
            "doc_id": "a",
            "chunk_index": 6,
            "score": 0.62,
        },
        {
            "text": "（二）工作时间\n公司实行双休，上午9:00-12:00，下午13:30-17:30。",
            "doc_id": "a",
            "chunk_index": 1,
            "score": 0.41,
        },
    ]
    out = rerank_kb_hits("公司的工作时间是什么", hits, final_k=1)
    assert out[0]["chunk_index"] == 1


def test_keyword_rescue_outside_pool():
    pool = [
        {
            "text": "加班与补卡",
            "doc_id": "a",
            "chunk_index": 5,
            "score": 0.55,
        },
    ]
    all_chunks = pool + [
        {
            "text": "（二）工作时间 上午9:00-12:00 下午13:30-17:30",
            "doc_id": "a",
            "chunk_index": 1,
            "score": 0.0,
        },
    ]
    terms = extract_query_terms("公司的工作时间是什么")
    rescued = pick_keyword_rescues(terms, all_chunks, pool)
    assert rescued and rescued[0]["chunk_index"] == 1
