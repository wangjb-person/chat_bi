from chatbi.application.intent_router import IntentRouter
from chatbi.agents.planner_agent import PlannerAgent
from chatbi.domain.models import Intent
from unittest.mock import MagicMock


def test_school_report_routes_to_analysis():
    q = "跟我分析一下金阳第一中学与世纪城第一中学的学生整体情况成绩，以报告的方式分析给我"
    r = IntentRouter(enable_llm=False).route(q)
    assert r.intent == Intent.ANALYSIS
    assert r.entities.get("report_mode") is True


def test_planner_report_has_multiple_tasks():
    planner = PlannerAgent(MagicMock(), MagicMock(), MagicMock())
    plan = planner.plan(
        "分析金阳第一中学与世纪城第一中学成绩，以报告方式"
    )
    assert plan.report_mode is True
    assert len(plan.sub_tasks) >= 2
