"""AI provider factory."""

from __future__ import annotations

from DesktopCompanion.config import (
    AI_PROVIDER,
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL_ID,
    GEMINI_API_KEY,
    GEMINI_MODEL_TIMEOUT_SECONDS,
    GEMINI_MODEL_IDS,
    MAX_HISTORY_TURNS,
    SYSTEM_PROMPT,
)


def create_ai_provider(
    provider_name: str | None = None,
):
    provider = (provider_name or AI_PROVIDER or "gemini").lower()
    if provider == "gemini":
        from DesktopCompanion.services.ai_providers.gemini_provider import GeminiProvider

        return GeminiProvider(
            api_key=GEMINI_API_KEY,
            system_prompt=SYSTEM_PROMPT,
            model_ids=GEMINI_MODEL_IDS,
            timeout_seconds=GEMINI_MODEL_TIMEOUT_SECONDS,
            max_history_turns=MAX_HISTORY_TURNS,
        )
    if provider == "deepseek":
        from DesktopCompanion.services.ai_providers.deepseek_provider import DeepSeekProvider

        return DeepSeekProvider(
            api_key=DEEPSEEK_API_KEY,
            system_prompt=SYSTEM_PROMPT,
            model_id=DEEPSEEK_MODEL_ID,
            base_url=DEEPSEEK_BASE_URL,
        )
    raise ValueError(f"Unknown AI provider: {provider_name}")
