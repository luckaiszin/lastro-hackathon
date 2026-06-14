"""Nó `rank`: seleciona oportunidades (R$/m² abaixo da média) e justifica."""

from __future__ import annotations

from typing import List

from rich.console import Console

from .. import config
from ..models import Listing, Opportunity
from ..state import GraphState

console = Console(stderr=True)

TOP_N = 3


def _candidatos(listings: List[Listing], media_m2: float | None) -> List[Listing]:
    com_m2 = [l for l in listings if l.preco_m2]
    if not com_m2:
        return []
    # ordena pelo melhor (menor) R$/m²
    com_m2.sort(key=lambda l: l.preco_m2)
    if media_m2:
        abaixo = [l for l in com_m2 if l.preco_m2 < media_m2]
        return (abaixo or com_m2)[:TOP_N]
    return com_m2[:TOP_N]


def _justificativa(listing: Listing, media_m2: float | None) -> str:
    if media_m2 and listing.preco_m2:
        desconto = round((1 - listing.preco_m2 / media_m2) * 100, 1)
        if desconto > 0:
            return (
                f"R$/m² de {listing.preco_m2} está {desconto}% abaixo da média do recorte "
                f"({media_m2}), indicando bom custo-benefício."
            )
    return f"R$/m² de {listing.preco_m2} entre os mais baixos do recorte."


def _llm_justificativas(query, candidatos, media_m2, segmento):
    """Tenta enriquecer as justificativas via Claude; degrada sem API."""
    if not config.ANTHROPIC_API_KEY or not candidatos:
        return None
    try:
        from ..llm import get_llm
        from pydantic import BaseModel

        class _Just(BaseModel):
            justificativas: list[str]

        itens = "\n".join(
            f"{i+1}. {l.titulo or l.url} — R$ {l.preco} | {l.area} m² | R$/m² {l.preco_m2}"
            for i, l in enumerate(candidatos)
        )
        prompt = (
            f"Recorte: {segmento} para {query.operacao} em {query.bairro}, {query.cidade}. "
            f"R$/m² médio do recorte: {media_m2}.\n\n"
            f"Para cada imóvel abaixo, escreva 1 frase em português justificando por que é "
            f"uma oportunidade (compare com a média). Responda na mesma ordem.\n\n{itens}"
        )
        llm = get_llm().with_structured_output(_Just)
        result = llm.invoke(prompt)
        if len(result.justificativas) >= len(candidatos):
            return result.justificativas
    except Exception as exc:
        console.log(f"[yellow]rank[/]: LLM indisponível: {exc}")
    return None


def _rank_segmento(query, segmento, listings, media_m2) -> List[Opportunity]:
    candidatos = _candidatos(listings, media_m2)
    llm_just = _llm_justificativas(query, candidatos, media_m2, segmento)
    ranking = []
    for i, l in enumerate(candidatos):
        justificativa = llm_just[i] if llm_just else _justificativa(l, media_m2)
        ranking.append(
            Opportunity(
                url=l.url,
                titulo=l.titulo,
                preco=l.preco,
                preco_m2=l.preco_m2,
                justificativa=justificativa,
            )
        )
    return ranking


def rank_node(state: GraphState) -> GraphState:
    from ..segments import segmentar

    query = state["query"]
    listings = state.get("listings", [])
    medias = {a.segmento: a.preco_m2_medio for a in state.get("analyses", [])}

    rankings: dict[str, List[Opportunity]] = {}
    for segmento, subset in segmentar(query, listings):
        rankings[segmento] = _rank_segmento(query, segmento, subset, medias.get(segmento))

    total = sum(len(v) for v in rankings.values())
    console.log(f"[green]rank[/]: {total} oportunidades selecionadas em {len(rankings)} segmento(s)")
    return {"rankings": rankings}
