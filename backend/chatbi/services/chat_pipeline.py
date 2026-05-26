"""
对话管道：chat / knowledge / clarify 三类意图仅调用 LLM，不连接 MySQL。

由 AskOrchestrator._stream_chat 使用。
"""

from __future__ import annotations

from typing import Dict, Generator, List, Optional

from chatbi.domain.models import Intent
from chatbi.domain.question_scope import is_product_or_meta_question
from chatbi.infrastructure.llm.client import LlmClient
from chatbi.infrastructure.llm.messages import assistant_message, system_message, user_message

_CHAT_SYSTEM = (
    "你是 ChatBI 助手（对话模式）。闲聊/笑话/问候直接中文回复；"
    "禁止 SQL 与假数据。如需查业务数据，简短引导补充指标与时间。"
)

_CLARIFY_SYSTEM = (
    "你是 ChatBI 助手（澄清模式）。说明用户需补充的指标/时间/对象/达标线，"
    "并给 2 个可查数示例（如成绩排名、标准差）。禁止 SQL。"
)


_KNOWLEDGE_SYSTEM = (
    "你是 ChatBI 助手。请像日常技术问答一样直接回答用户问题："
    "开门见山给结论，再按需补充要点；不要声明数据来源，"
    "不要写「以下为通用知识」「非数据库查询」等套话，不要生成 SQL。"
    "仅当用户明确要查本系统业务库数据时，再用一句话引导其说明指标与时间。"
)

_PRODUCT_KNOWLEDGE_SYSTEM = (
    "你是 ChatBI 平台助手，回答关于本系统架构与能力的问题（非 MySQL 业务表字段）。\n"
    "可参考的能力划分：\n"
    "- 问数入口 AskOrchestrator：意图路由后分对话/查数/分析三条通道；\n"
    "- 查数 QueryPipeline：指标 SQL 优先，否则 RAG+NL2SQL+执行纠错；\n"
    "- 分析 AgentWorkflow：Planner 拆子任务 → 并行 QueryAgent → Attribution → Reporter 报告；\n"
    "- MCP：外部工具协议，可在 Cursor/Agent 中挂载数据库或 API 工具（本仓库是否接入视部署而定）；\n"
    "- Skills：Cursor Agent 技能文件（.cursor/skills），用于约束助手行为，不是数据库列。\n"
    "- 语料/指标：Chroma 存 DDL/示例 SQL；metrics.json 定义口径。\n"
    "直接中文回答，不要 SQL，不要编造表字段名。"
)


class ChatPipeline:
    """对话 / 通用知识通道：只调 LLM，不访问 MySQL。"""

    def __init__(self, llm: LlmClient) -> None:
        """注入大模型客户端。"""
        self._llm = llm

    def _system_for(self, intent: Intent, *, question: str = "") -> str:
        """按意图选择 system prompt；产品元问题用专用架构说明。"""
        if intent == Intent.KNOWLEDGE and is_product_or_meta_question(question):
            return _PRODUCT_KNOWLEDGE_SYSTEM
        if intent == Intent.KNOWLEDGE:
            return _KNOWLEDGE_SYSTEM
        if intent == Intent.CLARIFY:
            return _CLARIFY_SYSTEM
        return _CHAT_SYSTEM

    def complete(
        self,
        question: str,
        *,
        intent: Intent = Intent.CHAT,
        missing_slots: Optional[List[str]] = None,
        history: Optional[List[Dict]] = None,
    ) -> str:
        messages = self._build_messages(
            question, intent=intent, missing_slots=missing_slots, history=history
        )
        return self._llm.complete(messages)

    def stream(
        self,
        question: str,
        *,
        intent: Intent = Intent.CHAT,
        missing_slots: Optional[List[str]] = None,
        history: Optional[List[Dict]] = None,
    ) -> Generator[str, None, str]:
        messages = self._build_messages(
            question, intent=intent, missing_slots=missing_slots, history=history
        )
        chunks: List[str] = []
        for chunk in self._llm.complete_stream(messages):
            chunks.append(chunk)
            yield chunk
        return "".join(chunks)

    def build_clarify_user_message(
        self, question: str, *, missing_slots: List[str]
    ) -> str:
        slot_names = {
            "metric": "指标定义（完成率/销售额等具体口径）",
            "time_range": "时间范围（本月、Q2、近30天等）",
            "filter_object": "分析对象（团队、学校、产品等）",
            "threshold": "达标标准（如 ≥95%）",
        }
        hints = [slot_names.get(s, s) for s in missing_slots]
        return (
            f"用户原始问题：{question}\n"
            f"需要用户补充：{'、'.join(hints)}。\n"
            "请引导用户补充后重新提问。"
        )

    def _build_messages(
        self,
        question: str,
        *,
        intent: Intent,
        missing_slots: List[str] | None = None,
        history: Optional[List[Dict]] = None,
    ) -> List[Dict]:
        user_content = question
        if intent == Intent.CLARIFY and missing_slots:
            user_content = self.build_clarify_user_message(
                question, missing_slots=missing_slots
            )
        msgs: List[Dict] = [
            system_message(self._system_for(intent, question=question)),
        ]
        if history:
            for item in history:
                role = item.get("role")
                content = (item.get("content") or "").strip()
                if role in ("user", "assistant") and content:
                    if role == "user":
                        msgs.append(user_message(content))
                    else:
                        msgs.append(assistant_message(content))
        msgs.append(user_message(user_content))
        return msgs
