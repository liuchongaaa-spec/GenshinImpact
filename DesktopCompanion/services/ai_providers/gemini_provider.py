"""Gemini AI provider."""

from __future__ import annotations

import asyncio

import httpx
from google import genai
from google.genai import errors, types

from DesktopCompanion.services.ai_providers.base import AIRequest
from DesktopCompanion.services.network_transport import NetworkTransport


class GeminiProvider:
    name = "gemini"

    def __init__(
        self,
        *,
        api_key: str,
        system_prompt: str,
        model_ids: tuple[str, ...] | list[str],
        network_transport: NetworkTransport,
        timeout_seconds: float = 60.0,
        max_history_turns: int = 6,
        client=None,
    ) -> None:
        self.api_key = api_key
        self.system_prompt = system_prompt
        self.model_ids = list(
            dict.fromkeys(
                model_id.strip() for model_id in model_ids if model_id.strip()
            )
        )
        if not self.model_ids:
            raise ValueError("At least one Gemini model must be configured")
        self.timeout_seconds = timeout_seconds
        self.max_history_turns = max(0, max_history_turns)
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
        self.chat_model_id = None
        self.async_chat = None
        self.async_chat_model_id = None
        self.history = []

    @property
    def current_model_id(self) -> str:
        return self.model_ids[0]

    def check_availability(self) -> bool:
        """Find the first currently available model without changing network failures."""
        self.network_transport.ensure_available()
        model_count = len(self.model_ids)
        for attempt_index in range(model_count):
            model_id = self.current_model_id
            try:
                self.client.models.generate_content(
                    model=model_id,
                    contents="Service health check. Reply with OK.",
                    config=types.GenerateContentConfig(
                        max_output_tokens=8,
                        http_options=types.HttpOptions(
                            timeout=10_000,
                            retry_options=types.HttpRetryOptions(
                                attempts=3,
                                initial_delay=1.0,
                                max_delay=4.0,
                                exp_base=2.0,
                                jitter=0.2,
                                http_status_codes=[408, 429, 500, 502, 503, 504],
                            ),
                        ),
                    ),
                )
                return True
            except Exception as exc:
                if not self._should_try_next_model(exc):
                    raise
                self._move_model_to_end(model_id)
                if attempt_index == model_count - 1:
                    raise
                print(
                    f"模型 {model_id} 暂时不可用，"
                    f"尝试备用模型 {self.current_model_id}"
                )
        return False

    def create_session(self, model_id: str | None = None) -> bool:
        model_id = model_id or self.current_model_id
        self.chat = self.client.chats.create(
            model=model_id,
            config=types.GenerateContentConfig(
                system_instruction=self.system_prompt,
            ),
            history=list(self.history),
        )
        self.chat_model_id = model_id
        return True

    def send(self, request: AIRequest) -> str:
        self.network_transport.ensure_available()
        parts = [types.Part.from_text(text=request.prompt)]
        if request.image_bytes:
            parts.append(
                types.Part.from_bytes(
                    data=request.image_bytes,
                    mime_type="image/jpeg",
                )
            )
        if request.audio_bytes:
            parts.append(
                types.Part.from_bytes(
                    data=request.audio_bytes,
                    mime_type="audio/wav",
                )
            )

        candidate_models = list(self.model_ids)
        for attempt_index, model_id in enumerate(candidate_models):
            if self.chat is None or self.chat_model_id != model_id:
                self.create_session(model_id)

            try:
                chunks: list[str] = []
                for chunk in self.chat.send_message_stream(parts):
                    if chunk.text:
                        chunks.append(chunk.text)
                full_text = "".join(chunks)
            except Exception as exc:
                self.chat = None
                self.chat_model_id = None
                timed_out = isinstance(exc, (TimeoutError, httpx.TimeoutException))
                model_unavailable = self._should_try_next_model(exc)
                if not timed_out and not model_unavailable:
                    raise
                if model_unavailable:
                    self._move_model_to_end(model_id)
                if attempt_index == len(candidate_models) - 1:
                    raise
                reason = "请求超时" if timed_out else "暂时不可用"
                next_model_id = candidate_models[attempt_index + 1]
                print(
                    f"模型 {model_id} {reason}，"
                    f"当前请求切换到 {next_model_id}"
                )
                continue

            self._update_history(request.prompt, full_text)
            # Recreate the chat next time so old screenshots/audio bytes are not kept by the SDK chat.
            self.chat = None
            self.chat_model_id = None
            return full_text

        raise RuntimeError("No Gemini model completed the request")

    async def send_async(self, request: AIRequest) -> str:
        self.network_transport.ensure_available()
        parts = [types.Part.from_text(text=request.prompt)]
        if request.image_bytes:
            parts.append(
                types.Part.from_bytes(
                    data=request.image_bytes,
                    mime_type="image/jpeg",
                )
            )
        if request.audio_bytes:
            parts.append(
                types.Part.from_bytes(
                    data=request.audio_bytes,
                    mime_type="audio/wav",
                )
            )

        candidate_models = list(self.model_ids)
        for attempt_index, model_id in enumerate(candidate_models):
            self.async_chat = self.client.aio.chats.create(
                model=model_id,
                config=types.GenerateContentConfig(
                    system_instruction=self.system_prompt,
                ),
                history=list(self.history),
            )
            self.async_chat_model_id = model_id

            try:
                chunks: list[str] = []
                stream = await self.async_chat.send_message_stream(parts)
                async for chunk in stream:
                    if chunk.text:
                        chunks.append(chunk.text)
                full_text = "".join(chunks)
            except asyncio.CancelledError:
                self.async_chat = None
                self.async_chat_model_id = None
                raise
            except Exception as exc:
                self.async_chat = None
                self.async_chat_model_id = None
                timed_out = isinstance(exc, (TimeoutError, httpx.TimeoutException))
                model_unavailable = self._should_try_next_model(exc)
                if not timed_out and not model_unavailable:
                    raise
                if model_unavailable:
                    self._move_model_to_end(model_id)
                if attempt_index == len(candidate_models) - 1:
                    raise
                reason = "请求超时" if timed_out else "暂时不可用"
                next_model_id = candidate_models[attempt_index + 1]
                print(
                    f"模型 {model_id} {reason}，"
                    f"当前请求切换到 {next_model_id}"
                )
                continue

            self._update_history(request.prompt, full_text)
            self.async_chat = None
            self.async_chat_model_id = None
            return full_text

        raise RuntimeError("No Gemini model completed the request")

    def _move_model_to_end(self, model_id: str) -> None:
        if model_id in self.model_ids:
            self.model_ids.remove(model_id)
            self.model_ids.append(model_id)

    @staticmethod
    def _should_try_next_model(error: Exception) -> bool:
        return isinstance(error, errors.APIError) and error.code in (429, 503)

    def _update_history(self, user_text: str, full_text: str) -> None:
        self.history.append(
            types.Content(role="user", parts=[types.Part.from_text(text=user_text)])
        )
        self.history.append(
            types.Content(role="model", parts=[types.Part.from_text(text=full_text)])
        )

        maximum_messages = self.max_history_turns * 2
        if maximum_messages <= 0:
            self.history = []
        elif len(self.history) > maximum_messages:
            self.history = self.history[-maximum_messages:]

    def close(self) -> None:
        close = getattr(self.client, "close", None)
        if callable(close):
            close()
        self.chat = None
        self.chat_model_id = None
        self.async_chat = None
        self.async_chat_model_id = None

    async def close_async(self) -> None:
        async_client = getattr(self.client, "aio", None)
        close_async = getattr(async_client, "aclose", None)
        if callable(close_async):
            await close_async()
        self.close()
