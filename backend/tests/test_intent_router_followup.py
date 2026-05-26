"""意图路由：改写后问句打分测试。"""

from chatbi.application.intent_router import IntentRouter
from chatbi.domain.models import Intent


def test_score_question_routes_query_without_follow_up_prefix():
    router = IntentRouter(enable_llm=False)
    score_q = "查询上个月贵阳金阳第一中学学生总分标准差"
    r = router.route("那上个月呢", score_question=score_q)
    assert r.intent in (Intent.QUERY, Intent.ANALYSIS, Intent.CLARIFY)
