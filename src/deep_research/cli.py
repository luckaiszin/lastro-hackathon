"""Entrypoint CLI: bairro + faixa de preço -> relatório de mercado."""

from __future__ import annotations

import argparse
import asyncio
import sys

from rich.console import Console
from rich.markdown import Markdown

# Garante UTF-8 na saída (terminais Windows usam cp1252 por padrão).
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from .graph import build_graph
from .models import Query


def _args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Deep-research de mercado imobiliário por bairro e faixa de preço."
    )
    p.add_argument("--cidade", required=True)
    p.add_argument("--bairro", required=True)
    p.add_argument("--operacao", default="venda", choices=["venda", "aluguel"],
                   help="venda | aluguel")
    p.add_argument("--min", type=int, default=None, help="preço mínimo (R$)")
    p.add_argument("--max", type=int, default=None, help="preço máximo (R$)")
    p.add_argument("--tipo", default="apartamento", help="apartamento | casa | ambos")
    p.add_argument("--quartos-min", type=int, default=None)
    p.add_argument("--uf", default="sp", help="estado, ex.: sp (usado por OLX/ZAP)")
    p.add_argument("--zona", default=None, help="zona da cidade, ex.: zona-oeste (OLX/ZAP)")
    p.add_argument("--paginas", type=int, default=5, help="máx. de páginas por portal")
    p.add_argument("--manter-outliers", action="store_true",
                   help="não remove R$/m² anômalos (por padrão são filtrados)")
    p.add_argument("--mock", action="store_true", help="usa dados sintéticos (sem rede/API)")
    return p.parse_args()


async def run(query: Query, options: dict) -> str:
    app = build_graph()
    final = await app.ainvoke({"query": query, "options": options})
    return final.get("report", "(sem relatório)")


def main() -> None:
    args = _args()
    # legacy_windows=False evita o renderer cp1252 do console antigo do Windows.
    console = Console(legacy_windows=False)

    query = Query(
        cidade=args.cidade,
        bairro=args.bairro,
        operacao=args.operacao,
        preco_min=args.min,
        preco_max=args.max,
        tipo=args.tipo,
        quartos_min=args.quartos_min,
        uf=args.uf,
        zona=args.zona,
        max_paginas=args.paginas,
        filtrar_outliers=not args.manter_outliers,
    )

    console.rule("[bold]Deep-Research Imobiliário")
    report = asyncio.run(run(query, {"mock": args.mock}))
    console.print(Markdown(report))


if __name__ == "__main__":
    main()
