"""Segmentação de imóveis por tipo (casa/apartamento)."""

from __future__ import annotations

from typing import List, Tuple

from .models import Listing, Query

# Ordem de exibição dos segmentos
ORDEM = ["apartamento", "casa", "outros"]


def segmentar(query: Query, listings: List[Listing]) -> List[Tuple[str, List[Listing]]]:
    """Agrupa os imóveis em segmentos (label, lista), na ordem de `ORDEM`.

    - tipo específico (apartamento/casa): um único segmento com todos os imóveis.
    - tipo "ambos": um segmento por tipo detectado (não detectado -> "outros").
    """
    if query.tipo != "ambos":
        return [(query.tipo, list(listings))]

    grupos: dict[str, List[Listing]] = {}
    for l in listings:
        chave = l.tipo if l.tipo in ("apartamento", "casa") else "outros"
        grupos.setdefault(chave, []).append(l)

    return [(k, grupos[k]) for k in ORDEM if k in grupos]
