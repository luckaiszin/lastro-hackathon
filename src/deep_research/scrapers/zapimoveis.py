"""Scraper do ZAP Imóveis (Grupo OLX).

⚠️ ZAP fica atrás do Cloudflare (como o VivaReal) e é **instável** em headless:
às vezes responde 200 com cards, às vezes 403/0 cards. O scraper é tolerante e
retorna [] quando bloqueado (o nó `scrape` ignora).

Quando carrega, cada card é `[data-cy="rp-property-cd"]` e o texto traz a frase
"Apartamento para comprar com 40 m², 1 quarto, 1 banheiro, 1 vaga em ...".
Requer a `zona` na URL (sem ela o ZAP devolve 404). Anúncios de imobiliária
(href `/imobiliaria/`) são descartados.
"""

from __future__ import annotations

import re
from typing import List

from ..models import Listing, Query
from .base import BaseScraper, detect_tipo, register, slugify

SEL_CARD = '[data-cy="rp-property-cd"]'

TIPO_ZAP = {"apartamento": "apartamentos", "casa": "casas"}


def _maior_preco(text: str) -> int | None:
    valores = [int(v.replace(".", "")) for v in re.findall(r"R\$\s*([\d.]+)", text)]
    return max(valores) if valores else None


@register
class ZapImoveisScraper(BaseScraper):
    name = "zapimoveis"

    def build_url(self, query: Query, page: int) -> str:
        tipo = TIPO_ZAP.get(query.tipo, "imoveis")
        partes = [slugify(query.uf), slugify(query.cidade)]
        if query.zona:
            partes.append(slugify(query.zona))
        partes.append(slugify(query.bairro))
        loc = "+".join(partes)
        op = "aluguel" if query.operacao == "aluguel" else "venda"
        url = f"https://www.zapimoveis.com.br/{op}/{tipo}/{loc}/"
        return f"{url}?pagina={page}" if page > 1 else url

    async def parse(self, page, query: Query) -> List[Listing]:
        try:
            await page.wait_for_selector(SEL_CARD, timeout=15000)
        except Exception:
            return []

        cards = await page.query_selector_all(SEL_CARD)
        listings: List[Listing] = []
        for card in cards:
            try:
                listing = await self._parse_card(card, query)
                if listing:
                    listings.append(listing)
            except Exception:
                continue
        return listings

    async def _parse_card(self, card, query: Query) -> Listing | None:
        link = await card.query_selector("a[href]")
        href = await link.get_attribute("href") if link else None
        if not href or "/imobiliaria/" in href:
            return None  # bloco de anunciante, não é um imóvel
        if href.startswith("/"):
            href = "https://www.zapimoveis.com.br" + href
        href = href.split("?")[0]

        text = await card.inner_text()

        area = quartos = vagas = None
        m = re.search(r"(\d+)\s*m²", text)
        if m:
            area = float(m.group(1))
        m = re.search(r"(\d+)\s*quarto", text)
        if m:
            quartos = int(m.group(1))
        m = re.search(r"(\d+)\s*vaga", text)
        if m:
            vagas = int(m.group(1))

        return Listing(
            portal=self.name,
            url=href,
            tipo=detect_tipo(text) or (query.tipo if query.tipo != "ambos" else None),
            preco=_maior_preco(text),
            area=area,
            quartos=quartos,
            vagas=vagas,
            bairro=query.bairro,
        )
