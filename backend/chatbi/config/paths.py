"""项目路径常量：统一解析 backend 根目录与仓库根目录。"""

from pathlib import Path

# backend/chatbi/config/paths.py -> backend/
BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
# 仓库根目录 chat_bi/
PROJECT_ROOT = BACKEND_ROOT.parent

DATA_DIR = BACKEND_ROOT / "data"
DEFAULT_CHROMA_DIR = DATA_DIR / "chroma_db"
DEFAULT_MODEL_CACHE_DIR = DATA_DIR / "model_cache"
DEFAULT_METRICS_PATH = DATA_DIR / "metrics.json"
DEFAULT_METRICS_SEED = DATA_DIR / "metrics_seed.json"
DEFAULT_KB_REGISTRY_PATH = DATA_DIR / "kb_documents.json"
DEFAULT_KB_FILES_DIR = DATA_DIR / "kb_files"
