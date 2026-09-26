"""LLM provider abstraction.

Saige works fully without an LLM. When ANTHROPIC_API_KEY is set, Claude is used for optional
enrichment. Every LLM output is treated as untrusted and verified before it is used.
"""

import logging
from typing import Protocol, TypeVar

import anthropic
from pydantic import BaseModel

from app.config import get_settings

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class LLMProvider(Protocol):
    name: str

    async def extract(self, *, system: str, prompt: str, schema: type[T]) -> T | None: ...


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str, model: str) -> None:
        self.client = anthropic.AsyncAnthropic(api_key=api_key, max_retries=2, timeout=90.0)
        self.model = model

    async def extract(self, *, system: str, prompt: str, schema: type[T]) -> T | None:
        """Structured extraction. Returns None on any failure so callers fall back to the
        deterministic result - enrichment must never block the core workflow."""
        try:
            response = await self.client.messages.parse(
                model=self.model,
                max_tokens=16000,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                output_config={"effort": "low"},  # simple extraction; keep cost and latency low
                output_format=schema,
            )
        except anthropic.RateLimitError:
            logger.warning("LLM rate limited; using deterministic analysis")
            return None
        except anthropic.APIStatusError as exc:
            logger.warning("LLM request failed with status %s", exc.status_code)
            return None
        except anthropic.APIConnectionError:
            logger.warning("LLM unreachable; using deterministic analysis")
            return None
        if response.stop_reason in {"refusal", "max_tokens"}:
            logger.warning("LLM stopped with %s; using deterministic analysis", response.stop_reason)
            return None
        return response.parsed_output


_provider: LLMProvider | None = None
_provider_set = False


def get_provider() -> LLMProvider | None:
    global _provider, _provider_set
    if not _provider_set:
        s = get_settings()
        _provider = AnthropicProvider(s.anthropic_api_key, s.llm_model) if s.llm_enabled else None
        _provider_set = True
    return _provider


def set_provider(provider: LLMProvider | None) -> None:
    """Override the provider (tests)."""
    global _provider, _provider_set
    _provider, _provider_set = provider, True
