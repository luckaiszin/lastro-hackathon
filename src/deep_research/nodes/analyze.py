"""Nó `analyze`: estatísticas (Python, confiável) + observações (LLM)."""

from __future__ import annotations

import statistics
from typing import List

from rich.console import Console

from .. import config
from ..models import Listing, MarketAnalysis, MarketObservations
from ..state import GraphState

console = Console(stderr=True)


def _stats(listings: List[Listing]) -> MarketAnalysis:
    precos = [l.preco for l in listings if l.preco]
    precos_m2 = [l.preco_m2 for l in listings if l.preco_m2]

    return MarketAnalysis(
        total_imoveis=len(listings),
        preco_medio=round(statistics.mean(precos), 2) if precos else None,
        preco_mediano=round(statistics.median(precos), 2) if precos else None,
        preco_min=min(precos) if precos else None,
        preco_max=max(precos) if precos else None,
        preco_m2_medio=round(statistics.mean(precos_m2), 2) if precos_m2 else None,
    )


def _llm_observations(query, analysis: MarketAnalysis, listings: List[Listing], segmento: str) -> str:
    """Leitura qualitativa via Claude. Best-effort: degrada sem API."""
    if not config.ANTHROPIC_API_KEY:
        return "(Observações do LLM indisponíveis: ANTHROPIC_API_KEY não definida.)"

    try:
        from ..llm import get_llm

        amostra = "\n".join(
            f"- {l.titulo or l.url}: R$ {l.preco} | {l.area} m² | R$/m² {l.preco_m2}"
            for l in listings[:15]
        )
        valores = "aluguéis mensais" if query.operacao == "aluguel" else "preços de venda"
        prompt = (
            f"Você é um analista do mercado imobiliário brasileiro. "
            f"Recorte: {segmento} para {query.operacao} em {query.bairro}, {query.cidade}. "
            f"Os valores abaixo são {valores}.\n\n"
            f"Estatísticas:\n"
            f"- Total: {analysis.total_imoveis}\n"
            f"- Preço médio: R$ {analysis.preco_medio}\n"
            f"- Preço mediano: R$ {analysis.preco_mediano}\n"
            f"- Faixa: R$ {analysis.preco_min} a R$ {analysis.preco_max}\n"
            f"- R$/m² médio: {analysis.preco_m2_medio}\n\n"
            f"Amostra:\n{amostra}\n\n"
            f"Escreva 2-4 frases em português com a leitura de mercado deste recorte "
            f"(nível de preço, dispersão, liquidez aparente)."
        )
        llm = get_llm().with_structured_output(MarketObservations)
        result = llm.invoke(prompt)
        return result.observacoes
    except Exception as exc:
        console.log(f"[yellow]analyze[/]: LLM indisponível: {exc}")
        return "(Observações do LLM indisponíveis nesta execução.)"


def analyze_node(state: GraphState) -> GraphState:
    from ..segments import segmentar

    query = state["query"]
    listings = state.get("listings", [])

    analyses: List[MarketAnalysis] = []
    for segmento, subset in segmentar(query, listings):
        analysis = _stats(subset)
        analysis.segmento = segmento
        if subset:
            analysis.observacoes = _llm_observations(query, analysis, subset, segmento)
        else:
            analysis.observacoes = "Nenhum imóvel encontrado para o recorte pesquisado."
        analyses.append(analysis)

    if not analyses:  # segurança (sem imóveis e sem segmentos)
        vazio = _stats([])
        vazio.segmento = query.tipo
        vazio.observacoes = "Nenhum imóvel encontrado para o recorte pesquisado."
        analyses = [vazio]

    resumo = ", ".join(f"{a.segmento}: {a.total_imoveis}" for a in analyses)
    console.log(f"[green]analyze[/]: {resumo}")
    return {"analyses": analyses}
