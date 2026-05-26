from chatbi.application.intent_router import IntentRouter
from chatbi.domain.models import Intent


def test_joke_routes_to_chat():
    r = IntentRouter().route("你可以给我讲个笑话吗")
    assert r.intent == Intent.CHAT


def test_company_intro_routes_to_knowledge():
    r = IntentRouter().route("华强集团公司介绍")
    assert r.intent == Intent.KNOWLEDGE


def test_data_question_routes_to_query():
    r = IntentRouter().route("贵阳金阳第一中学前20名学生总分成绩的标准差是多少？")
    assert r.intent == Intent.QUERY


def test_why_routes_to_analysis():
    r = IntentRouter().route("为什么A产品本月毛利率下降了？")
    assert r.intent == Intent.ANALYSIS


def test_student_list_below_score_routes_to_query():
    q = (
        "\u8d35\u9633\u4e16\u7eaa\u57ce\u7b2c\u4e00\u4e2d\u5b66\u8bed\u6587\u5206\u6570"
        "\u4f4e\u4e8e60\u5206\u7684\u5b66\u751f\u6709\u54ea\u4e9b"
    )
    r = IntentRouter(enable_llm=False).route(q)
    assert r.intent == Intent.QUERY
