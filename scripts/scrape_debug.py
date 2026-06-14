"""Diagnóstico de scraping: navega num portal e reporta o que foi obtido.

Uso:
    PYTHONPATH=src python scripts/scrape_debug.py vivareal
    PYTHONPATH=src python scripts/scrape_debug.py quintoandar
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from deep_research.models import Query  # noqa: E402
from deep_research.scrapers.base import USER_AGENT, all_scrapers  # noqa: E402
import deep_research.scrapers  # noqa: E402,F401  (registra os scrapers)

QUERY = Query(
    cidade="São Paulo", bairro="Pinheiros",
    preco_min=400000, preco_max=800000, tipo="apartamento", max_paginas=1,
)


async def main(portal: str) -> None:
    from playwright.async_api import async_playwright

    scraper_cls = {s.name: s for s in all_scrapers()}.get(portal)
    if not scraper_cls:
        print(f"portal desconhecido: {portal}. Opções: {[s.name for s in all_scrapers()]}")
        return

    scraper = scraper_cls(headless=True)
    url = scraper.build_url(QUERY, 1)
    print(f"URL construída: {url}\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(user_agent=USER_AGENT, locale="pt-BR",
                                        viewport={"width": 1366, "height": 900})
        page = await ctx.new_page()
        try:
            resp = await page.goto(url, timeout=45000, wait_until="domcontentloaded")
            await asyncio.sleep(3)
            print(f"HTTP status   : {resp.status if resp else '?'}")
            print(f"URL final     : {page.url}")
            print(f"Título        : {await page.title()}")

            # Quantos cards o seletor atual encontra?
            from deep_research.scrapers import vivareal, quintoandar  # noqa
            sel = getattr(sys.modules[scraper_cls.__module__], "SEL_CARD", "article")
            cards = await page.query_selector_all(sel)
            print(f"SEL_CARD      : {sel}")
            print(f"Cards casados : {len(cards)}")

            # Sinais de bloqueio / captcha
            body = (await page.inner_text("body"))[:400].replace("\n", " ")
            print(f"\nPrévia do body:\n{body}\n")

            if cards:
                html = await cards[0].inner_html()
                print("\n--- HTML do 1º card (2000 chars) ---")
                print(html[:2000])
                print("--- fim ---\n")

            listings = await scraper.parse(page, QUERY)
            print(f"Listings extraídos pelo scraper: {len(listings)}")
            for l in listings[:3]:
                print(f"  - {l.preco} | {l.area} m² | {l.quartos}q | {l.url}")

            await page.screenshot(path=str(ROOT / f"debug_{portal}.png"))
            print(f"\nScreenshot salvo em debug_{portal}.png")
        finally:
            await browser.close()


if __name__ == "__main__":
    portal = sys.argv[1] if len(sys.argv) > 1 else "vivareal"
    asyncio.run(main(portal))
