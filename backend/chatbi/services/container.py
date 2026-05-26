"""
依赖注入容器：在应用启动时组装向量库、LLM、查数管道、意图路由与 AskOrchestrator。

通过 Flask `app.extensions["container"]` 暴露给 API 路由。
"""

from dataclasses import dataclass

from chatbi.agents import (
    AttributionAgent,
    PlannerAgent,
    QueryAgent,
    ReporterAgent,
)
from chatbi.application.analysis_pipeline import AnalysisPipeline
from chatbi.application.ask_orchestrator import AskOrchestrator
from chatbi.application.query_understanding import QueryUnderstandingService
from chatbi.application.intent_router import IntentRouter
from chatbi.config.paths import (
    DEFAULT_KB_FILES_DIR,
    DEFAULT_KB_REGISTRY_PATH,
    DEFAULT_METRICS_PATH,
    DEFAULT_METRICS_SEED,
)
from chatbi.config.settings import Settings
from chatbi.domain.attribution_engine import AttributionEngine
from chatbi.domain.metric_resolver import MetricResolver
from chatbi.domain.sql_builder import MetricSqlBuilder
from chatbi.infrastructure.db.conversation_repository import ConversationRepository
from chatbi.infrastructure.db.mysql_client import MysqlClient
from chatbi.infrastructure.db.mysql_executor import MysqlExecutor
from chatbi.infrastructure.llm.client import LlmClient
from chatbi.infrastructure.llm.prompt_builder import SqlPromptBuilder
from chatbi.infrastructure.llm.sql_extractor import SqlExtractor
from chatbi.infrastructure.metrics.metric_store import MetricStore
from chatbi.infrastructure.vector.chroma_store import ChromaVectorStore
from chatbi.infrastructure.vector.schema_cache import SchemaContextCache
from chatbi.infrastructure.viz.plotly_renderer import PlotlyRenderer
from chatbi.services.chat_pipeline import ChatPipeline
from chatbi.services.conversation_service import ConversationService
from chatbi.services.enhancement_service import EnhancementService
from chatbi.services.metric_service import MetricService
from chatbi.services.query_pipeline import QueryPipeline
from chatbi.services.session_store import InMemorySessionStore
from chatbi.services.kb_pipeline import KbPipeline
from chatbi.services.kb_service import KbService
from chatbi.services.training_service import TrainingService
from chatbi.workflow.agent_workflow import AgentWorkflow


@dataclass
class ServiceContainer:
    """全局单例服务集合，避免在路由层重复 new 组件。"""

    settings: Settings
    training: TrainingService
    query: QueryPipeline
    enhancement: EnhancementService
    sessions: InMemorySessionStore
    metrics: MetricService
    schema_cache: SchemaContextCache
    kb: KbService
    ask: AskOrchestrator
    conversations: ConversationService

    def refresh_ddl_cache(self) -> None:
        """语料中 DDL 变更后刷新意图路由用的 schema 缓存。"""
        self.schema_cache.refresh()


def build_container(settings: Settings) -> ServiceContainer:
    """根据 Settings 构建完整后端依赖图（main.py 启动时调用一次）。"""
    vector_store = ChromaVectorStore(
        persist_directory=settings.persist_directory,
        embedding_model=settings.embedding_model,
        model_cache_dir=settings.model_cache_dir,
        sql_results=settings.chroma_sql_results,
        ddl_results=settings.chroma_ddl_results,
        doc_results=settings.chroma_doc_results,
    )
    schema_cache = SchemaContextCache(vector_store)
    schema_cache.warm()
    sampling = settings.llm_sampling
    llm = LlmClient(
        api_key=settings.api_key,
        base_url=settings.base_url,
        model=settings.model,
        temperature=sampling.temperature,
        top_p=sampling.top_p,
        top_k=sampling.top_k,
    )
    sessions = InMemorySessionStore()
    sql_executor = MysqlExecutor(settings.mysql)
    mysql_client = MysqlClient(settings.mysql)
    conversation_repo = ConversationRepository(mysql_client)
    conversations = ConversationService(conversation_repo)
    try:
        conversation_repo.ensure_tables()
    except Exception as exc:
        import logging

        logging.getLogger("chatbi").warning(
            "[container] 会话表初始化跳过（MySQL 不可用）: %s", exc
        )

    metric_store = MetricStore(DEFAULT_METRICS_PATH)
    metric_store.seed_if_empty(DEFAULT_METRICS_SEED)
    resolver = MetricResolver(metric_store)
    sql_builder = MetricSqlBuilder(metric_store)
    metrics = MetricService(metric_store, resolver)

    query_pipeline = QueryPipeline(
        settings=settings,
        vector_store=vector_store,
        llm=llm,
        prompt_builder=SqlPromptBuilder(),
        sql_extractor=SqlExtractor(),
        sql_executor=sql_executor,
        session_store=sessions,
        resolver=resolver,
        sql_builder=sql_builder,
    )
    enhancement = EnhancementService(llm, PlotlyRenderer(llm), sessions)
    training = TrainingService(vector_store, llm)

    planner = PlannerAgent(resolver, sql_builder, metric_store)
    query_agent = QueryAgent(query_pipeline)
    attribution_agent = AttributionAgent(AttributionEngine())
    reporter_agent = ReporterAgent(llm)
    workflow = AgentWorkflow(
        planner, query_agent, attribution_agent, reporter_agent
    )
    analysis = AnalysisPipeline(workflow)
    chat_pipeline = ChatPipeline(llm)
    kb_service = KbService(
        vector_store,
        registry_path=DEFAULT_KB_REGISTRY_PATH,
        files_dir=DEFAULT_KB_FILES_DIR,
        chunk_size=settings.kb_chunk_size,
        chunk_overlap=settings.kb_chunk_overlap,
        retrieve_top_k=settings.kb_retrieve_top_k,
        retrieve_pool_max=settings.kb_retrieve_pool_max,
        keyword_rescue_max_chunks=settings.kb_keyword_rescue_max_chunks,
        keyword_weight=settings.kb_keyword_weight,
    )
    kb_pipeline = KbPipeline(kb_service, llm)
    ask = AskOrchestrator(
        IntentRouter(
            llm=llm,
            schema_cache=schema_cache,
            metric_resolver=resolver,
            enable_llm=settings.enable_llm_intent,
        ),
        query_pipeline,
        analysis,
        chat_pipeline,
        kb_pipeline=kb_pipeline,
        session_store=sessions,
        enhancement=enhancement,
        query_understanding=QueryUnderstandingService(llm),
    )

    return ServiceContainer(
        settings=settings,
        training=training,
        query=query_pipeline,
        enhancement=enhancement,
        sessions=sessions,
        metrics=metrics,
        schema_cache=schema_cache,
        kb=kb_service,
        ask=ask,
        conversations=conversations,
    )
