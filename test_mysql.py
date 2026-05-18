# test_mysql.py
import pymysql
import pandas as pd

try:
    conn = pymysql.connect(
        host="localhost",
        port=3306,
        user="root",
        password="12345678",  # 改成您的密码
        database="testDatabase",  # 改成您的数据库
        cursorclass=pymysql.cursors.DictCursor
    )

    print("✅ MySQL 连接成功")

    # 测试查询
    with conn.cursor() as cursor:
        cursor.execute("SELECT 1 as test")
        result = cursor.fetchall()
        print(f"测试查询结果: {result}")

    conn.close()

except Exception as e:
    print(f"❌ MySQL 连接失败: {e}")