"""会话消息与 LLM 上下文转换测试。"""

from chatbi.services.conversation_service import ConversationService


def test_title_from_question_truncates():
    long_q = "这是一段很长的问题" * 10
    title = ConversationService.title_from_question(long_q, max_len=20)
    assert len(title) <= 20
    assert title.endswith("…")


def test_message_to_llm_text_query_result():
    svc = ConversationService.__new__(ConversationService)
    text = svc._message_to_llm_text(
        {
            "role": "assistant",
            "kind": "query-result",
            "content": {
                "sql": "SELECT 1",
                "queryResult": {"row_count": 2, "data": [{"a": 1}, {"a": 2}]},
            },
        }
    )
    assert "SELECT 1" in text
    assert "2" in text
