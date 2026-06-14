"""Nó `parse`: valida/normaliza a consulta do usuário."""

from __future__ import annotations

from ..state import GraphState


def parse_node(state: GraphState) -> GraphState:
    query = state["query"]

    # Garante consistência da faixa de preço (min <= max).
    if query.preco_min and query.preco_max and query.preco_min > query.preco_max:
        query.preco_min, query.preco_max = query.preco_max, query.preco_min

    query.cidade = query.cidade.strip()
    query.bairro = query.bairro.strip()
    query.tipo = (query.tipo or "apartamento").strip().lower()

    return {"query": query}
