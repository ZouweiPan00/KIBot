from pathlib import Path

from backend.core.config import settings


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SESSION_STORAGE_DIR = PROJECT_ROOT / settings.session_storage_dir
