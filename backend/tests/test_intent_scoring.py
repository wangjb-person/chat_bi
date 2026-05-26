from chatbi.domain.intent_scoring import IntentScorer
from chatbi.domain.models import Intent


def test_list_students_scores_query_highest():
    q = (
        "\u8d35\u9633\u4e16\u7eaa\u57ce\u7b2c\u4e00\u4e2d\u5b66\u8bed\u6587\u5206\u6570"
        "\u4f4e\u4e8e60\u5206\u7684\u5b66\u751f\u6709\u54ea\u4e9b"
    )
    s = IntentScorer().score(q)
    assert s.intent == Intent.QUERY
    assert s.scores[Intent.QUERY.value] > s.scores[Intent.KNOWLEDGE.value]
