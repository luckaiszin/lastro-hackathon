"""Factory do cliente Claude via langchain-anthropic."""

from __future__ import annotations

from typing import Optional

from . import config


def get_llm(model: Optional[str] = None, temperature: float = 0.2, max_tokens: int = 2048):
    """Retorna um ChatAnthropic configurado.

    Import tardio para que o pacote possa ser importado sem a dependência
    instalada (ex.: rodar o pipeline em modo --mock sem LLM).
    """
    from langchain_anthropic import ChatAnthropic

    if not config.ANTHROPIC_API_KEY:
        raise RuntimeError(
            "ANTHROPIC_API_KEY não definida. Preencha o .env ou use --mock para testar sem LLM."
        )

    return ChatAnthropic(
        model=model or config.LLM_MODEL,
        temperature=temperature,
        max_tokens=max_tokens,
        api_key=config.ANTHROPIC_API_KEY,
    )
