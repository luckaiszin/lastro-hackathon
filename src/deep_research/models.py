"""Modelos de dados (Pydantic) compartilhados pelo grafo."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class Query(BaseModel):
    """Parâmetros da pesquisa do usuário."""

    cidade: str
    bairro: str
    operacao: str = "venda"  # venda | aluguel
    preco_min: Optional[int] = None
    preco_max: Optional[int] = None
    tipo: str = "apartamento"  # apartamento | casa | ambos
    quartos_min: Optional[int] = None
    max_paginas: int = 5  # páginas por portal (paginação para no 1º "sem novidades")
    filtrar_outliers: bool = True  # remove R$/m² anômalos por segmento (log-IQR)
    # Usados por OLX/ZAP (que precisam de estado e, idealmente, da zona da cidade).
    uf: str = "sp"
    zona: Optional[str] = None  # ex.: "zona-oeste"


class Listing(BaseModel):
    """Um imóvel extraído de um portal."""

    portal: str
    url: str
    titulo: Optional[str] = None
    tipo: Optional[str] = None  # "apartamento" | "casa" (detectado do anúncio)
    preco: Optional[int] = None  # R$
    area: Optional[float] = None  # m²
    quartos: Optional[int] = None
    banheiros: Optional[int] = None
    vagas: Optional[int] = None
    bairro: Optional[str] = None
    endereco: Optional[str] = None
    descricao: Optional[str] = None
    preco_m2: Optional[float] = None

    def compute_preco_m2(self) -> Optional[float]:
        if self.preco and self.area and self.area > 0:
            self.preco_m2 = round(self.preco / self.area, 2)
        return self.preco_m2


class Opportunity(BaseModel):
    """Imóvel destacado como oportunidade pelo agente de ranking."""

    url: str
    titulo: Optional[str] = None
    preco: Optional[int] = None
    preco_m2: Optional[float] = None
    justificativa: str


class MarketAnalysis(BaseModel):
    """Resumo estatístico + qualitativo do mercado no recorte pesquisado."""

    segmento: str = "geral"  # "apartamento" | "casa" | tipo único pesquisado
    total_imoveis: int = 0
    preco_medio: Optional[float] = None
    preco_mediano: Optional[float] = None
    preco_min: Optional[int] = None
    preco_max: Optional[int] = None
    preco_m2_medio: Optional[float] = None
    observacoes: str = ""


class MarketObservations(BaseModel):
    """Saída estruturada do LLM: leitura qualitativa do mercado."""

    observacoes: str = Field(..., description="Análise qualitativa do mercado em 2-4 frases, em português.")
