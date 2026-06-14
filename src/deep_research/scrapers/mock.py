"""Scraper sintético — gera dados determinísticos para demo/teste sem rede.

Permite validar o pipeline (grafo -> análise LLM -> relatório) end-to-end
sem depender de scraping real nem driblar anti-bot.
"""

from __future__ import annotations

from typing import List

from ..models import Listing, Query


class MockScraper:
    name = "mock"

    def __init__(self, headless: bool = True):
        self.headless = headless

    async def scrape(self, query: Query) -> List[Listing]:
        base = query.preco_min or 400_000
        step = max(((query.preco_max or base + 600_000) - base) // 8, 25_000)
        listings: List[Listing] = []
        for i in range(8):
            preco = base + step * i
            area = 45 + i * 9  # m²
            # em modo "ambos", alterna casa/apartamento para demonstrar a segmentação
            tipo = ("casa" if i % 2 else "apartamento") if query.tipo == "ambos" else query.tipo
            listings.append(
                Listing(
                    portal="mock",
                    url=f"https://example.com/imovel/{i + 1}",
                    titulo=f"{tipo.capitalize()} {2 + (i % 3)} quartos em {query.bairro}",
                    tipo=tipo,
                    preco=preco,
                    area=float(area),
                    quartos=2 + (i % 3),
                    banheiros=1 + (i % 2),
                    vagas=i % 3,
                    bairro=query.bairro,
                    endereco=f"Rua Exemplo {100 + i}, {query.bairro}, {query.cidade}",
                    descricao=(
                        f"{query.tipo.capitalize()} reformado com {area} m², "
                        f"próximo a comércio e transporte em {query.bairro}."
                    ),
                )
            )
        return listings
