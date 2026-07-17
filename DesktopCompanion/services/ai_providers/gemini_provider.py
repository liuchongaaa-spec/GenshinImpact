"""Gemini AI provider."""

from __future__ import annotations

from google import genai
from google.genai import types

from DesktopCompanion.services.ai_providers.base import AIRequest
from DesktopCompanion.services.network_transport import NetworkTransport


class GeminiProvider:
    name = "gemini"

    def __init__(
        self,
        *,
        api_key: str,
        system_prompt: str,
        model_id: str,
        network_transport: NetworkTransport,
        timeout_seconds: float = 60.0,
        max_history_requests: int = 6,
        client=None,
    ) -> None:
        self.api_key = api_key
        self.system_prompt = system_prompt
        self.model_id = model_id
        self.timeout_seconds = timeout_seconds
        self.max_history_requests = max(0, max_history_requests)
        self.network_transport = network_transport
        self.client = client or genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=int(timeout_seconds * 1000),
                client_args=self.network_transport.gemini_client_args(),
                async_client_args=self.network_transport.gemini_client_args(),
            ),
        )
        self.chat = None
        self.history = []

    def create_session(self) -> bool:
        self.chat = self.client.chats.create(
            model=self.model_id,
            config=types.GenerateContentConfig(
                system_instruction=self.system_prompt,
            ),
            history=list(self.history),
        )
        return True

    def send(self, request: AIRequest) -> str:
        self.network_transport.ensure_available()
        if self.chat is None:
            self.create_session()

        parts = [types.Part.from_text(text=request.prompt)]
        if request.image_bytes:
            parts.append(types.Part.from_bytes(data=request.image_bytes, mime_type="image/jpeg"))
        if request.audio_bytes:
            parts.append(types.Part.from_bytes(data=request.audio_bytes, mime_type="audio/wav"))

        chunks: list[str] = []
        for chunk in self.chat.send_message_stream(parts):
            if chunk.text:
                chunks.append(chunk.text)

        full_text = "".join(chunks)
        self._update_history(request.prompt, full_text)
        # Recreate the chat next time so old screenshots/audio bytes are not kept by the SDK chat.
        self.chat = None
        return full_text

    def _update_history(self, user_text: str, full_text: str) -> None:
        self.history.append(
            types.Content(role="user", parts=[types.Part.from_text(text=user_text)])
        )
        self.history.append(
            types.Content(role="model", parts=[types.Part.from_text(text=full_text)])
        )

        maximum_messages = self.max_history_requests * 2
        if maximum_messages <= 0:
            self.history = []
        elif len(self.history) > maximum_messages:
            self.history = self.history[-maximum_messages:]

    def close(self) -> None:
        close = getattr(self.client, "close", None)
        if callable(close):
            close()
        self.chat = None
