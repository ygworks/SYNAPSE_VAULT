import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data/vault_core.db"
LLM_API_URL = os.getenv("LLM_API_URL", "http://127.0.0.1:1234/v1/chat/completions")

# 핀셋 타깃 경로 고정
STORAGE_TARGETS = ['L:/', 'M:/', 'N:/', 'O:/(AV)', 'O:/(Uncensored Leak)']
