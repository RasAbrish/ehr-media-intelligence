"""Summary providers: Fake (tests), Extractive (offline), Anthropic (Claude) and Groq."""

from __future__ import annotations

from anthropic import AsyncAnthropic

from ehr_mip.config import Settings
from ehr_mip.summarization.providers.anthropic import AnthropicProvider
from ehr_mip.summarization.providers.base import Provider
from ehr_mip.summarization.providers.extractive import ExtractiveProvider
from ehr_mip.summarization.providers.groq import GroqProvider


def make_provider(settings: Settings) -> Provider:
    """Claude or Groq when chosen and keyed (``effective_llm_provider``), otherwise extractive."""
    if settings.effective_llm_provider == "anthropic" and settings.anthropic_api_key is not None:
        client = AsyncAnthropic(
            api_key=settings.anthropic_api_key.get_secret_value(),
            max_retries=0,  # the provider counts and paces its own retries
            timeout=settings.llm_timeout_s,
        )
        return AnthropicProvider(client=client, model=settings.llm_model)
    if settings.effective_llm_provider == "groq" and settings.groq_api_key is not None:
        return GroqProvider(
            api_key=settings.groq_api_key.get_secret_value(),
            model=settings.groq_model,
            timeout_s=max(settings.llm_timeout_s, 60),
        )
    return ExtractiveProvider()
