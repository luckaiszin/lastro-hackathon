"""Persistência vetorial (Chroma) — histórico de imóveis + busca semântica.

A coleção é persistida em disco (`CHROMA_DIR`) e acumula os imóveis de todas as
buscas (upsert por URL). Os embeddings são gerados por um modelo **local**:
Ollama por padrão (`EMBED_BACKEND=ollama`) ou o ONNX embutido do Chroma
(`EMBED_BACKEND=default`, para testes sem servidor).

IMPORTANTE: o mesmo backend de embedding deve ser usado para indexar e para
buscar (vetores de dimensões diferentes não são comparáveis).
"""

from __future__ import annotations

from typing import List, Optional

from . import config
from .models import Listing, Query

COLLECTION = "imoveis"


def _embedding_function():
    from chromadb.utils import embedding_functions as ef

    if config.EMBED_BACKEND == "ollama":
        return ef.OllamaEmbeddingFunction(
            url=config.OLLAMA_URL, model_name=config.OLLAMA_EMBED_MODEL
        )
    return ef.DefaultEmbeddingFunction()


def get_collection():
    import chromadb

    client = chromadb.PersistentClient(path=config.CHROMA_DIR)
    return client.get_or_create_collection(
        COLLECTION, embedding_function=_embedding_function()
    )


def _documento(l: Listing) -> str:
    """Texto descritivo do imóvel para o embedding."""
    partes: List[str] = []
    if l.titulo:
        partes.append(l.titulo)

    fatos = []
    if l.tipo:
        fatos.append(l.tipo)
    if l.quartos:
        fatos.append(f"{l.quartos} quartos")
    if l.area:
        fatos.append(f"{l.area:g} m²")
    if l.bairro:
        fatos.append(f"em {l.bairro}")
    if fatos:
        partes.append(", ".join(fatos))

    if l.endereco:
        partes.append(l.endereco)
    if l.descricao and l.descricao != l.titulo:
        partes.append(l.descricao)

    return ". ".join(partes) or l.url


def _metadata(l: Listing, query: Optional[Query]) -> dict:
    md = {
        "portal": l.portal,
        "url": l.url,
        "operacao": (query.operacao if query else "") or "",
        "cidade": (query.cidade if query else "") or "",
        "bairro": l.bairro or (query.bairro if query else "") or "",
        "tipo": l.tipo or "",
    }
    # Chroma aceita str/int/float/bool — só inclui numéricos existentes.
    if l.preco is not None:
        md["preco"] = l.preco
    if l.area is not None:
        md["area"] = l.area
    if l.quartos is not None:
        md["quartos"] = l.quartos
    if l.preco_m2 is not None:
        md["preco_m2"] = l.preco_m2
    return md


def index_listings(listings: List[Listing], query: Optional[Query] = None) -> int:
    """Insere/atualiza (upsert) os imóveis no histórico. Retorna quantos."""
    docs = [l for l in listings if l.url]
    if not docs:
        return 0
    col = get_collection()
    col.upsert(
        ids=[l.url for l in docs],
        documents=[_documento(l) for l in docs],
        metadatas=[_metadata(l, query) for l in docs],
    )
    return len(docs)


def search(texto: str, n: int = 10, where: Optional[dict] = None) -> List[dict]:
    """Busca semântica no histórico. `where` é um filtro de metadados do Chroma."""
    col = get_collection()
    res = col.query(query_texts=[texto], n_results=n, where=where or None)

    out: List[dict] = []
    if res and res.get("ids") and res["ids"][0]:
        ids = res["ids"][0]
        metas = res["metadatas"][0]
        docs = res["documents"][0]
        dists = res["distances"][0]
        for i in range(len(ids)):
            out.append(
                {
                    "url": ids[i],
                    "metadata": metas[i],
                    "documento": docs[i],
                    "distancia": dists[i],
                }
            )
    return out


def count() -> int:
    return get_collection().count()
