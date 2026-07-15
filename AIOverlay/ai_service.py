"""Gemini client wrapper with bounded requests and classified failures."""

from __future__ import annotations

from enum import Enum
import os
import threading
import time
from typing import Iterable

import httpx
from google import genai
from google.genai import errors, types

from AIOverlay.config import (
    GEMINI_API_KEY,
    MODEL_ID,
    PROXY_URL,
    SYSTEM_PROMPT,
    InitializationError,
)
from AIOverlay.utils.diagnostics import get_logger, health_registry


logger = get_logger("ai_service")

TRANSPORT_TIMEOUT_SECONDS = 60.0
MAX_SEND_ATTEMPTS = 2
DEFAULT_HISTORY_REQUESTS = 6


class AIErrorCategory(str, Enum):
    AUTHENTICATION = "authentication"
    QUOTA = "quota"
    PROXY = "proxy"
    NETWORK = "network"
    TIMEOUT = "timeout"
    MODEL_UNAVAILABLE = "model_unavailable"
    CONTENT = "content"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class AIServiceError(RuntimeError):
    def __init__(
        self,
        category: AIErrorCategory,
        message: str,
        *,
        retryable: bool = False,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.retryable = retryable
        self.__cause__ = cause


def classify_ai_error(exc: Exception) -> AIServiceError:
    if isinstance(exc, AIServiceError):
        return exc
    if isinstance(exc, (TimeoutError, httpx.TimeoutException)):
        return AIServiceError(
            AIErrorCategory.TIMEOUT,
            "AI request timed out",
            retryable=True,
            cause=exc,
        )
    if isinstance(exc, httpx.ProxyError):
        return AIServiceError(
            AIErrorCategory.PROXY,
            "AI proxy connection failed",
            retryable=True,
            cause=exc,
        )
    if isinstance(exc, httpx.NetworkError):
        return AIServiceError(
            AIErrorCategory.NETWORK,
            "AI network connection failed",
            retryable=True,
            cause=exc,
        )

    code = getattr(exc, "code", None)
    status = str(getattr(exc, "status", "") or "").lower()
    message = str(getattr(exc, "message", "") or str(exc))
    lowered = f"{status} {message}".lower()

    if code in (401, 403) or any(
        marker in lowered for marker in ("api key not valid", "invalid api key", "unauthenticated")
    ):
        category = AIErrorCategory.AUTHENTICATION
        retryable = False
        public_message = "AI authentication failed"
    elif code == 429 or any(
        marker in lowered for marker in ("resource_exhausted", "quota", "rate limit")
    ):
        category = AIErrorCategory.QUOTA
        retryable = False
        public_message = "AI quota or rate limit reached"
    elif code == 404 or "model not found" in lowered:
        category = AIErrorCategory.MODEL_UNAVAILABLE
        retryable = False
        public_message = "Configured AI model is unavailable"
    elif code is not None and 500 <= code < 600:
        category = AIErrorCategory.MODEL_UNAVAILABLE
        retryable = True
        public_message = "AI service is temporarily unavailable"
    elif code == 400 or any(
        marker in lowered for marker in ("blocked", "safety", "content", "invalid_argument")
    ):
        category = AIErrorCategory.CONTENT
        retryable = False
        public_message = "AI rejected the request content"
    elif "proxy" in lowered:
        category = AIErrorCategory.PROXY
        retryable = True
        public_message = "AI proxy connection failed"
    elif any(
        marker in lowered
        for marker in ("disconnect", "connection", "network", "eof", "dns")
    ):
        category = AIErrorCategory.NETWORK
        retryable = True
        public_message = "AI network connection failed"
    elif "timeout" in lowered or "timed out" in lowered:
        category = AIErrorCategory.TIMEOUT
        retryable = True
        public_message = "AI request timed out"
    else:
        category = AIErrorCategory.UNKNOWN
        retryable = False
        public_message = "Unexpected AI service failure"

    return AIServiceError(category, public_message, retryable=retryable, cause=exc)


class AIService:
    def __init__(
        self,
        client=None,
        api_key: str = GEMINI_API_KEY,
        system_prompt: str = SYSTEM_PROMPT,
        model_id: str = MODEL_ID,
        proxy_url: str = PROXY_URL,
        transport_timeout_seconds: float = TRANSPORT_TIMEOUT_SECONDS,
        max_history_requests: int = DEFAULT_HISTORY_REQUESTS,
    ) -> None:
        if proxy_url:
            os.environ["HTTP_PROXY"] = proxy_url
            os.environ["HTTPS_PROXY"] = proxy_url

        self.api_key = api_key
        self.system_prompt = system_prompt
        self.model_id = model_id
        self.proxy_url = proxy_url
        self.transport_timeout_seconds = transport_timeout_seconds
        self.max_history_requests = max(0, max_history_requests)
        self.client = client or genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=int(transport_timeout_seconds * 1000),
            ),
        )
        self.chat = None
        self.history = []
        self._init_history()
        health_registry.update("ai", "starting", "AI service created")
        logger.info(
            "AI service created for model %s",
            self.model_id,
            extra={"component": "ai", "event": "service_created", "task_id": None},
        )

    def _init_history(self) -> None:
        self.history = [
            types.Content(role="user", parts=[types.Part.from_text(text="你好")]),
            types.Content(
                role="model",
                parts=[types.Part.from_text(text="你好！我是您的AI助手。")],
            ),
        ]

    def create_session(self) -> bool:
        try:
            self.chat = self.client.chats.create(
                model=self.model_id,
                config=types.GenerateContentConfig(
                    system_instruction=self.system_prompt,
                    http_options=types.HttpOptions(
                        timeout=int(self.transport_timeout_seconds * 1000)
                    ),
                ),
                history=list(self.history),
            )
        except Exception as exc:
            self.chat = None
            error = classify_ai_error(exc)
            health_registry.update("ai", "failed", error.category.value)
            logger.exception(
                "Gemini chat session creation failed; category=%s",
                error.category.value,
                extra={"component": "ai", "event": "session_failed", "task_id": None},
            )
            raise error from exc

        health_registry.update("ai", "healthy", "Gemini chat session ready")
        logger.info(
            "Gemini chat session created",
            extra={"component": "ai", "event": "session_created", "task_id": None},
        )
        return True

    def send_stream(
        self,
        content,
        *,
        cancel_event: threading.Event | None = None,
        deadline: float | None = None,
    ) -> Iterable[str]:
        """Return one committed response; failed partial streams never escape."""
        last_error: AIServiceError | None = None
        for attempt in range(1, MAX_SEND_ATTEMPTS + 1):
            self._check_cancelled_or_expired(cancel_event, deadline)
            try:
                if self.chat is None:
                    self.create_session()

                response_stream = self.chat.send_message_stream(content)
                logger.info(
                    "Gemini stream started; attempt=%d",
                    attempt,
                    extra={"component": "ai", "event": "stream_started", "task_id": None},
                )
                chunks: list[str] = []
                for chunk in response_stream:
                    self._check_cancelled_or_expired(cancel_event, deadline)
                    if chunk.text:
                        chunks.append(chunk.text)

                full_text = "".join(chunks)
                self._update_history(content, full_text)
                # The SDK Chat retains inline media. Rebuild from bounded text-only
                # history for the next request so old screenshots and WAV data die here.
                self.chat = None
                health_registry.update("ai", "healthy", "Last stream completed")
                logger.info(
                    "Gemini stream completed; characters=%d attempt=%d history_requests=%d history_characters=%d",
                    len(full_text),
                    attempt,
                    self._history_request_count(),
                    self._history_character_count(),
                    extra={"component": "ai", "event": "stream_completed", "task_id": None},
                )
                yield full_text
                return
            except Exception as exc:
                error = classify_ai_error(exc)
                last_error = error
                health_registry.update("ai", "degraded", error.category.value)
                logger.exception(
                    "Gemini stream failed; attempt=%d category=%s retryable=%s",
                    attempt,
                    error.category.value,
                    error.retryable,
                    extra={"component": "ai", "event": "stream_failed", "task_id": None},
                )
                if not error.retryable or attempt >= MAX_SEND_ATTEMPTS:
                    raise error from exc
                self.chat = None

        if last_error is not None:
            raise last_error

    def _check_cancelled_or_expired(
        self,
        cancel_event: threading.Event | None,
        deadline: float | None,
    ) -> None:
        if cancel_event is not None and cancel_event.is_set():
            raise AIServiceError(AIErrorCategory.CANCELLED, "AI request cancelled")
        if deadline is not None and time.monotonic() >= deadline:
            raise AIServiceError(
                AIErrorCategory.TIMEOUT,
                "AI request exceeded its total deadline",
                retryable=False,
            )

    def _update_history(self, content, full_text: str) -> None:
        user_text = self._extract_text(content)
        self.history.append(
            types.Content(role="user", parts=[types.Part.from_text(text=user_text)])
        )
        self.history.append(
            types.Content(role="model", parts=[types.Part.from_text(text=full_text)])
        )
        maximum_messages = self.max_history_requests * 2
        conversation = self.history[2:]
        if len(conversation) > maximum_messages:
            conversation = conversation[-maximum_messages:] if maximum_messages else []
            self.history = self.history[:2] + conversation

    @staticmethod
    def _extract_text(content) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, types.Content):
            parts = content.parts or []
        else:
            parts = content or []
        text_parts = []
        for part in parts:
            if isinstance(part, str):
                text_parts.append(part)
                continue
            text = getattr(part, "text", None)
            if text:
                text_parts.append(text)
        return "\n".join(text_parts)

    def _history_request_count(self) -> int:
        return max(0, (len(self.history) - 2) // 2)

    def _history_character_count(self) -> int:
        total = 0
        for content in self.history[2:]:
            for part in content.parts or []:
                total += len(part.text or "")
        return total

    def close(self) -> None:
        close = getattr(self.client, "close", None)
        if callable(close):
            close()
        self.chat = None
        health_registry.update("ai", "stopped", "AI client closed")

    @staticmethod
    def create_text_part(text: str):
        return types.Part.from_text(text=text)

    @staticmethod
    def create_image_part(image_bytes: bytes, mime_type: str = "image/jpeg"):
        return types.Part.from_bytes(data=image_bytes, mime_type=mime_type)

    @staticmethod
    def create_audio_part(audio_bytes: bytes, mime_type: str = "audio/wav"):
        return types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)

    @staticmethod
    def test_connection(
        api_key: str,
        model_id: str = MODEL_ID,
        proxy_url: str = PROXY_URL,
        timeout_seconds: float = 15.0,
    ) -> None:
        if proxy_url:
            os.environ["HTTP_PROXY"] = proxy_url
            os.environ["HTTPS_PROXY"] = proxy_url

        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=int(timeout_seconds * 1000)),
        )
        try:
            client.models.generate_content(
                model=model_id,
                contents="Reply with OK.",
                config=types.GenerateContentConfig(
                    max_output_tokens=2,
                    http_options=types.HttpOptions(timeout=int(timeout_seconds * 1000)),
                ),
            )
        except Exception as exc:
            error = classify_ai_error(exc)
            raise InitializationError(
                f"AI connection test failed ({error.category.value}): {error}"
            ) from exc
        finally:
            client.close()
