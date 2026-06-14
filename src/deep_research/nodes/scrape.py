"""Nó `scrape`: fan-out dos scrapers, tolerante a falhas por portal."""

from __future__ import annotations

import asyncio

from rich.console import Console

from .. import config
from ..scrapers.base import all_scrapers
from ..scrapers.mock import MockScraper
from ..state import GraphState

console = Console(stderr=True)


async def scrape_node(state: GraphState) -> GraphState:
    query = state["query"]
    options = state.get("options", {})

    if options.get("mock"):
        scrapers = [MockScraper(headless=config.HEADLESS)]
    else:
        scrapers = [S(headless=config.HEADLESS) for S in all_scrapers()]

    results = await asyncio.gather(
        *[s.scrape(query) for s in scrapers], return_exceptions=True
    )

    raw = []
    for scraper, result in zip(scrapers, results):
        if isinstance(result, Exception):
            console.log(f"[yellow]scrape[/]: portal '{scraper.name}' falhou: {result}")
            continue
        console.log(f"[green]scrape[/]: '{scraper.name}' retornou {len(result)} imóveis")
        raw.extend(result)

    return {"raw_listings": raw}
