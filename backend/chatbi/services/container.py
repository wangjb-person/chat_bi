from dataclasses import dataclass

from chatbi.config.settings import Settings
from chatbi.infrastructure.db.mysql_executor import MysqlExecutor
from chatbi.infrastructure.llm.client import LlmClient
from chatbi.infrastructure.llm.prompt_builder import SqlPromptBuilder
from chatbi.infrastructure.llm.sql_extractor import SqlExtractor
from chatbi.infrastructure.vector.chroma_store import ChromaVectorStore
from chatbi.infrastructure.viz.plotly_renderer import PlotlyRenderer
from chatbi.services.chat_service import ChatService
from chatbi.services.session_store import InMemorySessionStore
from chatbi.services.training_service import TrainingService


@dataclass
class ServiceContainer:
    """依赖注入容器：组合各层实现，供 API 层统一获取。"""

    settings: Settings
    training: TrainingService
    chat: ChatService
    sessions: InMemorySessionStore


def build_container(settings: Settings) -> ServiceContainer:
    vector_store = ChromaVectorStore(
        persist_directory=settings.persist_directory,
        embedding_model=settings.embedding_model,
        model_cache_dir=settings.model_cache_dir,
    )
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
    chat = ChatService(
        settings=settings,
        vector_store=vector_store,
        llm=llm,
        prompt_builder=SqlPromptBuilder(),
        sql_extractor=SqlExtractor(),
        sql_executor=MysqlExecutor(settings.mysql),
        plotly_renderer=PlotlyRenderer(llm),
        session_store=sessions,
    )
    training = TrainingService(vector_store, llm)
    return ServiceContainer(
        settings=settings,
        training=training,
        chat=chat,
        sessions=sessions,
    )
