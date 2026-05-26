"""
业务库范围判断：问题是否属于当前租户 DDL/业务域，还是库外通识。

用于意图门控与库外问题改判 knowledge。
"""

from __future__ import annotations

import re
from typing import List, Optional

_OUT_OF_DOMAIN_PATTERNS: List[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bMCP\b|skills?|Cursor|Chroma|NL2SQL|AskOrchestrator", re.I), "产品/系统"),
    (re.compile(r"多少个省|几个省|省份|直辖市|自治区|地级市|行政区域|行政区|辖区"), "地理行政"),
    (re.compile(r"新能源|车企|比亚迪|特斯拉|蔚来|小鹏|理想汽车"), "汽车行业"),
    (re.compile(r"中国历史|朝代|人口.*?(?:中国|全国)"), "历史人口常识"),
    (
        re.compile(
            r"清朝|明朝|唐朝|宋朝|元朝|民国|汉代|秦代|"
            r"皇帝|太后|太子|大臣|登基|驾崩|年号"
        ),
        "历史朝代",
    ),
    (
        re.compile(
            r"Python|Java|C\+\+|JavaScript|编程语言|"
            r"数据类型|语法|面向对象|函数式"
        ),
        "编程常识",
    ),
    (re.compile(r"世界杯|奥运会|NBA|股票大盘|汇率|黄金价"), "泛资讯"),
    (re.compile(r"天气|气温|降雨"), "天气"),
]

_IN_DOMAIN_PATTERNS: List[re.Pattern[str]] = [
    re.compile(p)
    for p in [
        r"学生|考生|成绩|总分|排名|标准差|方差|平均分",
        r"学校|中学|小学|班级|年级",
        r"销售|订单|营收|毛利|产品|渠道",
        r"销售区域|业务区域|按区域|分区域|大区",
        r"完成率|达标|KPI|目标值",
        r"gy_[a-z_]+",
    ]
]


class SchemaScopeChecker:
    """基于规则词表与 DDL 词汇判断问题是否在业务库能力范围内。"""

    def __init__(self, schema_vocabulary: Optional[List[str]] = None) -> None:
        """schema_vocabulary 通常来自 SchemaContextCache 从 DDL 抽取的字段/中文词。"""
        self._vocab = set(schema_vocabulary or [])

    def build_hint_from_ddl(self, ddl_snippets: List[str]) -> str:
        """拼接若干条 DDL 为 LLM/意图用的短摘要（有长度上限）。"""
        if not ddl_snippets:
            return "（暂无表结构语料）"
        return "\n".join(ddl_snippets[:5])[:3000]

    def extract_vocab_from_ddl(self, ddl_snippets: List[str]) -> List[str]:
        """从 DDL 文本抽取英文字段名与中文 COMMENT 词，供词表匹配。"""
        words: set[str] = set()
        for ddl in ddl_snippets:
            for m in re.finditer(
                r"`?([a-zA-Z_][a-zA-Z0-9_]*)`?|([\u4e00-\u9fff]{2,8})",
                ddl,
            ):
                g = m.group(1) or m.group(2)
                if g and len(g) >= 2:
                    words.add(g.lower() if g.isascii() else g)
        return list(words)

    def is_out_of_business_schema(self, question: str, *, schema_hint: str = "") -> bool:
        """True 表示问题与当前业务库无关（省份、编程、朝代等）。"""
        q = question.strip()
        if any(p.search(q) for p in _IN_DOMAIN_PATTERNS):
            return False

        for pattern, _label in _OUT_OF_DOMAIN_PATTERNS:
            if pattern.search(q):
                return True

        if self._vocab:
            q_lower = q.lower()
            if any(v in q_lower or v in q for v in self._vocab if len(v) >= 3):
                return False

        if schema_hint:
            tokens = re.findall(r"[\u4e00-\u9fff]{2,6}", q)
            if any(t in schema_hint for t in tokens):
                return False

        return False

    def out_of_domain_label(self, question: str) -> Optional[str]:
        """返回库外域的中文标签，用于 intent reason 展示。"""
        for pattern, label in _OUT_OF_DOMAIN_PATTERNS:
            if pattern.search(question):
                return label
        return None
