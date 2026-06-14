"""Interface Streamlit para o Deep-Research Imobiliário."""

from __future__ import annotations

import asyncio
import threading

import streamlit as st

st.set_page_config(
    page_title="Pesquisa de Mercado Imobiliário",
    page_icon="🏠",
    layout="wide",
)

# ── imports lazy ───────────────────────────────────────────────────────────────
@st.cache_resource
def _load_graph():
    from deep_research.graph import build_graph
    return build_graph()


def _run_async(coro):
    """Executa coroutine em thread separada (evita conflito de event loop)."""
    result: dict = {"value": None, "error": None}

    def _target():
        try:
            result["value"] = asyncio.run(coro)
        except Exception as exc:
            result["error"] = exc

    t = threading.Thread(target=_target, daemon=True)
    t.start()
    t.join()
    if result["error"]:
        raise result["error"]
    return result["value"]


async def _invoke(query, options: dict) -> str:
    app = _load_graph()
    final = await app.ainvoke({"query": query, "options": options})
    return final.get("report", "(sem relatório)")


# ── navegação por abas ─────────────────────────────────────────────────────────
aba_pesquisa, aba_historico = st.tabs(["🔍 Nova Pesquisa", "📚 Busca no Histórico"])


# ==============================================================================
# ABA 1 — Nova Pesquisa (scraping completo)
# ==============================================================================
with aba_pesquisa:
    col_form, col_resultado = st.columns([1, 2], gap="large")

    with col_form:
        st.subheader("Parâmetros")

        cidade = st.text_input("Cidade", value="São Paulo", key="p_cidade")
        bairro = st.text_input("Bairro", value="Vila Madalena", key="p_bairro")
        uf     = st.text_input("Estado (UF)", value="sp", max_chars=2, key="p_uf").lower()

        operacao = st.radio("Operação", ["aluguel", "venda"], horizontal=True, key="p_op")
        tipo     = st.selectbox("Tipo de imóvel", ["ambos", "apartamento", "casa"], key="p_tipo")

        c1, c2 = st.columns(2)
        with c1:
            preco_min = st.number_input("Preço mín. (R$)", min_value=0, value=1_200, step=100, key="p_min")
        with c2:
            preco_max = st.number_input("Preço máx. (R$)", min_value=0, value=5_000, step=100, key="p_max")

        quartos_min = st.number_input("Quartos (mín.)", min_value=0, value=1, step=1, key="p_qtos")
        zona        = st.text_input("Zona (opcional)", placeholder="ex.: zona-sul", key="p_zona")
        paginas     = st.slider("Páginas por portal", 1, 10, 5, key="p_pag")

        manter_outliers = st.toggle("Manter outliers de R$/m²", value=False, key="p_out")
        mock            = st.toggle("Modo demo (sem rede)", value=False, key="p_mock")

        pesquisar = st.button("Pesquisar", use_container_width=True, type="primary", key="p_btn")

    with col_resultado:
        st.subheader("Relatório")

        if not pesquisar:
            st.info("Preencha os parâmetros ao lado e clique em **Pesquisar**.")
        else:
            erros: list[str] = []
            if not cidade.strip():
                erros.append("Informe a cidade.")
            if not bairro.strip():
                erros.append("Informe o bairro.")
            if preco_max and preco_min and preco_max < preco_min:
                erros.append("Preço máximo deve ser maior que o mínimo.")

            if erros:
                for e in erros:
                    st.error(e)
            else:
                with st.spinner(f"Pesquisando em {bairro}, {cidade}… pode levar alguns minutos."):
                    from deep_research.models import Query

                    query = Query(
                        cidade=cidade.strip(),
                        bairro=bairro.strip(),
                        operacao=operacao,
                        preco_min=int(preco_min) or None,
                        preco_max=int(preco_max) or None,
                        tipo=tipo,
                        quartos_min=int(quartos_min) or None,
                        uf=uf.strip(),
                        zona=zona.strip() or None,
                        max_paginas=paginas,
                        filtrar_outliers=not manter_outliers,
                    )

                    try:
                        report = _run_async(_invoke(query, {"mock": mock}))
                        st.success("Relatório gerado!")
                        st.markdown(report)
                        st.download_button(
                            "⬇️ Baixar como .md",
                            data=report.encode("utf-8"),
                            file_name=f"relatorio_{cidade.lower().replace(' ','_')}_{bairro.lower().replace(' ','_')}.md",
                            mime="text/markdown",
                        )
                    except Exception as exc:
                        st.error(f"Erro durante a pesquisa: {exc}")


# ==============================================================================
# ABA 2 — Busca no Histórico (semântica, sem scraping)
# ==============================================================================
with aba_historico:
    st.subheader("Busca semântica no histórico")
    st.caption(
        "Consulta imóveis já coletados em buscas anteriores. "
        "Basta descrever em português — os filtros são detectados automaticamente."
    )

    col_h_form, col_h_result = st.columns([1, 2], gap="large")

    with col_h_form:
        texto = st.text_area(
            "Descreva o que procura",
            placeholder=(
                "ex.: apartamento 2 quartos para alugar em Osasco até R$ 2.000\n"
                "ex.: casa com quintal no Pinheiros\n"
                "ex.: studio perto do metrô para comprar"
            ),
            height=130,
            key="h_texto",
        )
        n_resultados = st.slider("Nº de resultados", 5, 30, 10, key="h_n")

        with st.expander("Filtros manuais (opcional — sobrescrevem o texto)"):
            hc1, hc2 = st.columns(2)
            with hc1:
                h_cidade   = st.text_input("Cidade", key="h_cidade")
                h_bairro   = st.text_input("Bairro", key="h_bairro")
                h_operacao = st.selectbox("Operação", ["(qualquer)", "aluguel", "venda"], key="h_op")
            with hc2:
                h_tipo     = st.selectbox("Tipo", ["(qualquer)", "apartamento", "casa"], key="h_tipo")
                h_min      = st.number_input("Preço mín.", min_value=0, value=0, step=100, key="h_min")
                h_max      = st.number_input("Preço máx.", min_value=0, value=0, step=100, key="h_max")

        buscar = st.button("Buscar no histórico", use_container_width=True, type="primary", key="h_btn")

    with col_h_result:
        if not buscar:
            st.info("Digite o que procura e clique em **Buscar no histórico**.")
        elif not texto.strip():
            st.error("Digite algo no campo de busca.")
        else:
            from deep_research.search import _extract_filters, _merge_filters, _where
            import argparse, types

            # Monta namespace simulando argparse com os valores do formulário
            ns = argparse.Namespace(
                texto=texto,
                operacao=h_operacao if h_operacao != "(qualquer)" else None,
                tipo=h_tipo if h_tipo != "(qualquer)" else None,
                cidade=h_cidade.strip().lower() or None,
                bairro=h_bairro.strip() or None,
                preco_min=int(h_min) or None,
                preco_max=int(h_max) or None,
            )

            # Infere filtros do texto (flags manuais têm prioridade)
            inferidos = _extract_filters(texto)
            quartos_min = inferidos.pop("quartos_min", None)
            ns = _merge_filters(ns, inferidos)

            # Mostra filtros ativos
            ativos = {k: getattr(ns, k) for k in ("operacao", "tipo", "cidade", "bairro", "preco_min", "preco_max") if getattr(ns, k)}
            if quartos_min:
                ativos["quartos_min"] = quartos_min
            if ativos:
                st.info("Filtros aplicados: " + "  •  ".join(f"**{k}** = {v}" for k, v in ativos.items()))

            try:
                from deep_research import store, config

                total = store.count()
                if total == 0:
                    st.warning("Histórico vazio. Faça pesquisas com **USE_CHROMA=true** para populá-lo.")
                else:
                    with st.spinner("Buscando…"):
                        resultados = store.search(texto, n=n_resultados, where=_where(ns, quartos_min))

                    if not resultados:
                        st.warning("Nenhum imóvel encontrado com esses critérios.")
                    else:
                        st.success(f"{len(resultados)} imóveis encontrados (de {total} no histórico)")

                        import pandas as pd

                        def _brl(v):
                            return f"R$ {v:,.0f}".replace(",", ".") if v else "—"

                        rows = []
                        for r in resultados:
                            md = r["metadata"]
                            sim = max(0.0, 1 - r["distancia"] / 2)
                            rows.append({
                                "Sim.": f"{sim:.2f}",
                                "Operação": md.get("operacao") or "—",
                                "Tipo": md.get("tipo") or "—",
                                "Preço": _brl(md.get("preco")),
                                "Bairro": md.get("bairro") or "—",
                                "Cidade": md.get("cidade") or "—",
                                "Descrição": (r["documento"] or "")[:80],
                                "URL": r["url"],
                            })

                        df = pd.DataFrame(rows)
                        st.dataframe(
                            df.drop(columns=["URL"]),
                            use_container_width=True,
                            hide_index=True,
                        )

                        st.subheader("Links")
                        for r in resultados:
                            md = r["metadata"]
                            label = (r["documento"] or r["url"])[:60]
                            st.markdown(f"- [{label}]({r['url']})")

            except Exception as exc:
                st.error(f"Erro na busca: {exc}")
                if "embed" in str(exc).lower() or "ollama" in str(exc).lower():
                    st.info("Verifique se o Ollama está rodando, ou use `EMBED_BACKEND=default` no `.env`.")
