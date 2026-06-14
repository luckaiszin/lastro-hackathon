# Documentação — Deep-Research Imobiliário

Documento técnico do projeto: visão geral, fluxo de dados e o papel de **cada script**.

---

## 1. Visão geral

A ferramenta recebe um **recorte de mercado** (cidade, bairro, faixa de preço, tipo) e produz um **relatório de mercado imobiliário** em Markdown. O trabalho é organizado como um **grafo de estado** (LangGraph): cada etapa é um "nó" que lê e escreve num estado compartilhado.

```
Entrada (CLI / Streamlit)
        │  Query
        ▼
┌──────────────────────────────────────────────────────────────┐
│  parse → scrape → normalize → index → analyze → rank → report │
└──────────────────────────────────────────────────────────────┘
        │  report (Markdown)
        ▼
     Terminal / UI
```

**Princípios de design:**
- **Números são calculados em Python** (confiáveis); o **LLM** só produz texto qualitativo.
- **Tolerância a falhas:** um portal que quebra não derruba o pipeline.
- **Degrada sem LLM:** sem `ANTHROPIC_API_KEY`, o pipeline ainda roda (texto do LLM vira placeholder).
- **Modo `--mock`:** dados sintéticos para validar tudo sem rede nem API.

---

## 2. Mapa de arquivos

```
lastro_hackathon/
├── REAMDE.md                  # brief original do hackathon
├── README.md                  # apresentação + instalação + uso
├── DOCUMENTACAO.md            # este documento
├── requirements.txt           # dependências
├── pyproject.toml             # metadados + entrypoint `deep-research`
├── .env.example               # variáveis de ambiente (copiar p/ .env)
├── app.py                     # UI Streamlit (opcional)
└── src/deep_research/
    ├── __init__.py            # versão do pacote
    ├── config.py              # lê .env (chaves, flags)
    ├── models.py              # modelos de dados (Pydantic)
    ├── state.py               # tipo do estado do grafo
    ├── llm.py                 # factory do cliente Claude
    ├── graph.py               # monta e compila o grafo
    ├── segments.py            # agrupa imóveis por tipo (casa/apartamento)
    ├── store.py               # histórico vetorial (Chroma + embeddings locais)
    ├── cli.py                 # entrypoint: pipeline de busca
    ├── search.py              # entrypoint: busca semântica no histórico
    ├── scrapers/
    │   ├── __init__.py        # registra os scrapers
    │   ├── base.py            # infraestrutura Playwright + helpers + registro
    │   ├── quintoandar.py     # scraper do QuintoAndar  ✅
    │   ├── olx.py             # scraper do OLX Imóveis  ✅
    │   ├── zapimoveis.py      # scraper do ZAP Imóveis  ⚠️ (Cloudflare, instável)
    │   ├── vivareal.py        # scraper do VivaReal     ⛔ (Cloudflare)
    │   └── mock.py            # scraper sintético (demo/teste)
    └── nodes/
        ├── __init__.py
        ├── parse.py           # normaliza a consulta
        ├── scrape.py          # fan-out dos scrapers
        ├── normalize.py       # dedupe + filtro + R$/m²
        ├── index.py           # (opcional) indexa no Chroma
        ├── analyze.py         # estatísticas + observações (LLM)
        ├── rank.py            # oportunidades + justificativas (LLM)
        └── report.py          # monta o Markdown final
```

---

## 3. Núcleo do pacote

### `src/deep_research/__init__.py`
Marca a pasta como pacote Python e expõe `__version__`. Sem lógica.

### `config.py` — Configuração
Carrega o `.env` (via `python-dotenv`) e expõe constantes usadas em todo o projeto:
- `ANTHROPIC_API_KEY` — chave da Anthropic.
- `LLM_MODEL` — modelo Claude padrão (`claude-sonnet-4-6`).
- `HEADLESS` — roda o Chromium com/sem janela.
- `USE_CHROMA` — liga/desliga a indexação semântica.
- `CHROMA_DIR` — onde o Chroma persiste.
- `_flag()` — helper que interpreta `"true"/"1"/"on"` como booleano.

### `models.py` — Modelos de dados (Pydantic)
Define os "contratos" de dados que trafegam pelo grafo:
- **`Query`** — a consulta do usuário: cidade, bairro, **`operacao`** (`venda`|`aluguel`), `preco_min/max`, **`tipo`** (`apartamento`|`casa`|`ambos`), `quartos_min`, `uf`, `zona`, `max_paginas`.
- **`Listing`** — um imóvel (portal, url, **`tipo`** detectado, preço, área, quartos, etc.). Método `compute_preco_m2()` calcula R$/m².
- **`Opportunity`** — um imóvel destacado no ranking, com `justificativa`.
- **`MarketAnalysis`** — resumo do mercado de **um segmento** (campo `segmento`, médias, mediana, R$/m² médio, `observacoes`).
- **`MarketObservations`** — saída **estruturada** do LLM (apenas o campo `observacoes`), usada com `with_structured_output`.

### `state.py` — Estado do grafo
Define **`GraphState`** (`TypedDict`): o "quadro branco" que os nós leem e escrevem. Campos: `query`, `options` (ex.: `{"mock": True}`), `raw_listings`, `listings`, **`analyses`** (uma `MarketAnalysis` por segmento), **`rankings`** (`segmento → [Opportunity]`), `report`. Cada nó retorna um dicionário **parcial** que o LangGraph mescla nesse estado.

### `segments.py` — Segmentação por tipo
`segmentar(query, listings)` agrupa os imóveis: para `tipo` específico, um único segmento; para `tipo="ambos"`, um segmento por tipo detectado (`apartamento`, `casa`, `outros`). Usado por `analyze` e `rank` para produzir estatísticas/ranking **por tipo** (evita o viés de R$/m² ao misturar casa e apartamento).

### `store.py` — Histórico vetorial (Chroma)
Camada de persistência da busca semântica:
- **`get_collection()`** — abre/cria a coleção `imoveis` persistida em `CHROMA_DIR` (`.chroma/`), com a função de embedding configurada.
- **`_embedding_function()`** — escolhe o backend: **Ollama** (`EMBED_BACKEND=ollama`, modelo local) ou **default** (ONNX `all-MiniLM-L6-v2` embutido, para testes). O mesmo backend deve ser usado para indexar e buscar.
- **`index_listings(listings, query)`** — upsert por URL (acumula o histórico sem duplicar). Documento = título + fatos (tipo, quartos, área, bairro) + endereço/descrição; metadados = portal, operação, cidade, bairro, tipo, preço, área, quartos, R$/m².
- **`search(texto, n, where)`** — consulta semântica com filtro opcional de metadados. **`count()`** — tamanho do histórico.

### `llm.py` — Cliente Claude
Função **`get_llm()`**: fábrica do `ChatAnthropic` (langchain-anthropic). Faz import tardio (só quando há LLM a usar) e levanta erro claro se faltar a API key. Centraliza modelo, temperatura e `max_tokens`.

### `graph.py` — Montagem do grafo
**`build_graph()`** instancia o `StateGraph`, registra os 7 nós, liga as arestas e chama `.compile()`. É o único lugar que define a topologia — para reordenar/adicionar etapas, edita-se aqui. Contém **uma aresta condicional** (`_route_after_normalize`): se `normalize` não produzir imóveis, o grafo faz curto-circuito direto para `report`, pulando `index`/`analyze`/`rank`. Veja os diagramas em [`ARQUITETURA_GRAFO.md`](ARQUITETURA_GRAFO.md).

---

## 4. Scrapers (`scrapers/`)

### `base.py` — Infraestrutura de scraping
O coração do scraping:
- **`BaseScraper`** (classe abstrata): cada portal herda dela e implementa `build_url(query, page)` (monta a URL de busca) e `parse(page, query)` (extrai `Listing`s do DOM). O método `scrape()` já cuida de: abrir o Chromium (Playwright), `user-agent` realista, locale pt-BR, atraso aleatório entre páginas e paginação até `max_paginas`.
- **`register` / `all_scrapers()`**: um decorator que registra cada scraper num catálogo, usado pelo nó `scrape` para o fan-out automático.
- **`parse_int` / `parse_float`**: helpers que convertem texto sujo (`"R$ 750.000"`, `"72 m²"`) em número.

### Scrapers de portais (`quintoandar.py`, `olx.py`, `zapimoveis.py`, `vivareal.py`)
Implementações concretas (`@register`) para cada portal:
- `build_url` monta a URL de busca com cidade/bairro "slugificados" (`slugify` translitera acentos: "São Paulo" → "sao-paulo").
- `parse` localiza os cards de resultado e extrai cada `Listing`.
- São **tolerantes a falha**: retornam `[]` em vez de quebrar.
- OLX e ZAP usam os campos `uf` e `zona` da `Query` (a zona, ex.: `zona-oeste`, é necessária para filtrar por bairro nesses portais).

**Estado real das fontes (testado em 2026-06):**

| Portal | Status | Como extrai | Paginação | Observação |
|--------|--------|-------------|-----------|------------|
| **QuintoAndar** | ✅ **funcional** | `aria-label` do card | ⚠️ ~12 (lista acoplada ao mapa) | Filtro de preço da URL ignorado → reaplicado no `normalize`. |
| **OLX** | ✅ **funcional** | texto visível do card (regex; preço = maior `R$`) | ✅ `?o=N`, ~50/página | Motor de volume (~250 imóveis). Precisa de `zona`. |
| **ZAP Imóveis** | ⚠️ **instável** | texto visível do card (frase descritiva) | ⚠️ só página 1 (Cloudflare bloqueia 2+) | Requer `zona`; descarta blocos de imobiliária. |
| **VivaReal** | ⛔ **bloqueado** | — | — | Cloudflare (HTTP 403) barra headless. Scaffold. |

> **Paginação:** `Query.max_paginas` (default 5, flag `--paginas`). O `BaseScraper.scrape` acumula com **dedupe por URL** e **para no primeiro lote sem novidades** — o OLX cresce, QuintoAndar/ZAP encerram na 1ª página sem desperdício. A tabela do relatório mostra os 25 melhores R$/m² e indica o total.

> **Anti-ruído:** imóveis sem preço (cards incompletos/bloqueados) são descartados no `normalize`, pois não servem a uma pesquisa de mercado por preço.

> **Filtro de outliers:** por segmento (tipo), o `normalize` remove imóveis com R$/m² **< 0,5×** ou **> 2,5×** a mediana do segmento (amostra mínima de 8). Critério relativo à mediana — robusto à dispersão natural alta do R$/m² (studios vs. imóveis grandes) e interpretável. Captura erros de cadastro (ex.: quarto compartilhado anunciado como imóvel inteiro) sem descartar bons negócios reais. O relatório informa quantos foram removidos; `--manter-outliers` desativa.

### `mock.py` — Scraper sintético
**`MockScraper`**: gera 8 imóveis determinísticos a partir da `Query` (preços/áreas escalonados). Não usa rede. Serve para **demonstrar e testar o pipeline inteiro** (incluindo LLM e relatório) sem depender de scraping real. Ativado pela flag `--mock`.

### `scrapers/__init__.py`
Importa `vivareal` e `quintoandar` — esse import é o que **dispara o registro** dos scrapers (efeito colateral do `@register`).

---

## 5. Nós do grafo (`nodes/`)

Cada nó é uma função que recebe o `GraphState` e retorna um dicionário parcial.

| Nó | Arquivo | Entrada → Saída | O que faz |
|----|---------|-----------------|-----------|
| **parse** | `parse.py` | `query` → `query` | Normaliza a consulta: corrige faixa invertida (min>max), faz `strip`, padroniza o tipo. |
| **scrape** | `scrape.py` | `query`, `options` → `raw_listings` | **Async.** Roda todos os scrapers em paralelo (`asyncio.gather`). Se `options.mock`, usa só o `MockScraper`. Falha de um portal é logada e ignorada. |
| **normalize** | `normalize.py` | `raw_listings` → `listings` | Dedupe por URL, filtro de faixa de preço, `quartos_min` e **tipo**; descarta imóveis **sem preço**; calcula R$/m²; remove **outliers de R$/m²** por segmento (relativo à mediana; `--manter-outliers` desliga). |
| **index** | `index.py` | `listings` → (efeito colateral) | **Opcional** (`USE_CHROMA=true`). Persiste os imóveis no **histórico vetorial** (`store.index_listings`) para busca semântica posterior. Best-effort; pass-through quando desligado. |
| **analyze** | `analyze.py` | `listings` → `analyses` | **Segmenta por tipo** e, para cada segmento, calcula estatísticas em **Python** + leitura qualitativa via **Claude** (`MarketObservations`). Sem API key, usa placeholder. |
| **rank** | `rank.py` | `listings` + `analyses` → `rankings` | Por segmento, seleciona o `TOP_N` com R$/m² **abaixo da média daquele tipo**. Justificativa via **Claude**; sem LLM, calculada (% abaixo da média). |
| **report** | `report.py` | tudo → `report` | Monta o Markdown: **uma seção de mercado + oportunidades por segmento**, depois a tabela (top-25 por R$/m²). Rótulos adaptam a `operacao` (Preço/Aluguel, R$/m² ou R$/m²/mês). **Puro Python**. |

**Divisão de responsabilidades LLM × Python:** os nós `analyze` e `rank` calculam **todos os números** em Python e usam o LLM **apenas para texto** (observações e justificativas). Isso evita erros de aritmética do modelo e mantém o relatório confiável.

---

## 6. Interfaces de entrada

### `cli.py` — Linha de comando
Entrypoint principal:
1. Lê argumentos (`--cidade`, `--bairro`, `--min`, `--max`, `--tipo`, `--quartos-min`, `--paginas`, `--mock`).
2. Monta a `Query`.
3. Constrói o grafo e roda com `app.ainvoke(...)` (via `asyncio.run`, porque o nó `scrape` é assíncrono).
4. Imprime o relatório com `rich` (Markdown formatado).
   - Força **UTF-8** na saída (`sys.stdout.reconfigure` + `Console(legacy_windows=False)`) para evitar o erro de encoding cp1252 no terminal do Windows.

Função `run(query, options)` é reutilizável — também é chamada pelo Streamlit.

### `search.py` — Busca semântica (CLI)
Entrypoint separado (`python -m deep_research.search`) que **consulta o histórico** (`store.search`) sem fazer scraping. O `--texto` é **semântico** (significado); os demais são **filtros estruturados** (`where` de metadados do Chroma): `--operacao`, `--tipo`, `--bairro`, `--cidade` e **`--min/--max`** de preço (`preco $gte/$lte`). Importante: faixa de preço deve ir nas flags, **não no texto** — embeddings não entendem números. Mostra os resultados por similaridade numa tabela `rich`. Requer o histórico populado (`USE_CHROMA=true`).

### `app.py` — Streamlit (opcional)
UI web que reaproveita **o mesmo `run()`** da CLI. Formulário com cidade/bairro/faixa/tipo + checkbox "modo demo", e renderiza o relatório com `st.markdown`. Ajusta o `sys.path` para achar o pacote em `src/`.

---

## 7. Configuração e build

- **`requirements.txt`** — dependências (LangGraph/LangChain, Playwright, Selenium, ChromaDB, Pydantic, dotenv, rich).
- **`pyproject.toml`** — metadados do pacote; define o comando `deep-research` (= `cli:main`) e o layout `src/`. Permite `pip install -e .`.
- **`.env.example`** — modelo das variáveis de ambiente; copie para `.env` e preencha a API key.
- **`.gitignore`** — ignora `.env`, `__pycache__`, venvs, dados do Chroma.

---

## 8. Como o fluxo roda (passo a passo)

1. O usuário chama a CLI → cria uma `Query` e injeta `{"query", "options"}` no grafo.
2. **parse** higieniza a consulta.
3. **scrape** dispara os scrapers em paralelo → `raw_listings`.
4. **normalize** deduplica/filtra → `listings` (com R$/m²).
5. **index** (se ligado) joga descrições no Chroma.
6. **analyze** calcula estatísticas + observações do Claude → `analysis`.
7. **rank** escolhe as oportunidades + justificativas do Claude → `ranking`.
8. **report** transforma tudo em Markdown → `report`.
9. A CLI imprime o `report`.

---

## 9. Como estender

- **Novo portal:** crie `scrapers/meuportal.py` com uma classe `@register` herdando de `BaseScraper`, implemente `build_url`/`parse` e importe-a em `scrapers/__init__.py`. O fan-out a inclui automaticamente.
- **Nova etapa de análise:** crie `nodes/x.py`, registre o nó e ligue as arestas em `graph.py`.
- **Trocar o modelo LLM:** ajuste `LLM_MODEL` no `.env` (ex.: `claude-opus-4-8` para síntese mais robusta).
- **Ajustar scraping real:** afine as constantes `SEL_*` em cada scraper conforme o DOM atual do portal.
