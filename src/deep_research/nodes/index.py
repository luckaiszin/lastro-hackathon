"""Nó `index` (opcional): persiste os imóveis no histórico vetorial (Chroma).

Ativado por USE_CHROMA=true. Pass-through quando desativado. Falhas de indexação
(ex.: Ollama fora do ar) não derrubam o pipeline.
"""

from __future__ import annotations

from rich.console import Console

from .. import config
from ..state import GraphState

console = Console(stderr=True)


def index_node(state: GraphState) -> GraphState:
    if not config.USE_CHROMA:
        return {}

    listings = state.get("listings", [])
    if not listings:
        return {}

    try:
        from ..store import index_listings

        n = index_listings(listings, state["query"])
        console.log(f"[green]index[/]: {n} imóveis no histórico (embeddings: {config.EMBED_BACKEND})")
    except Exception as exc:  # indexação é best-effort
        console.log(f"[yellow]index[/]: falha ao indexar no Chroma: {exc}")

    return {}
