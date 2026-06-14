"""Scrapers de portais imobiliários.

Importar este pacote registra os scrapers (via decorator @register) para o
fan-out automático em `scrapers.base.all_scrapers()`.
"""

from . import olx, quintoandar, vivareal, zapimoveis  # noqa: F401  (efeito colateral: registro)
from .base import all_scrapers, register

__all__ = ["all_scrapers", "register"]
