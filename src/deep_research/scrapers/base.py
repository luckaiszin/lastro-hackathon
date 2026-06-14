"""Infraestrutura base de scraping (Playwright) + registro de portais."""

from __future__ import annotations

import asyncio
import random
import re
import unicodedata
from abc import ABC, abstractmethod
from typing import Dict, List, Type

from ..models import Listing, Query

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

_REGISTRY: Dict[str, Type["BaseScraper"]] = {}


def register(cls: Type["BaseScraper"]) -> Type["BaseScraper"]:
    """Decorator: registra um scraper para o fan-out automático."""
    _REGISTRY[cls.name] = cls
    return cls


def all_scrapers() -> List[Type["BaseScraper"]]:
    return list(_REGISTRY.values())


def slugify(text: str) -> str:
    """'São Paulo' -> 'sao-paulo' (translitera acentos)."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.strip().lower()
    text = re.sub(r"\s+", "-", text)
    return re.sub(r"[^a-z0-9\-]", "", text)


_CASA_HINTS = ("casa", "sobrado", "terrea", "térrea", "geminada")
_APTO_HINTS = (
    "apartamento", "apto", "studio", "stúdio", "kitnet", "kitchenette",
    "cobertura", "flat", "loft", "duplex", "garden",
)


def detect_tipo(text: str | None) -> str | None:
    """Classifica o anúncio em 'casa' ou 'apartamento' a partir do texto/título."""
    if not text:
        return None
    t = text.lower()
    if any(h in t for h in _CASA_HINTS):
        return "casa"
    if any(h in t for h in _APTO_HINTS):
        return "apartamento"
    return None


# ---------------------------------------------------------------------------
# Helpers de parsing de texto -> número (R$, m², etc.)
# ---------------------------------------------------------------------------

def parse_int(text: str | None) -> int | None:
    """'R$ 750.000' -> 750000 ; 'A partir de 1.200.000' -> 1200000."""
    if not text:
        return None
    digits = re.sub(r"[^\d]", "", text.split(",")[0])
    return int(digits) if digits else None


def parse_float(text: str | None) -> float | None:
    """'72 m²' -> 72.0 ; '120,5' -> 120.5."""
    if not text:
        return None
    m = re.search(r"\d+(?:[.,]\d+)?", text)
    if not m:
        return None
    return float(m.group(0).replace(".", "").replace(",", "."))


class BaseScraper(ABC):
    """Contrato de um scraper de portal.

    Subclasses implementam `build_url` (URL de busca por página) e
    `parse` (extrai Listings da página já carregada).
    """

    name: str = "base"

    def __init__(self, headless: bool = True):
        self.headless = headless

    @abstractmethod
    def build_url(self, query: Query, page: int) -> str:  # pragma: no cover
        ...

    @abstractmethod
    async def parse(self, page, query: Query) -> List[Listing]:  # pragma: no cover
        ...

    async def scrape(self, query: Query) -> List[Listing]:
        """Percorre as páginas de busca e agrega os Listings encontrados."""
        from playwright.async_api import async_playwright

        results: List[Listing] = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                user_agent=USER_AGENT,
                locale="pt-BR",
                viewport={"width": 1366, "height": 900},
            )
            page = await context.new_page()
            seen: set[str] = set()
            try:
                for n in range(1, query.max_paginas + 1):
                    url = self.build_url(query, n)
                    try:
                        await page.goto(url, timeout=45000, wait_until="domcontentloaded")
                    except Exception:
                        break  # navegação falhou (timeout/bloqueio) -> encerra paginação
                    # Aborta se o portal redirecionou para outra cidade ou bairro (busca
                    # ampliada pelo portal quando não há resultados suficientes).
                    landed = page.url.lower()
                    if slugify(query.cidade) not in landed or slugify(query.bairro) not in landed:
                        break
                    # pequeno atraso aleatório para reduzir bloqueios
                    await asyncio.sleep(random.uniform(1.5, 3.0))
                    items = await self.parse(page, query)

                    # só conta o que é novo: portais sem paginação real (ex.: lista
                    # acoplada a mapa) ou bloqueados repetem/zeram a página seguinte.
                    novos = [l for l in items if l.url not in seen]
                    if not novos:
                        break
                    seen.update(l.url for l in novos)
                    results.extend(novos)
            finally:
                await browser.close()
        return results
