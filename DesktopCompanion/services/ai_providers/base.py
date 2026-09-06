"""Common AI provider types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class AIRequest:
    prompt: str
    image_bytes: bytes | None = None
    audio_bytes: bytes | None = None
    model_profile: str = "standard"


class AIProvider(Protocol):
    name: str

    def check_availability(self) -> bool:
        ...

    def create_session(self) -> bool:
        ...

    def send(self, request: AIRequest) -> str:
        ...

    def close(self) -> None:
        ...
