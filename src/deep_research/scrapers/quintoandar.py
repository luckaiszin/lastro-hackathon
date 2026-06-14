"""Scraper do QuintoAndar (compra).

A extração lê o `aria-label` do card, que carrega os dados estruturados, ex.:
". Pinheiros, São Paulo, Avenida Eusébio Matoso. 46 metros quadrados, 1 quarto,
1 vaga de garagem.  R$ 1.967 Condo. + IPTU, R$ 1.140.000 ."

Observação: o filtro de preço da URL do portal é pouco confiável; a faixa de
preço é reaplicada no nó `normalize` (em Python).
"""

from __future__ import annotations

import re
from typing import List

from ..models import Listing, Query
from .base import BaseScraper, detect_tipo, register, slugify

# Âncora do imóvel: funciona tanto em /comprar quanto em /alugar (cujo wrapper
# perde o data-testid). Links de navegação têm letra após /imovel/ e são filtrados.
SEL_CARD = 'a[href*="/imovel/"]'
SEL_ARIA = "[role='group'][aria-label]"
_ID_RE = re.compile(r"/imovel/\d")


def _parse_aria(aria: str) -> dict:
    """Extrai campos estruturados do aria-label do card."""
    out: dict = {}

    m = re.search(r"(\d+)\s*metros quadrados", aria)
    if m:
        out["area"] = float(m.group(1))

    m = re.search(r"(\d+)\s*quarto", aria)
    if m:
        out["quartos"] = int(m.group(1))

    m = re.search(r"(\d+)\s*vaga", aria)
    if m:
        out["vagas"] = int(m.group(1))

    # Todos os valores em R$; o preço de venda é o último (após o condomínio).
    precos = re.findall(r"R\$\s*([\d.]+)", aria)
    if precos:
        out["preco"] = int(precos[-1].replace(".", ""))

    # Endereço: trecho antes de "<n> metros quadrados".
    m = re.search(r"^[.\s]*(.*?)\.\s*\d+\s*metros", aria)
    if m:
        out["endereco"] = m.group(1).strip()

    return out


@register
class QuintoAndarScraper(BaseScraper):
    name = "quintoandar"

    def build_url(self, query: Query, page: int) -> str:
        cidade = slugify(query.cidade)
        bairro = slugify(query.bairro)
        op = "alugar" if query.operacao == "aluguel" else "comprar"
        base = f"https://www.quintoandar.com.br/{op}/imovel/{bairro}-{cidade}-brasil"
        if page > 1:
            return f"{base}?pagina={page}"
        return base

    async def parse(self, page, query: Query) -> List[Listing]:
        try:
            await page.wait_for_selector(SEL_ARIA, timeout=15000)
        except Exception:
            return []

        anchors = await page.query_selector_all(SEL_CARD)
        listings: List[Listing] = []
        vistos: set[str] = set()
        for anchor in anchors:
            try:
                href = await anchor.get_attribute("href") or ""
                if not _ID_RE.search(href) or href in vistos:
                    continue  # link de navegação ou repetido
                vistos.add(href)
                listing = await self._parse_card(anchor, query)
                if listing:
                    listings.append(listing)
            except Exception:
                continue
        return listings

    async def _parse_card(self, anchor, query: Query) -> Listing | None:
        href = await anchor.get_attribute("href")
        if not href:
            return None
        if href.startswith("/"):
            href = "https://www.quintoandar.com.br" + href.split("?")[0]

        titulo = await anchor.get_attribute("title")

        aria_el = await anchor.query_selector(SEL_ARIA)
        aria = (await aria_el.get_attribute("aria-label")) if aria_el else ""
        campos = _parse_aria(aria or "")

        return Listing(
            portal=self.name,
            url=href,
            titulo=titulo,
            tipo=detect_tipo(titulo) or (query.tipo if query.tipo != "ambos" else None),
            preco=campos.get("preco"),
            area=campos.get("area"),
            quartos=campos.get("quartos"),
            vagas=campos.get("vagas"),
            bairro=query.bairro,
            endereco=campos.get("endereco"),
            descricao=titulo,
        )
