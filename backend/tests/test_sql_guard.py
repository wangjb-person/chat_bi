from chatbi.core.sql_guard import looks_like_executable_sql


def test_rejects_plain_chinese():
    assert not looks_like_executable_sql("当前数据库未包含华强集团公司相关信息")


def test_accepts_select():
    assert looks_like_executable_sql("SELECT name AS `姓名` FROM gy_jyyz_student_score LIMIT 10;")
