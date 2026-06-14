"""Interface Streamlit para o Deep-Research Imobiliário."""

from __future__ import annotations

import asyncio
import threading
from typing import Optional

import streamlit as st

# ── page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Pesquisa de Mercado Imobiliário",
    page_icon="🏠",
    layout="wide",
)

# ── imports do projeto (lazy para não travar o boot do Streamlit) ──────────────
@st.cache_resource
def _load_graph():
    from deep_research.graph import build_graph
    return build_graph()


def _run_async(coro):
    """Executa uma coroutine em uma thread separada (evita conflito de event loop)."""
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


# ── sidebar: formulário ────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🏠 Pesquisa Imobiliária")
    st.caption("Preencha os filtros e clique em **Pesquisar**.")

    cidade = st.text_input("Cidade", value="São Paulo")
    bairro = st.text_input("Bairro", value="Vila Madalena")
    uf     = st.text_input("Estado (UF)", value="sp", max_chars=2).lower()

    operacao = st.radio("Operação", ["aluguel", "venda"], horizontal=True)
    tipo     = st.selectbox("Tipo de imóvel", ["ambos", "apartamento", "casa"])

    col1, col2 = st.columns(2)
    with col1:
        preco_min = st.number_input("Preço mínimo (R$)", min_value=0, value=1_200, step=100)
    with col2:
        preco_max = st.number_input("Preço máximo (R$)", min_value=0, value=5_000, step=100)

    quartos_min = st.number_input("Quartos (mín.)", min_value=0, value=1, step=1)
    zona        = st.text_input("Zona (opcional)", placeholder="ex.: zona-sul")
    paginas     = st.slider("Páginas por portal", 1, 10, 5)

    manter_outliers = st.toggle("Manter outliers de R$/m²", value=False)
    mock            = st.toggle("Modo demo (sem rede)", value=False)

    st.divider()
    pesquisar = st.button("🔍 Pesquisar", use_container_width=True, type="primary")

# ── área principal ─────────────────────────────────────────────────────────────
st.title("Relatório de Mercado Imobiliário")

if not pesquisar:
    st.info("Configure os filtros na barra lateral e clique em **Pesquisar** para gerar o relatório.")
    st.stop()

# validações simples
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
    st.stop()

# execução
with st.spinner(f"Pesquisando imóveis em {bairro}, {cidade}… isso pode levar alguns minutos."):
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
    except Exception as exc:
        st.error(f"Erro durante a pesquisa: {exc}")
        st.stop()

# resultado
st.success("Relatório gerado com sucesso!")
st.markdown(report)

st.divider()
st.download_button(
    label="⬇️ Baixar relatório (.md)",
    data=report.encode("utf-8"),
    file_name=f"relatorio_{cidade.lower().replace(' ', '_')}_{bairro.lower().replace(' ', '_')}.md",
    mime="text/markdown",
)
