"""Servidor MCP (Model Context Protocol) para o Deep-Research Imobiliário.

Expõe duas ferramentas para Claude Desktop (ou qualquer cliente MCP):

  • pesquisar_mercado   — pipeline completo (scraping + análise + relatório)
  • buscar_semantico    — busca no histórico Chroma sem scraping (instantâneo)

Para registrar no Claude Desktop, adicione ao claude_desktop_config.json:

    {
      "mcpServers": {
        "imobiliario": {
          "command": "python",
          "args": ["-m", "deep_research.mcp_server"],
          "cwd": "<caminho>/lastro_hackathon/src"
        }
      }
    }
"""

from __future__ import annotations

from typing import Optional

from mcp.server.fastmcp import FastMCP

from .graph import build_graph
from .models import Query
from .search import _extract_filters, _merge_filters, _where
from . import store

import argparse

mcp = FastMCP("Pesquisa Imobiliária")


# ──────────────────────────────────────────────────────────────────────────────
# Ferramenta 1 — pipeline completo
# ──────────────────────────────────────────────────────────────────────────────

@mcp.tool()
async def pesquisar_mercado(
    cidade: str,
    bairro: str,
    operacao: str = "aluguel",
    tipo: str = "ambos",
    preco_min: Optional[int] = None,
    preco_max: Optional[int] = None,
    quartos_min: Optional[int] = None,
    uf: str = "sp",
    zona: Optional[str] = None,
    paginas: int = 5,
    mock: bool = False,
) -> str:
    """Pesquisa imóveis nos principais portais (OLX, ZAP, QuintoAndar) e retorna
    um relatório de mercado em Markdown com estatísticas de preço, R$/m² e
    oportunidades abaixo da mediana.

    Use mock=True para testar sem fazer scraping real.
    """
    query = Query(
        cidade=cidade,
        bairro=bairro,
        operacao=operacao,
        tipo=tipo,
        preco_min=preco_min,
        preco_max=preco_max,
        quartos_min=quartos_min,
        uf=uf,
        zona=zona,
        max_paginas=paginas,
    )
    app = build_graph()
    final = await app.ainvoke({"query": query, "options": {"mock": mock}})
    return final.get("report", "(sem relatório)")


# ──────────────────────────────────────────────────────────────────────────────
# Ferramenta 2 — busca semântica no histórico
# ──────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def buscar_semantico(
    texto: str,
    n: int = 10,
    operacao: Optional[str] = None,
    tipo: Optional[str] = None,
    cidade: Optional[str] = None,
    bairro: Optional[str] = None,
    preco_min: Optional[int] = None,
    preco_max: Optional[int] = None,
) -> str:
    """Busca imóveis no histórico local usando linguagem natural, sem fazer scraping.

    Detecta automaticamente cidade, operação, tipo e faixa de preço do texto.
    Requer que pesquisas anteriores tenham sido feitas com USE_CHROMA=true.

    Exemplos de texto:
      "apartamento 2 quartos para alugar em Osasco até R$ 2000"
      "casa com quintal no Pinheiros para comprar"
      "studio barato perto do metrô em São Paulo"
    """
    total = store.count()
    if total == 0:
        return "Histórico vazio. Faça pesquisas com USE_CHROMA=true para popular o banco de imóveis."

    # Infere filtros do texto; parâmetros explícitos têm prioridade
    ns = argparse.Namespace(
        texto=texto,
        operacao=operacao,
        tipo=tipo,
        cidade=cidade.lower() if cidade else None,
        bairro=bairro,
        preco_min=preco_min,
        preco_max=preco_max,
    )
    inferidos = _extract_filters(texto)
    quartos_min = inferidos.pop("quartos_min", None)
    ns = _merge_filters(ns, inferidos)

    resultados = store.search(texto, n=n, where=_where(ns, quartos_min))

    if not resultados:
        return "Nenhum imóvel encontrado com esses critérios no histórico."

    def _brl(v) -> str:
        return f"R$ {v:,.0f}".replace(",", ".") if v else "—"

    linhas = [f"**{len(resultados)} imóveis encontrados** (de {total} no histórico)\n"]
    linhas.append("| Sim. | Tipo | Operação | Preço | Bairro | Cidade |")
    linhas.append("|------|------|----------|-------|--------|--------|")

    for r in resultados:
        md = r["metadata"]
        sim = max(0.0, 1 - r["distancia"] / 2)
        linhas.append(
            f"| {sim:.2f} | {md.get('tipo') or '—'} | {md.get('operacao') or '—'} "
            f"| {_brl(md.get('preco'))} | {md.get('bairro') or '—'} | {md.get('cidade') or '—'} |"
        )

    linhas.append("\n**Links:**")
    for r in resultados:
        desc = (r["documento"] or r["url"])[:60]
        linhas.append(f"- [{desc}]({r['url']})")

    return "\n".join(linhas)


# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
