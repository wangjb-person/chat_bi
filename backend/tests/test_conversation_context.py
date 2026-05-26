"""多轮上下文与问句理解测试。"""

from chatbi.application.query_understanding import QueryUnderstandingService
from chatbi.core.conversation_context import prior_history, trim_messages, truncate_text


class _FakeLlm:
    def complete(self, messages):
        return "查询上个月各学校的完成率"


def test_trim_messages_truncates_long_content():
    msgs = [{"role": "user", "content": "x" * 3000}]
    out = trim_messages(msgs, max_chars=100)
    assert len(out[0]["content"]) <= 100


def test_prior_history_strips_duplicate_user_tail():
    msgs = [
        {"role": "user", "content": "查本月完成率"},
        {"role": "assistant", "content": "SQL: SELECT 1"},
        {"role": "user", "content": "那上个月呢"},
    ]
    prior = prior_history(msgs, "那上个月呢")
    assert prior is not None
    assert prior[-1]["content"] == "SQL: SELECT 1"


def test_query_understanding_rewrites_with_prior():
    history = [
        {"role": "user", "content": "查本月销售额"},
        {"role": "assistant", "content": "查询结果（共 10 行）"},
    ]
    resolved = QueryUnderstandingService(_FakeLlm()).resolve("那上个月呢", history)
    assert resolved.rewritten
    assert "上个月" in resolved.text
