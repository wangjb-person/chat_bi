# -*- coding: utf-8 -*-
from chatbi.application.intent_router import IntentRouter
from chatbi.domain.models import Intent
from chatbi.domain.question_scope import (
    analysis_is_grounded,
    is_product_or_meta_question,
)
from chatbi.domain.schema_scope import SchemaScopeChecker

MCP_QUESTION = "\u5206\u6790\u4e00\u4e0b\u5f53\u524d\u7684MCP\u4e0eskills"
SCHOOL_REPORT = (
    "\u8ddf\u6211\u5206\u6790\u4e00\u4e0b\u91d1\u9633\u7b2c\u4e00\u4e2d\u5b66\u4e0e"
    "\u4e16\u7eaa\u57ce\u7b2c\u4e00\u4e2d\u5b66\u7684\u5b66\u751f\u6574\u4f53\u60c5\u51b5"
    "\u6210\u7ee9\uff0c\u4ee5\u62a5\u544a\u7684\u65b9\u5f0f\u5206\u6790\u7ed9\u6211"
)


def test_mcp_skills_routes_to_knowledge():
    assert is_product_or_meta_question(MCP_QUESTION)
    r = IntentRouter(enable_llm=False).route(MCP_QUESTION)
    assert r.intent == Intent.KNOWLEDGE


def test_school_report_still_analysis():
    r = IntentRouter(enable_llm=False).route(SCHOOL_REPORT)
    assert r.intent == Intent.ANALYSIS
    assert r.entities.get("report_mode") is True


def test_ungrounded_analysis_not_grounded():
    scope = SchemaScopeChecker([])
    assert not analysis_is_grounded(
        MCP_QUESTION,
        report_mode=False,
        scope=scope,
    )
