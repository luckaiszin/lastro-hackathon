# Deep-Research Imobiliário

Ferramenta de **deep-research** que pesquisa o mercado imobiliário de um **bairro** dentro de uma **faixa de preço**: faz scraping de portais, estrutura os dados e um agente LLM produz um **relatório de mercado** (listagens, estatísticas e ranking de oportunidades).

## Stack

- **LangGraph / LangChain** — orquestração dos agentes (grafo de estado)
- **Playwright** (Selenium como fallback) — scraping de portais JS-pesados
- **Claude** (`langchain-anthropic`) — análise e síntese do relatório
- **ChromaDB** (opcional) — busca semântica nas descrições

## Arquitetura (grafo)

```
parse → scrape → normalize → index(opcional) → analyze → rank → report
```

| Nó | Responsabilidade |
|----|------------------|
| `parse`     | Normaliza a consulta (cidade, bairro, faixa de preço, tipo) |
| `scrape`    | Fan-out dos scrapers por portal (tolerante a falhas) |
| `normalize` | Limpa, deduplica e filtra por faixa de preço; calcula R$/m² |
| `index`     | (Opcional) indexa descrições no Chroma |
| `analyze`   | Estatísticas (Python) + observações de mercado (LLM) |
| `rank`      | Seleciona oportunidades abaixo da média; LLM justifica |
| `report`    | Monta o relatório final em Markdown |

## Instalação

```bash
pip install -r requirements.txt
playwright install chromium
cp .env.example .env   # preencha ANTHROPIC_API_KEY
```

## Uso

```bash
# Compra (venda) — apartamentos
python -m deep_research.cli --cidade "São Paulo" --bairro "Pinheiros" \
    --min 400000 --max 800000 --tipo apartamento --zona zona-oeste

# Aluguel — valores mensais
python -m deep_research.cli --cidade "São Paulo" --bairro "Pinheiros" \
    --operacao aluguel --min 2000 --max 8000 --zona zona-oeste

# Casa e apartamento juntos, com análise segmentada por tipo
python -m deep_research.cli --cidade "São Paulo" --bairro "Pinheiros" \
    --min 400000 --max 1500000 --tipo ambos --zona zona-oeste

# Demo sem rede nem API (dados sintéticos) — valida o pipeline end-to-end
python -m deep_research.cli --cidade "São Paulo" --bairro "Pinheiros" \
    --min 400000 --max 800000 --tipo ambos --mock
```

Principais flags: `--operacao venda|aluguel`, `--tipo apartamento|casa|ambos`,
`--zona` (OLX/ZAP), `--uf` (default `sp`), `--paginas`, `--manter-outliers`
(por padrão, R$/m² anômalos por segmento são removidos).

Rode a partir da pasta `src/`, ou instale em modo editável (`pip install -e .`).

## Documentação

- [`DOCUMENTACAO.md`](DOCUMENTACAO.md) — fluxo de dados e o papel de **cada script**.
- [`ARQUITETURA_GRAFO.md`](ARQUITETURA_GRAFO.md) — **máquina de estado** do agente (diagramas).

## Fontes de dados

| Portal | Status | Observação |
|--------|--------|------------|
| **QuintoAndar** | ✅ funcional | dados via `aria-label` do card |
| **OLX Imóveis** | ✅ funcional | ~50 anúncios/página; precisa de `--zona` |
| **ZAP Imóveis** | ⚠️ instável | Cloudflare intermitente; precisa de `--zona` |
| **VivaReal** | ⛔ bloqueado | Cloudflare; scaffold mantido |

OLX e ZAP filtram por bairro melhor com a zona da cidade:

```bash
python -m deep_research.cli --cidade "São Paulo" --bairro "Pinheiros" \
    --min 400000 --max 800000 --zona zona-oeste
```

Sem scraping, use `--mock` para uma demo completa do pipeline.

## Busca semântica no histórico (Chroma + Ollama)

A cada busca com `USE_CHROMA=true`, os imóveis são indexados num **histórico
vetorial** (ChromaDB, persistido em `.chroma/`). Depois é possível pesquisar
esses dados **já coletados** em linguagem natural — sem refazer o scraping.

Os embeddings rodam **localmente via Ollama** (padrão):

```bash
# 1) instale o Ollama (https://ollama.com), deixe o servidor rodando e baixe o modelo
ollama pull nomic-embed-text

# 2) colete dados com indexação ligada
USE_CHROMA=true python -m deep_research.cli --cidade "São Paulo" --bairro "Pinheiros" \
    --min 400000 --max 900000 --zona zona-oeste

# 3) pesquise o histórico semanticamente (com filtros opcionais)
python -m deep_research.search --texto "studio reformado perto do metrô"
python -m deep_research.search --texto "studio no centro" --operacao aluguel --min 800 --max 1200
```

> **Importante:** o `--texto` é semântico (busca por *significado*) e **não entende
> números/faixas**. Preço, bairro, tipo e operação são **filtros estruturados** —
> use as flags `--min/--max`, `--bairro`, `--tipo`, `--operacao`, não escreva o preço
> na frase. Ex.: `--texto "studio aconchegante" --max 1200` (não `--texto "studio até 1200"`).

Sem Ollama, use o backend embutido para testar: `EMBED_BACKEND=default` (ONNX
local, sem servidor). O backend/modelo deve ser o **mesmo** na indexação e na
busca — vetores de dimensões diferentes não são comparáveis. Ao trocar de
backend ou modelo, **resete o histórico**: apague `.chroma/` e reindexe.

## Aviso

Os scrapers são para fins **educacionais / hackathon**. Respeite os Termos de Uso e o `robots.txt` de cada portal e use com responsabilidade.
