"""Estado compartilhado entre os nós do grafo LangGraph."""

from __future__ import annotations

from typing import Any, Dict, List, TypedDict

from .models import Listing, MarketAnalysis, Opportunity, Query


class GraphState(TypedDict, total=False):
    query: Query
    options: Dict[str, Any]               # ex.: {"mock": True}
    raw_listings: List[Listing]           # bruto, antes de filtrar/deduplicar
    listings: List[Listing]               # normalizado
    outliers_removidos: int               # nº de R$/m² anômalos descartados
    analyses: List[MarketAnalysis]        # uma análise por segmento (tipo)
    rankings: Dict[str, List[Opportunity]]  # segmento -> oportunidades
    report: str
