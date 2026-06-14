"""Scraper do VivaReal (Grupo OLX).

⚠️ ATENÇÃO: o VivaReal está atrás de **Cloudflare** (retorna HTTP 403
"Attention Required") e bloqueia Chromium headless. Para funcionar exigiria
playwright-stealth + proxy residencial / navegador undetected — fora do escopo
deste hackathon. O scraper é mantido como scaffold e retorna [] quando bloqueado
(o nó `scrape` tolera isso). Para scraping real, prefira o QuintoAndar.

Quando desbloqueado, a extração lê os cards por `data-testid` (constantes SEL_*).
"""

from __future__ import annotations

from typing import List

from ..models import Listing, Query
from .base import BaseScraper, detect_tipo, parse_float, parse_int, register, slugify

SEL_CARD = '[data-testid="card"], article[data-cy="rp-property-cd"]'
SEL_PRICE = '[data-testid="price"], .property-card__price'
SEL_AREA = '[itemprop="floorSize"], .property-card__detail-area'
SEL_ROOMS = '[itemprop="numberOfRooms"], .property-card__detail-room'
SEL_TITLE = '.property-card__title, [data-testid="card-title"]'
SEL_ADDRESS = '.property-card__address, [data-testid="card-address"]'
SEL_LINK = "a"


@register
class VivaRealScraper(BaseScraper):
    name = "vivareal"

    def build_url(self, query: Query, page: int) -> str:
        cidade = slugify(query.cidade)
        bairro = slugify(query.bairro)
        tipo = "imoveis" if query.tipo == "ambos" else slugify(query.tipo)
        op = "aluguel" if query.operacao == "aluguel" else "venda"
        params = []
        if query.preco_min:
            params.append(f"preco-desde={query.preco_min}")
        if query.preco_max:
            params.append(f"preco-ate={query.preco_max}")
        if page > 1:
            params.append(f"pagina={page}")
        qs = ("?" + "&".join(params)) if params else ""
        return (
            f"https://www.vivareal.com.br/{op}/{cidade}/bairros/{bairro}/"
            f"{tipo}_residencial/{qs}"
        )

    async def parse(self, page, query: Query) -> List[Listing]:
        try:
            await page.wait_for_selector(SEL_CARD, timeout=15000)
        except Exception:
            return []

        cards = await page.query_selector_all(SEL_CARD)
        listings: List[Listing] = []
        for card in cards:
            try:
                listings.append(await self._parse_card(card, query))
            except Exception:
                continue
        return [l for l in listings if l is not None]

    async def _parse_card(self, card, query: Query) -> Listing | None:
        async def text(sel: str) -> str | None:
            el = await card.query_selector(sel)
            return (await el.inner_text()).strip() if el else None

        link_el = await card.query_selector(SEL_LINK)
        href = await link_el.get_attribute("href") if link_el else None
        if not href:
            return None
        if href.startswith("/"):
            href = "https://www.vivareal.com.br" + href

        titulo = await text(SEL_TITLE)
        return Listing(
            portal=self.name,
            url=href,
            titulo=titulo,
            tipo=detect_tipo(titulo) or (query.tipo if query.tipo != "ambos" else None),
            preco=parse_int(await text(SEL_PRICE)),
            area=parse_float(await text(SEL_AREA)),
            quartos=parse_int(await text(SEL_ROOMS)),
            bairro=query.bairro,
            endereco=await text(SEL_ADDRESS),
        )
