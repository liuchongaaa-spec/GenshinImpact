"""DeepSeek/OpenAI-compatible chat provider."""

from __future__ import annotations

import base64

import httpx

from DesktopCompanion.services.ai_providers.base import AIRequest
from DesktopCompanion.services.network_transport import NetworkTransport


class DeepSeekProvider:
    name = "deepseek"

    def __init__(
        self,
        *,
        api_key: str,
        system_prompt: str,
        model_id: str = "deepseek-chat",
        base_url: str = "https://api.deepseek.com/v1",
        network_transport: NetworkTransport,
        timeout_seconds: float = 60.0,
        max_history_requests: int = 6,
    ) -> None:
        self.api_key = api_key
        self.system_prompt = system_prompt
        self.model_id = model_id
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_history_requests = max(0, max_history_requests)
        self.network_transport = network_transport
        self.history: list[dict[str, str]] = []

    def create_session(self) -> bool:
        return True

    def send(self, request: AIRequest) -> str:
        self.network_transport.ensure_available()
        if request.audio_bytes:
            raise RuntimeError("当前 DeepSeek Provider 未配置音频输入能力。")

        user_content = self._build_user_content(request)
        messages = [
            {"role": "system", "content": self.system_prompt},
            *self.history,
            {"role": "user", "content": user_content},
        ]
        payload = {
            "model": self.model_id,
            "messages": messages,
            "stream": False,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        with httpx.Client(
            timeout=self.timeout_seconds,
            **self.network_transport.httpx_client_kwargs(),
        ) as client:
            response = client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        text = data["choices"][0]["message"].get("content", "")
        self._update_history(request.prompt, text)
        return text

    def _build_user_content(self, request: AIRequest):
        if not request.image_bytes:
            return request.prompt
        image_b64 = base64.b64encode(request.image_bytes).decode("ascii")
        return [
            {"type": "text", "text": request.prompt},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
            },
        ]

    def _update_history(self, user_text: str, assistant_text: str) -> None:
        self.history.append({"role": "user", "content": user_text})
        self.history.append({"role": "assistant", "content": assistant_text})

        maximum_messages = self.max_history_requests * 2
        if maximum_messages <= 0:
            self.history = []
        elif len(self.history) > maximum_messages:
            self.history = self.history[-maximum_messages:]

    def close(self) -> None:
        pass
