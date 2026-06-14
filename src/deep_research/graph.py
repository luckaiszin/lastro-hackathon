"""Construção do grafo LangGraph: parse → scrape → normalize → index → analyze → rank → report."""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from .nodes.analyze import analyze_node
from .nodes.index import index_node
from .nodes.normalize import normalize_node
from .nodes.parse import parse_node
from .nodes.rank import rank_node
from .nodes.report import report_node
from .nodes.scrape import scrape_node
from .state import GraphState


def _route_after_normalize(state: GraphState) -> str:
    """Curto-circuito: sem imóveis, pula análise/ranking e vai direto ao relatório."""
    return "index" if state.get("listings") else "report"


def build_graph():
    g = StateGraph(GraphState)

    g.add_node("parse", parse_node)
    g.add_node("scrape", scrape_node)        # async
    g.add_node("normalize", normalize_node)
    g.add_node("index", index_node)
    g.add_node("analyze", analyze_node)
    g.add_node("rank", rank_node)
    g.add_node("report", report_node)

    g.set_entry_point("parse")
    g.add_edge("parse", "scrape")
    g.add_edge("scrape", "normalize")
    # ramo condicional: com imóveis segue para index; sem imóveis vai ao report
    g.add_conditional_edges(
        "normalize",
        _route_after_normalize,
        {"index": "index", "report": "report"},
    )
    g.add_edge("index", "analyze")
    g.add_edge("analyze", "rank")
    g.add_edge("rank", "report")
    g.add_edge("report", END)

    return g.compile()
