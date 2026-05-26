"""MySQL SQL 预检与纠错相关测试。"""

from unittest.mock import MagicMock

import pandas as pd

from chatbi.services.query_pipeline import QueryPipeline


def _make_pipeline() -> QueryPipeline:
    return QueryPipeline(
        settings=MagicMock(),
        vector_store=MagicMock(),
        llm=MagicMock(),
        prompt_builder=MagicMock(),
        sql_extractor=MagicMock(),
        sql_executor=MagicMock(),
        session_store=MagicMock(),
        resolver=MagicMock(),
        sql_builder=MagicMock(),
    )


def test_preflight_rejects_percentile_cont():
    svc = _make_pipeline()
    err = svc._mysql_sql_preflight(
        "SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY x) FROM t;"
    )
    assert err is not None
    assert "PERCENTILE_CONT" in err


def test_preflight_rejects_offset_subquery():
    svc = _make_pipeline()
    err = svc._mysql_sql_preflight("SELECT 1 LIMIT 2 OFFSET (SELECT 1);")
    assert err is not None
    assert "OFFSET" in err


def test_run_sql_with_correction_retries_on_failure():
    svc = _make_pipeline()
    svc._sql_extractor.extract.return_value = "SELECT 1;"
    svc._llm.complete.return_value = "修正后:\n```sql\nSELECT 1;\n```"
    svc._sql_executor.execute.side_effect = [
        Exception("SQL 执行失败: syntax error"),
        pd.DataFrame([{"n": 1}]),
    ]
    svc._build_rag_prompt = MagicMock(return_value=[{"role": "system", "content": "x"}])

    df, final_sql, correction_count = svc.run_sql_with_correction(
        messages=[{"role": "user", "content": "test"}],
        table_name="",
        sql="SELECT bad;",
        llm_response="SELECT bad;",
    )

    assert correction_count == 1
    assert final_sql == "SELECT 1;"
    assert len(df) == 1
    svc._llm.complete.assert_called_once()
