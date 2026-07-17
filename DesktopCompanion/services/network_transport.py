"""Single mandatory proxy route shared by every AI provider."""

from __future__ import annotations

import socket
from dataclasses import dataclass
from urllib.parse import urlparse


class ProxyConfigurationError(RuntimeError):
    """Raised when the mandatory proxy setting is invalid."""


class ProxyUnavailableError(RuntimeError):
    """Raised when the configured proxy endpoint is not listening."""


@dataclass(frozen=True)
class NetworkTransport:
    proxy_url: str
    connect_timeout_seconds: float = 1.0

    def __post_init__(self) -> None:
        parsed = urlparse(self.proxy_url)
        if parsed.scheme not in {"http", "https", "socks5", "socks5h"}:
            raise ProxyConfigurationError("代理地址必须使用 http、https 或 socks5。")
        if not parsed.hostname or parsed.port is None:
            raise ProxyConfigurationError("代理地址必须包含主机名和端口。")
        if self.connect_timeout_seconds <= 0:
            raise ProxyConfigurationError("代理连接超时必须大于 0。")

    @property
    def host(self) -> str:
        hostname = urlparse(self.proxy_url).hostname
        assert hostname is not None
        return hostname

    @property
    def port(self) -> int:
        port = urlparse(self.proxy_url).port
        assert port is not None
        return port

    def ensure_available(self) -> None:
        try:
            with socket.create_connection(
                (self.host, self.port),
                timeout=self.connect_timeout_seconds,
            ):
                return
        except OSError as exc:
            raise ProxyUnavailableError(
                f"代理服务未就绪: {self.host}:{self.port}"
            ) from exc

    def httpx_client_kwargs(self) -> dict[str, object]:
        return {"proxy": self.proxy_url, "trust_env": False}

    def gemini_client_args(self) -> dict[str, object]:
        return {"proxy": self.proxy_url, "trust_env": False}
