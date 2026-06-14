"""Demo Streamlit (opcional) reaproveitando o mesmo grafo da CLI.

Uso:  streamlit run app.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import streamlit as st  # noqa: E402

from deep_research.cli import run  # noqa: E402
from deep_research.models import Query  # noqa: E402

st.set_page_config(page_title="Deep-Research Imobiliário", page_icon="🏠")
st.title("🏠 Deep-Research Imobiliário")

with st.form("busca"):
    col1, col2 = st.columns(2)
    cidade = col1.text_input("Cidade", "São Paulo")
    bairro = col2.text_input("Bairro", "Pinheiros")
    preco_min = col1.number_input("Preço mínimo (R$)", value=400_000, step=50_000)
    preco_max = col2.number_input("Preço máximo (R$)", value=800_000, step=50_000)
    tipo = col1.selectbox("Tipo", ["apartamento", "casa"])
    mock = col2.checkbox("Modo demo (sem scraping)", value=True)
    enviar = st.form_submit_button("Pesquisar")

if enviar:
    query = Query(
        cidade=cidade,
        bairro=bairro,
        preco_min=int(preco_min),
        preco_max=int(preco_max),
        tipo=tipo,
    )
    with st.spinner("Pesquisando o mercado..."):
        report = asyncio.run(run(query, {"mock": mock}))
    st.markdown(report)
