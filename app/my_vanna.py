import pandas as pd
from chroma_vector import ChromaVectorStore
import pymysql
from typing import List, Dict, Optional


class VannaChroma(ChromaVectorStore):
    """
    集成 MySQL 数据库操作的 Vanna 类
    """

    def __init__(self, config=None):
        super().__init__(config=config)
        self.mysql_config = config.get("mysql", {}) if config else {}

    def run_sql(self, sql: str) -> pd.DataFrame:
        """
        执行 SQL 查询并返回 DataFrame。
        每次请求使用独立连接，避免 Flask 多线程下共享 pymysql 连接导致阻塞或异常。
        """
        host = self.mysql_config.get("host", "127.0.0.1")
        port = self.mysql_config.get("port", 3306)
        print(f"[run_sql] 正在连接 MySQL {host}:{port} ...", flush=True)
        conn = None
        try:
            conn = pymysql.connect(
                host=host,
                port=port,
                user=self.mysql_config.get("user", "root"),
                password=self.mysql_config.get("password", "12345678"),
                database=self.mysql_config.get("database", "testDatabase"),
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor,
                connect_timeout=10,
                read_timeout=60,
                write_timeout=60,
                autocommit=True,
            )
            print("[run_sql] 已连接，执行 SQL ...", flush=True)
            with conn.cursor() as cursor:
                cursor.execute(sql)
                results = cursor.fetchall()
                print(f"[run_sql] 已取回 {len(results)} 行", flush=True)
                return pd.DataFrame(results)
        except Exception as e:
            print(f"❌ SQL 执行失败: {e}", flush=True)
            import traceback
            traceback.print_exc()
            raise Exception(f"SQL 执行失败: {str(e)}\nSQL: {sql}")
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    def close(self):
        """兼容旧接口；数据库连接已改为按次创建，此处无长连接需要关闭。"""
        pass

    def train(self, question: str = None, sql: str = None, ddl: str = None,
              documentation: str = None, general: str = None,
              table_name: str = "", gen_type: str = "") -> str:
        """
        训练方法：添加训练数据到对应的集合
        """
        if question and sql:
            return self.add_question_sql(question, sql, table_name)
        elif ddl:
            return self.add_ddl(ddl, table_name)
        elif documentation:
            return self.add_documentation(documentation, table_name)
        elif general:
            return self.add_general(general, gen_type)
        else:
            raise ValueError("至少需要提供一种训练数据")

    def generate_questions(self, table_name: str = "") -> List[str]:
        """生成示例问题"""
        # 获取该表的相关文档和DDL来生成问题
        ddl_list = self.get_related_ddl("表结构", table_name)
        doc_list = self.get_related_documentation("表说明", table_name)

        context = "\n".join(ddl_list + doc_list)

        prompt = [
            self.system_message(
                "你是一个数据分析专家。根据提供的表结构，生成5个用户可以问的示例问题。"
                "每个问题应该能够通过SQL查询来回答。直接输出问题列表，每行一个。"
            ),
            self.user_message(f"根据以下表结构生成5个示例问题:\n{context}")
        ]

        response = self.submit_prompt(prompt)
        return [q.strip() for q in response.split("\n") if q.strip()]