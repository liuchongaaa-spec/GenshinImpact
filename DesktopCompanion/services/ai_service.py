"""Provider-neutral AI service facade."""

from __future__ import annotations

import asyncio

from DesktopCompanion.config import AI_PROVIDER
from DesktopCompanion.services.ai_providers import AIRequest, create_ai_provider


class AIService:
    def __init__(self, provider=None, provider_name: str | None = None) -> None:
        self.provider = provider or create_ai_provider(provider_name)

    @property
    def provider_name(self) -> str:
        return getattr(self.provider, "name", AI_PROVIDER)

    @property
    def current_model_id(self) -> str:
        return getattr(self.provider, "current_model_id", "")

    def check_availability(self) -> bool:
        return self.provider.check_availability()

    def create_session(self) -> bool:
        return self.provider.create_session()

    def send(self, request: AIRequest) -> str:
        return self.provider.send(request)

    async def send_async(self, request: AIRequest) -> str:
        send_async = getattr(self.provider, "send_async", None)
        if callable(send_async):
            return await send_async(request)
        return await asyncio.to_thread(self.provider.send, request)

    def close(self) -> None:
        self.provider.close()

    async def close_async(self) -> None:
        close_async = getattr(self.provider, "close_async", None)
        if callable(close_async):
            await close_async()
        else:
            await asyncio.to_thread(self.provider.close)
