"""Nó `report`: monta o relatório final em Markdown (puro Python)."""

from __future__ import annotations

from ..models import Listing, MarketAnalysis, Opportunity
from ..state import GraphState


def _fmt_brl(valor) -> str:
    if valor is None:
        return "—"
    return f"R$ {valor:,.0f}".replace(",", ".")


TABELA_MAX = 25


def _bloco_segmento(analysis: MarketAnalysis, ranking: list[Opportunity], titulo_seg: str, termo: str, unidade_m2: str) -> list[str]:
    """Resumo de mercado + oportunidades de um segmento."""
    out = [f"## Mercado — {titulo_seg}\n"]
    out.append(f"- **Imóveis analisados:** {analysis.total_imoveis}")
    out.append(f"- **{termo} médio:** {_fmt_brl(analysis.preco_medio)}")
    out.append(f"- **{termo} mediano:** {_fmt_brl(analysis.preco_mediano)}")
    out.append(f"- **Faixa observada:** {_fmt_brl(analysis.preco_min)} – {_fmt_brl(analysis.preco_max)}")
    out.append(f"- **{unidade_m2} médio:** {analysis.preco_m2_medio or '—'}\n")
    out.append(f"> {analysis.observacoes}\n")

    out.append(f"### Oportunidades — {titulo_seg}\n")
    if ranking:
        for i, opp in enumerate(ranking, 1):
            out.append(
                f"{i}. **{opp.titulo or opp.url}** — {_fmt_brl(opp.preco)} "
                f"(R$/m² {opp.preco_m2})\n   {opp.justificativa}\n   [{opp.url}]({opp.url})\n"
            )
    else:
        out.append("_Sem oportunidades destacadas._\n")
    return out


def _tabela(listings: list[Listing], com_tipo: bool) -> str:
    if not listings:
        return "_Nenhum imóvel encontrado._\n"
    ordenados = sorted(listings, key=lambda x: (x.preco_m2 or 1e18))
    mostradas = ordenados[:TABELA_MAX]

    if com_tipo:
        linhas = [
            "| Tipo | Preço | Área | Quartos | R$/m² | Portal | Link |",
            "|:-----|------:|-----:|:-------:|------:|:------:|------|",
        ]
        for l in mostradas:
            linhas.append(
                f"| {l.tipo or '—'} | {_fmt_brl(l.preco)} | {l.area or '—'} m² | "
                f"{l.quartos or '—'} | {l.preco_m2 or '—'} | {l.portal} | [ver]({l.url}) |"
            )
    else:
        linhas = [
            "| Preço | Área | Quartos | R$/m² | Portal | Link |",
            "|------:|-----:|:-------:|------:|:------:|------|",
        ]
        for l in mostradas:
            linhas.append(
                f"| {_fmt_brl(l.preco)} | {l.area or '—'} m² | {l.quartos or '—'} | "
                f"{l.preco_m2 or '—'} | {l.portal} | [ver]({l.url}) |"
            )

    out = "\n".join(linhas) + "\n"
    if len(ordenados) > TABELA_MAX:
        out += f"\n_Mostrando os {TABELA_MAX} melhores R$/m² de {len(ordenados)} imóveis._\n"
    return out


def report_node(state: GraphState) -> GraphState:
    query = state["query"]
    listings = state.get("listings", [])
    analyses = state.get("analyses", [])
    rankings = state.get("rankings", {})

    segmentado = len(analyses) > 1
    aluguel = query.operacao == "aluguel"
    termo = "Aluguel" if aluguel else "Preço"
    unidade_m2 = "R$/m²/mês" if aluguel else "R$/m²"
    faixa = f"{_fmt_brl(query.preco_min)} – {_fmt_brl(query.preco_max)}"

    out = [f"# Deep-Research Imobiliário — {query.bairro}, {query.cidade}\n"]
    out.append(f"**Operação:** {query.operacao}  |  **Tipo:** {query.tipo}  |  **Faixa de {termo.lower()}:** {faixa}\n")

    for analysis in analyses:
        titulo_seg = analysis.segmento.capitalize()
        ranking = rankings.get(analysis.segmento, [])
        out.extend(_bloco_segmento(analysis, ranking, titulo_seg, termo, unidade_m2))

    out.append("## Todas as listagens\n")
    out.append(_tabela(listings, com_tipo=segmentado))

    outliers = state.get("outliers_removidos", 0)
    if outliers:
        out.append(
            f"\n_{outliers} anúncio(s) com R$/m² anômalo foram removidos por segmento "
            f"(filtro de outliers; use `--manter-outliers` para mantê-los)._\n"
        )

    return {"report": "\n".join(out)}
