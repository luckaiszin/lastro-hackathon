"""Nó `normalize`: dedupe, filtros, R$/m² e remoção de outliers por segmento."""

from __future__ import annotations

import statistics
from typing import List, Tuple

from rich.console import Console

from ..models import Listing
from ..scrapers.base import slugify
from ..state import GraphState

console = Console(stderr=True)

# Outliers: amostra mínima por segmento e limites relativos à mediana do R$/m².
OUTLIER_MIN_AMOSTRA = 8
OUTLIER_PISO = 0.5   # remove R$/m² < 0,5 × mediana (barato demais → provável erro)
OUTLIER_TETO = 2.5   # remove R$/m² > 2,5 × mediana (caro demais → fora do padrão)


def _remove_outliers(listings: List[Listing]) -> Tuple[List[Listing], int]:
    """Remove R$/m² anômalos por segmento (tipo), relativo à mediana do segmento.

    O R$/m² imobiliário tem dispersão natural alta (studios vs. imóveis grandes),
    então um critério relativo à mediana é mais robusto e interpretável que IQR:
    descarta valores < 0,5× ou > 2,5× a mediana do tipo — tipicamente erros de
    cadastro (ex.: quarto compartilhado anunciado como imóvel inteiro) ou imóveis
    fora do padrão que distorceriam a média. Segmentos com amostra pequena não são
    filtrados (mediana pouco confiável); imóveis sem R$/m² são preservados.
    """
    grupos: dict[str, List[Listing]] = {}
    for l in listings:
        chave = l.tipo if l.tipo in ("apartamento", "casa") else "outros"
        grupos.setdefault(chave, []).append(l)

    mantidos: List[Listing] = []
    removidos = 0
    for items in grupos.values():
        com_m2 = [l for l in items if l.preco_m2 and l.preco_m2 > 0]
        sem_m2 = [l for l in items if not (l.preco_m2 and l.preco_m2 > 0)]

        if len(com_m2) < OUTLIER_MIN_AMOSTRA:
            mantidos.extend(items)
            continue

        mediana = statistics.median(l.preco_m2 for l in com_m2)
        lo, hi = mediana * OUTLIER_PISO, mediana * OUTLIER_TETO

        for l in com_m2:
            if lo <= l.preco_m2 <= hi:
                mantidos.append(l)
            else:
                removidos += 1
        mantidos.extend(sem_m2)

    return mantidos, removidos


def normalize_node(state: GraphState) -> GraphState:
    query = state["query"]
    raw = state.get("raw_listings", [])

    seen: set[str] = set()
    out = []
    descartados = 0

    for listing in raw:
        # dedupe por URL
        if listing.url in seen:
            descartados += 1
            continue
        seen.add(listing.url)

        # imóvel sem preço é inútil para pesquisa de mercado (e costuma ser
        # ruído de card incompleto/bloqueado) — descarta.
        if listing.preco is None:
            descartados += 1
            continue

        # Para o OLX, a URL do anúncio inclui cidade e bairro — descarta listings
        # de outras localidades que escaparam de um redirecionamento do portal.
        if listing.portal == "olx":
            url_lower = listing.url.lower()
            if slugify(query.cidade) not in url_lower or slugify(query.bairro) not in url_lower:
                descartados += 1
                continue

        listing.compute_preco_m2()

        # filtro por faixa de preço
        if query.preco_min and listing.preco < query.preco_min:
            descartados += 1
            continue
        if query.preco_max and listing.preco > query.preco_max:
            descartados += 1
            continue

        # filtro por nº mínimo de quartos
        if query.quartos_min and listing.quartos is not None and listing.quartos < query.quartos_min:
            descartados += 1
            continue

        # filtro por tipo (quando específico): descarta tipo divergente detectado.
        # Mantém os de tipo indeterminado para não perder anúncios válidos.
        if query.tipo in ("apartamento", "casa") and listing.tipo and listing.tipo != query.tipo:
            descartados += 1
            continue

        out.append(listing)

    outliers = 0
    if query.filtrar_outliers:
        out, outliers = _remove_outliers(out)

    extra = f", {outliers} outliers (R$/m²)" if outliers else ""
    console.log(f"[green]normalize[/]: {len(out)} imóveis válidos, {descartados} descartados{extra}")
    return {"listings": out, "outliers_removidos": outliers}
