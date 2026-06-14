"""Gera as imagens de documentação do grafo.

- grafo.png            : máquina de estado oficial (exportada do LangGraph)
- pipeline_exemplo.png : pipeline anotado com um exemplo de consulta real

Uso:
    PYTHONPATH=src python scripts/diagrams.py
"""

from __future__ import annotations

import base64
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from deep_research.graph import build_graph  # noqa: E402

# Exemplo validado em modo --mock:
# python -m deep_research.cli --cidade "São Paulo" --bairro "Pinheiros" --min 400000 --max 800000 --mock
EXEMPLO_MERMAID = """
flowchart TD
    Q["🔎 Consulta do usuário<br/>São Paulo · Pinheiros<br/>R$ 400k – 800k · apartamento"]:::query
    Q --> parse

    parse["<b>parse</b><br/>normaliza a Query"]:::node
    parse -->|"query válida"| scrape

    scrape["<b>scrape</b> · fan-out paralelo<br/>vivareal · quintoandar · mock"]:::node
    scrape -->|"raw_listings: 8 imóveis"| normalize

    normalize["<b>normalize</b><br/>dedupe + filtro de preço + R$/m²"]:::node
    normalize -->|"listings: 8 válidos · 0 descartados"| index

    index["<b>index</b> (opcional)<br/>USE_CHROMA=false → pass-through"]:::opt
    index --> analyze

    analyze["<b>analyze</b><br/>médio R$ 575k · mediano R$ 575k<br/>R$/m² médio 7.680 + leitura Claude"]:::llm
    analyze -->|"analysis"| rank

    rank["<b>rank</b> · Top-3 abaixo da média<br/>6.944 · 7.071 · 7.222 R$/m²<br/>+ justificativas Claude"]:::llm
    rank -->|"ranking"| report

    report["<b>report</b><br/>monta o Markdown"]:::node
    report --> OUT["📄 Relatório<br/>resumo de mercado + 3 oportunidades + tabela"]:::out

    classDef query fill:#e8fff0,stroke:#2bb673,stroke-width:2px;
    classDef node fill:#f2f0ff,stroke:#7c6cf0;
    classDef opt fill:#fff6e6,stroke:#e0a800;
    classDef llm fill:#eef4ff,stroke:#5b8def,stroke-width:2px;
    classDef out fill:#fbe9ff,stroke:#b14fd8,stroke-width:2px;
"""


def render_official(dest: Path) -> None:
    png = build_graph().get_graph().draw_mermaid_png()
    dest.write_bytes(png)
    print(f"ok: {dest.name}")


def render_mermaid_ink(mermaid: str, dest: Path) -> None:
    encoded = base64.urlsafe_b64encode(mermaid.strip().encode("utf-8")).decode("ascii")
    url = f"https://mermaid.ink/img/{encoded}?type=png&bgColor=ffffff"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        dest.write_bytes(resp.read())
    print(f"ok: {dest.name}")


if __name__ == "__main__":
    render_official(ROOT / "grafo.png")
    render_mermaid_ink(EXEMPLO_MERMAID, ROOT / "pipeline_exemplo.png")
