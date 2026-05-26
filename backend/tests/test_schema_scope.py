from chatbi.application.intent_router import IntentRouter
from chatbi.domain.models import Intent
from chatbi.domain.schema_scope import SchemaScopeChecker


def test_provinces_out_of_schema():
    scope = SchemaScopeChecker()
    assert scope.is_out_of_business_schema("中国有多少个省份")


def test_chongqing_admin_regions_fast_knowledge():
    r = IntentRouter(enable_llm=False).route("重庆的行政区域有哪些")
    assert r.intent == Intent.KNOWLEDGE
    assert r.confidence >= 0.82


def test_student_in_schema():
    scope = SchemaScopeChecker()
    assert not scope.is_out_of_business_schema(
        "贵阳金阳第一中学前20名学生总分成绩的标准差是多少？"
    )


def test_ev_companies_out_of_schema():
    scope = SchemaScopeChecker()
    assert scope.is_out_of_business_schema("当前比较出名的新能源车企有多少个")


def test_router_provinces_to_knowledge():
    r = IntentRouter(enable_llm=False).route("中国有多少个省份")
    assert r.intent == Intent.KNOWLEDGE


def test_router_team_kpi_to_clarify():
    r = IntentRouter(enable_llm=False).route("张三团队的完成率达标了吗")
    assert r.intent == Intent.CLARIFY
    assert r.missing_slots
