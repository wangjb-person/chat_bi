# -*- coding: utf-8 -*-
import json
from pathlib import Path

import pytest

from chatbi.application.intent_router import IntentRouter
from chatbi.domain.models import Intent
from chatbi.domain.metric_resolver import MetricResolver
from chatbi.infrastructure.metrics.metric_store import MetricStore

_CASES_PATH = Path(__file__).parent / "intent_cases.json"


def _load_cases():
    data = json.loads(_CASES_PATH.read_text(encoding="utf-8"))
    return data["cases"]


def _router() -> IntentRouter:
    metrics_path = Path(__file__).resolve().parents[1] / "data" / "metrics.json"
    store = MetricStore(metrics_path)
    return IntentRouter(
        enable_llm=False,
        metric_resolver=MetricResolver(store),
    )


@pytest.mark.parametrize("case", _load_cases(), ids=lambda c: c["intent"])
def test_intent_regression_case(case):
    router = _router()
    r = router.route(case["question"])
    expected = Intent(case["intent"])
    assert r.intent == expected, (
        f"q={case['question']!r} expected={expected.value} "
        f"got={r.intent.value} reason={r.reason} scores={r.entities.get('scores')}"
    )
