"""生成面向业务人员的中文问句时，须遵守的表述规则。"""

CHINESE_BUSINESS_QUESTION_RULES = (
    "问题必须使用中文，面向业务人员阅读。\n"
    "禁止在问题中出现英文字段名、表名（例如 total_score、rank_num、student_id、"
    "gy_sjcyz_student_score 等）。\n"
    "应使用 DDL 中的 COMMENT、字段说明、业务文档里的中文说法，"
    "或 SQL 查询结果列的中文别名（如「总分」「排名」「学号」「姓名」）。\n"
    "若参考信息里出现英文列名或 SQL，须在问题中改写为中文业务含义，不得照搬英文。\n"
    "禁止出现 SELECT、SQL、AS 等技术词汇。"
)
