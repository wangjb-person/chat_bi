# test_mysql.py
import os
from pathlib import Path

import pymysql
from dotenv import load_dotenv



################# 测试数据库连接

_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_ROOT / ".env")

host = os.getenv("MYSQL_HOST", "127.0.0.1")
port = int(os.getenv("MYSQL_PORT", "3306"))
user = os.getenv("MYSQL_USER", "root")
password = os.getenv("MYSQL_PASSWORD")
database = os.getenv("MYSQL_DATABASE", "testDatabase")

TEST_SQL = """
SELECT (SELECT total_score FROM gy_jyyz_student_score WHERE rank_num = 1)
     - (SELECT total_score FROM gy_jyyz_student_score WHERE rank_num = 2) AS score_difference
""".strip()

if not password:
    raise SystemExit("请在项目根目录 .env 中配置 MYSQL_PASSWORD")

try:
    conn = pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        cursorclass=pymysql.cursors.DictCursor,
    )

    print("✅ MySQL 连接成功")
    print(f"执行 SQL:\n{TEST_SQL}\n")

    with conn.cursor() as cursor:
        cursor.execute(TEST_SQL)
        result = cursor.fetchall()
        print(f"查询结果: {result}")

    conn.close()

except Exception as e:
    print(f"❌ 执行失败: {e}")
