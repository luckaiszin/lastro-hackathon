"""Scraper do OLX Imóveis.

Acessível (HTTP 200). Cada anúncio é um `a[data-testid="adcard-link"]`; os
dados (área, quartos, preço) vêm do **texto visível** do card, no formato:
"<título> | <quartos> | <área>m² | <banheiros> | <vagas> | R$ <preço> | IPTU... | Condomínio..."

A `zona` (ex.: "zona-oeste") é necessária para filtrar por bairro; sem ela o OLX
devolve a região inteira.
"""

from __future__ import annotations

import re
from typing import List

from ..models import Listing, Query
from .base import BaseScraper, detect_tipo, register, slugify

SEL_LINK = 'a[data-testid="adcard-link"]'

TIPO_OLX = {"apartamento": "apartamentos", "casa": "casas"}


def _maior_preco(text: str) -> int | None:
    """O preço de venda é o maior valor em R$ (acima de IPTU/condomínio)."""
    valores = [int(v.replace(".", "")) for v in re.findall(r"R\$\s*([\d.]+)", text)]
    return max(valores) if valores else None


def _area_quartos(text: str) -> tuple[float | None, int | None]:
    """Área = primeiro '<n>m²'; quartos = inteiro imediatamente antes da área."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    area = quartos = None
    for i, line in enumerate(lines):
        m = re.fullmatch(r"(\d+)\s*m²", line)
        if m:
            area = float(m.group(1))
            if i > 0 and lines[i - 1].isdigit():
                quartos = int(lines[i - 1])
            break
    if area is None:
        m = re.search(r"(\d+)\s*m²", text)
        if m:
            area = float(m.group(1))
    return area, quartos


@register
class OLXScraper(BaseScraper):
    name = "olx"

    def build_url(self, query: Query, page: int) -> str:
        tipo = TIPO_OLX.get(query.tipo, "imoveis")
        op = "aluguel" if query.operacao == "aluguel" else "venda"
        segs = [f"estado-{slugify(query.uf)}", f"{slugify(query.cidade)}-e-regiao"]
        if query.zona:
            segs.append(slugify(query.zona))
        segs.append(slugify(query.bairro))
        url = f"https://www.olx.com.br/imoveis/{op}/{tipo}/" + "/".join(segs)
        params = []
        if page > 1:
            params.append(f"o={page}")
        if query.preco_min:
            params.append(f"ps={query.preco_min}")
        if query.preco_max:
            params.append(f"pe={query.preco_max}")
        return url + ("?" + "&".join(params) if params else "")

    async def parse(self, page, query: Query) -> List[Listing]:
        try:
            await page.wait_for_selector(SEL_LINK, timeout=15000)
        except Exception:
            return []

        links = await page.query_selector_all(SEL_LINK)
        listings: List[Listing] = []
        for link in links:
            try:
                listing = await self._parse_card(link, query)
                if listing:
                    listings.append(listing)
            except Exception:
                continue
        return listings

    async def _parse_card(self, link, query: Query) -> Listing | None:
        href = await link.get_attribute("href")
        if not href:
            return None

        titulo = (await link.inner_text()).strip().splitlines()[0]

        container = await link.evaluate_handle("el => el.closest('section') || el.parentElement")
        el = container.as_element()
        text = await el.inner_text() if el else ""

        area, quartos = _area_quartos(text)
        return Listing(
            portal=self.name,
            url=href,
            titulo=titulo,
            tipo=detect_tipo(titulo) or (query.tipo if query.tipo != "ambos" else None),
            preco=_maior_preco(text),
            area=area,
            quartos=quartos,
            bairro=query.bairro,
        )
