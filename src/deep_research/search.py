"""Busca semântica no histórico de imóveis (Chroma + embeddings locais).

Consulta os dados **já coletados** em buscas anteriores (não faz scraping). O
histórico é populado pelo pipeline quando `USE_CHROMA=true`.

Uso (texto livre — flags são opcionais):
    python -m deep_research.search --texto "apê reformado perto do metrô em Pinheiros"
    python -m deep_research.search --texto "casa com quintal para alugar até R$ 3000"
    python -m deep_research.search --texto "studio 1 quarto para comprar em Osasco"
"""

from __future__ import annotations

import argparse
import re
import sys

from rich.console import Console
from rich.table import Table

from . import config, store

# Garante UTF-8 na saída (terminais Windows usam cp1252 por padrão).
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


# ---------------------------------------------------------------------------
# Extração de filtros a partir do texto livre
# ---------------------------------------------------------------------------

def _extract_filters(texto: str) -> dict:
    """Infere filtros de metadados a partir do texto da busca.

    Retorna um dict com as chaves encontradas (operacao, tipo, cidade,
    preco_min, preco_max, quartos_min). Qualquer flag explícita do CLI
    tem prioridade e sobrescreve o que for inferido aqui.
    """
    t = texto.lower()
    filtros: dict = {}

    # operação: alugar / vender
    if re.search(r'\b(alug|aluguel|locação|locaç)\w*\b', t):
        filtros["operacao"] = "aluguel"
    elif re.search(r'\b(compr|vend|comprar|venda|aquisição)\w*\b', t):
        filtros["operacao"] = "venda"

    # tipo: apartamento ou casa
    if re.search(r'\b(apartamento|apto|studio|stúdio|kitnet|flat|cobertura|loft)\w*\b', t):
        filtros["tipo"] = "apartamento"
    elif re.search(r'\b(casa|sobrado|térrea|terrea|geminada)\w*\b', t):
        filtros["tipo"] = "casa"

    # quartos mínimos: "2 quartos", "1 dormitório", "3 dorms"
    m = re.search(r'(\d+)\s*(quarto|dormitório|dorm)\w*', t)
    if m:
        filtros["quartos_min"] = int(m.group(1))

    # preço máximo: "até R$ 2.000", "máximo 3000", "por até 1500"
    m = re.search(r'(?:até|max|máx|menos de|por até)\s*r?\$?\s*([\d.,]+)', t)
    if m:
        filtros["preco_max"] = int(re.sub(r'[.,]', '', m.group(1)))

    # preço mínimo: "a partir de R$ 1.000", "mínimo 800"
    m = re.search(r'(?:a partir de|mínimo|min|acima de)\s*r?\$?\s*([\d.,]+)', t)
    if m:
        filtros["preco_min"] = int(re.sub(r'[.,]', '', m.group(1)))

    # cidade: "em Osasco", "em São Paulo", "no Centro" — captura o nome próprio após a preposição
    m = re.search(
        r'\bem\s+([A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇ][a-zA-ZÁÉÍÓÚÂÊÎÔÛÃÕÇáéíóúâêîôûãõç\s]{2,35}?)(?:\s*$|\s*,|\.|\se\sregião|\spara\s|\scom\s|\s\d)',
        texto,
        re.IGNORECASE,
    )
    if m:
        filtros["cidade"] = m.group(1).strip().lower()

    return filtros


def _merge_filters(args: argparse.Namespace, inferidos: dict) -> argparse.Namespace:
    """Flags explícitas do CLI têm prioridade; inferidos preenchem o que está vazio."""
    for chave, valor in inferidos.items():
        attr = chave  # "cidade", "operacao", "tipo", "preco_min", "preco_max"
        if chave == "quartos_min":
            # quartos_min não existe no argparse original — ignora para _where
            continue
        if getattr(args, attr, None) is None:
            setattr(args, attr, valor)
    return args


# ---------------------------------------------------------------------------
# Filtro de metadados para o Chroma
# ---------------------------------------------------------------------------

def _where(args: argparse.Namespace, quartos_min: int | None = None) -> dict | None:
    """Monta o filtro de metadados do Chroma.

    Preço é tratado aqui (filtro estruturado), e NÃO no texto da busca — a
    similaridade vetorial não entende faixas numéricas.
    """
    cond: list[dict] = []
    if getattr(args, "operacao", None):
        cond.append({"operacao": args.operacao})
    if getattr(args, "tipo", None):
        cond.append({"tipo": args.tipo})
    if getattr(args, "bairro", None):
        cond.append({"bairro": args.bairro})
    if getattr(args, "cidade", None):
        cond.append({"cidade": args.cidade})
    if getattr(args, "preco_min", None) is not None:
        cond.append({"preco": {"$gte": args.preco_min}})
    if getattr(args, "preco_max", None) is not None:
        cond.append({"preco": {"$lte": args.preco_max}})
    if quartos_min is not None:
        cond.append({"quartos": {"$gte": quartos_min}})

    if not cond:
        return None
    if len(cond) == 1:
        return cond[0]
    return {"$and": cond}


# ---------------------------------------------------------------------------
# Helpers de formatação
# ---------------------------------------------------------------------------

def _fmt_brl(valor) -> str:
    if valor in (None, ""):
        return "—"
    return f"R$ {valor:,.0f}".replace(",", ".")


def _args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Busca semântica no histórico. Flags são opcionais — o texto "
                    "já é suficiente: 'apê 2 quartos para alugar em Osasco até R$ 2000'."
    )
    p.add_argument("--texto", required=True, help="consulta em linguagem natural")
    p.add_argument("--n", type=int, default=10, help="nº de resultados")
    p.add_argument("--operacao", choices=["venda", "aluguel"], default=None)
    p.add_argument("--tipo", choices=["apartamento", "casa"], default=None)
    p.add_argument("--bairro", default=None)
    p.add_argument("--cidade", default=None)
    p.add_argument("--min", type=int, default=None, dest="preco_min")
    p.add_argument("--max", type=int, default=None, dest="preco_max")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

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

    # Infere filtros do texto e mescla com flags explícitas (flags têm prioridade).
    inferidos = _extract_filters(args.texto)
    quartos_min = inferidos.pop("quartos_min", None)
    args = _merge_filters(args, inferidos)

    # Mostra quais filtros foram aplicados automaticamente.
    ativos = {k: getattr(args, k, None) for k in ("operacao", "tipo", "cidade", "bairro", "preco_min", "preco_max")}
    ativos = {k: v for k, v in ativos.items() if v is not None}
    if quartos_min:
        ativos["quartos_min"] = quartos_min
    if ativos:
        resumo = "  ".join(f"[cyan]{k}[/]=[yellow]{v}[/]" for k, v in ativos.items())
        console.print(f"[dim]Filtros detectados:[/] {resumo}")

    console.rule(f"[bold]Busca semântica — '{args.texto}'")

    try:
        resultados = store.search(args.texto, n=args.n, where=_where(args, quartos_min))
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
