"""Configuração carregada de variáveis de ambiente / .env."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Raiz do projeto (…/lastro_hackathon), a partir de src/deep_research/config.py
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _flag(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
LLM_MODEL: str = os.getenv("LLM_MODEL", "claude-haiku-4-5-20251001")
HEADLESS: bool = _flag("HEADLESS", True)
USE_CHROMA: bool = _flag("USE_CHROMA", True)

# Diretório de persistência do Chroma (histórico de imóveis).
# Absoluto por padrão (ancorado na raiz do projeto) para não depender do
# diretório de onde o comando é executado.
CHROMA_DIR: str = os.getenv("CHROMA_DIR", str(_PROJECT_ROOT / ".chroma"))

# Embeddings da busca semântica:
#   "ollama"  -> modelo local via Ollama (precisa do servidor + `ollama pull <modelo>`)
#   "default" -> ONNX all-MiniLM-L6-v2 embutido no Chroma (sem servidor; para testes)
EMBED_BACKEND: str = os.getenv("EMBED_BACKEND", "ollama")
OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434/api/embeddings")
OLLAMA_EMBED_MODEL: str = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
