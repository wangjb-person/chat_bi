# -*- coding: utf-8 -*-
from pathlib import Path

from chatbi.application.intent_router import IntentRouter
from chatbi.domain.metric_resolver import MetricResolver
from chatbi.domain.models import Intent
from chatbi.domain.question_scope import evaluate_warehouse_eligibility
from chatbi.domain.schema_scope import SchemaScopeChecker
from chatbi.infrastructure.metrics.metric_store import MetricStore

PYTHON_Q = "python\u8bed\u8a00\u91cc\u6709\u591a\u5c11\u79cd\u6570\u636e\u7c7b\u578b"
QING_Q = "\u6e05\u671d\u6709\u591a\u5c11\u4f4d\u7687\u5e1d"
STUDENT_Q = (
    "\u8d35\u9633\u4e16\u7eaa\u57ce\u7b2c\u4e00\u4e2d\u5b66\u8bed\u6587\u5206\u6570"
    "\u4f4e\u4e8e60\u5206\u7684\u5b66\u751f\u6709\u54ea\u4e9b"
)


def _resolver():
    path = Path(__file__).resolve().parents[1] / "data" / "metrics.json"
    return MetricResolver(MetricStore(path))


def test_python_not_warehouse_eligible():
    e = evaluate_warehouse_eligibility(
        PYTHON_Q, SchemaScopeChecker(), metric_resolver=_resolver()
    )
    assert not e.can_query
    assert e.source in ("general_knowledge", "out_of_domain", "ungrounded_query", "default")


def test_qing_not_warehouse_eligible():
    e = evaluate_warehouse_eligibility(QING_Q, SchemaScopeChecker())
    assert not e.can_query


def test_student_list_eligible():
    e = evaluate_warehouse_eligibility(STUDENT_Q, SchemaScopeChecker())
    assert e.can_query


def test_router_python_and_qing_to_knowledge():
    router = IntentRouter(enable_llm=False, metric_resolver=_resolver())
    assert router.route(PYTHON_Q).intent == Intent.KNOWLEDGE
    assert router.route(QING_Q).intent == Intent.KNOWLEDGE
    assert router.route(STUDENT_Q).intent == Intent.QUERY
