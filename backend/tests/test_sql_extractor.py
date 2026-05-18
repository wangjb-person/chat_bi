"""SqlExtractor 单元测试。"""

from chatbi.infrastructure.llm.sql_extractor import SqlExtractor


def test_extract_from_sql_fence():
    text = "说明文字\n```sql\nSELECT 1;\n```"
    assert "SELECT 1" in SqlExtractor().extract(text)


def test_extract_select_statement():
    text = "结果如下:\nSELECT id FROM t WHERE id = 1;"
    assert SqlExtractor().extract(text).strip().startswith("SELECT")
