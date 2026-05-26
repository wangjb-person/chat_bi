from chatbi.core.sql_error_message import format_sql_run_error_parts


def test_unknown_column_includes_raw_and_zh():
    exc = Exception(
        '(1054, "Unknown column \'student_id\' in \'field list\'")'
    )
    parts = format_sql_run_error_parts(exc, sql="SELECT student_id FROM t")
    assert "student_id" in parts["raw"]
    assert "不存在列" in parts["hint_zh"]
    assert "Original" in parts["display"] or parts["raw"]
    assert "中文说明" in parts["display"]
    assert "不存在列" in parts["hint_zh"]
