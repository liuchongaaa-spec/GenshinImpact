"""Provider-neutral AI service facade."""

from __future__ import annotations

from DesktopCompanion.config import AI_PROVIDER
from DesktopCompanion.services.ai_providers import AIRequest, create_ai_provider


class AIService:
    def __init__(self, provider=None, provider_name: str | None = None) -> None:
        self.provider = provider or create_ai_provider(provider_name)

    @property
    def provider_name(self) -> str:
        return getattr(self.provider, "name", AI_PROVIDER)

    def create_session(self) -> bool:
        return self.provider.create_session()

    def send(self, request: AIRequest) -> str:
        return self.provider.send(request)

    def close(self) -> None:
        self.provider.close()
