"""MySQL 连接与示例 SQL 冒烟测试。"""

from chatbi.config.settings import get_settings
from chatbi.infrastructure.db.mysql_executor import MysqlExecutor

TEST_SQL = """
SELECT (SELECT total_score FROM gy_jyyz_student_score WHERE rank_num = 1)
     - (SELECT total_score FROM gy_jyyz_student_score WHERE rank_num = 2) AS score_difference
""".strip()


def main() -> None:
    settings = get_settings()
    executor = MysqlExecutor(settings.mysql)
    print(f"MySQL: {settings.mysql.host}:{settings.mysql.port}/{settings.mysql.database}")
    print(f"执行 SQL:\n{TEST_SQL}\n")
    df = executor.execute(TEST_SQL)
    print(f"查询结果:\n{df}")


if __name__ == "__main__":
    main()
