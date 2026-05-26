"""分析类意图辅助判断（路由与 Planner 共用）。"""

from __future__ import annotations

import re

_REPORT_STYLE = re.compile(
    r"报告|以报告|分析报告|分析报|整体情况|综合评价|对比分析|分析对比|"
    r"(?:分析|对比|比较).*(?:中学|学校)|(?:中学|学校).*(?:分析|对比|比较|情况)"
)

_SCHOOL_NAME = re.compile(
    r"[\u4e00-\u9fff]{2,20}(?:中学|学校|实验小学|附中)"
)


def is_report_style_question(question: str) -> bool:
    """用户是否要求「报告式」多步分析（非单次表格）。"""
    q = question.strip()
    if _REPORT_STYLE.search(q):
        return True
    return bool(
        re.search(r"分析", q)
        and _SCHOOL_NAME.search(q)
        and re.search(r"与|和|及|对比|比较", q)
    )


def extract_school_names(question: str) -> list[str]:
    """从问题中提取「某某中学/学校」实体名列表（去重保序）。"""
    found = _SCHOOL_NAME.findall(question)
    # 去重保序
    seen: set[str] = set()
    out: list[str] = []
    for name in found:
        if name not in seen:
            seen.add(name)
            out.append(name)
    return out
