"""Busca semântica no histórico de imóveis (Chroma + embeddings locais).

Consulta os dados **já coletados** em buscas anteriores (não faz scraping). O
histórico é populado pelo pipeline quando `USE_CHROMA=true`.

Uso:
    python -m deep_research.search --texto "apê reformado perto do metrô"
    python -m deep_research.search --texto "casa com quintal" --operacao aluguel --bairro Pinheiros
"""

from __future__ import annotations

import argparse
import sys

from rich.console import Console
from rich.table import Table

from . import config, store

# Garante UTF-8 na saída (terminais Windows usam cp1252 por padrão).
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def _args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Busca semântica no histórico de imóveis já coletados."
    )
    p.add_argument("--texto", required=True, help="consulta em linguagem natural")
    p.add_argument("--n", type=int, default=10, help="nº de resultados")
    p.add_argument("--operacao", choices=["venda", "aluguel"], default=None)
    p.add_argument("--tipo", choices=["apartamento", "casa"], default=None)
    p.add_argument("--bairro", default=None)
    p.add_argument("--cidade", default=None)
    p.add_argument("--min", type=int, default=None, dest="preco_min",
                   help="preço/aluguel mínimo (filtro exato, não semântico)")
    p.add_argument("--max", type=int, default=None, dest="preco_max",
                   help="preço/aluguel máximo (filtro exato, não semântico)")
    return p.parse_args()


def _where(args: argparse.Namespace) -> dict | None:
    """Monta o filtro de metadados do Chroma a partir das flags.

    Preço é tratado aqui (filtro estruturado), e NÃO no texto da busca — a
    similaridade vetorial não entende faixas numéricas.
    """
    cond: list[dict] = []
    if args.operacao:
        cond.append({"operacao": args.operacao})
    if args.tipo:
        cond.append({"tipo": args.tipo})
    if args.bairro:
        cond.append({"bairro": args.bairro})
    if args.cidade:
        cond.append({"cidade": args.cidade})
    if args.preco_min is not None:
        cond.append({"preco": {"$gte": args.preco_min}})
    if args.preco_max is not None:
        cond.append({"preco": {"$lte": args.preco_max}})

    if not cond:
        return None
    if len(cond) == 1:
        return cond[0]
    # múltiplas condições exigem $and no Chroma
    return {"$and": cond}


def _fmt_brl(valor) -> str:
    if valor in (None, ""):
        return "—"
    return f"R$ {valor:,.0f}".replace(",", ".")


def main() -> None:
    args = _args()
    console = Console(legacy_windows=False)

    try:
        total = store.count()
    except Exception as exc:
        console.print(f"[red]Erro ao abrir o histórico (Chroma): {exc}[/]")
        return

    if total == 0:
        console.print(
            "[yellow]Histórico vazio.[/] Rode buscas com USE_CHROMA=true para "
            "popular o repositório antes de pesquisar."
        )
        return

    console.rule(f"[bold]Busca semântica — “{args.texto}”")

    try:
        resultados = store.search(args.texto, n=args.n, where=_where(args))
    except Exception as exc:
        console.print(f"[red]Falha na busca (embeddings: {config.EMBED_BACKEND}): {exc}[/]")
        console.print("Verifique se o Ollama está rodando e o modelo foi baixado "
                      "(`ollama pull <modelo>`), ou use EMBED_BACKEND=default.")
        return

    if not resultados:
        console.print("[yellow]Nenhum imóvel correspondente no histórico.[/]")
        return

    tabela = Table(title=f"{len(resultados)} de {total} imóveis no histórico")
    tabela.add_column("Sim.", justify="right")
    tabela.add_column("Operação")
    tabela.add_column("Tipo")
    tabela.add_column("Preço", justify="right")
    tabela.add_column("Bairro")
    tabela.add_column("Descrição")

    for r in resultados:
        md = r["metadata"]
        # distância de cosseno -> similaridade aproximada (0..1)
        sim = max(0.0, 1 - r["distancia"] / 2)
        tabela.add_row(
            f"{sim:.2f}",
            str(md.get("operacao") or "—"),
            str(md.get("tipo") or "—"),
            _fmt_brl(md.get("preco")),
            str(md.get("bairro") or "—"),
            (r["documento"] or "")[:70],
        )

    console.print(tabela)
    console.print("\n[dim]Links:[/]")
    for r in resultados[:5]:
        console.print(f"  {r['url']}")


if __name__ == "__main__":
    main()
