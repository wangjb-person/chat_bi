"""
ChatBI 后端应用包。

分层说明:
  api/              HTTP 接口（Flask Blueprint）
  services/         领域服务与编排
  infrastructure/   外部能力适配（向量库、LLM、MySQL、图表）
  config/           配置与路径
  core/             横切工具（日志、ID）
"""

from chatbi.config import BACKEND_ROOT, PROJECT_ROOT, Settings, get_settings
from chatbi.main import create_app
from chatbi.services.container import ServiceContainer, build_container

__all__ = [
    "create_app",
    "Settings",
    "get_settings",
    "ServiceContainer",
    "build_container",
    "BACKEND_ROOT",
    "PROJECT_ROOT",
]
