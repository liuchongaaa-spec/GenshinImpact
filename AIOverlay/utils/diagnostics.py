"""In-memory runtime health with file logging explicitly disabled."""

from __future__ import annotations

import logging
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping


VALID_STATES = {"starting", "healthy", "degraded", "failed", "stopped"}


@dataclass(frozen=True)
class ComponentHealth:
    component: str
    state: str
    detail: str = ""
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata: Mapping[str, Any] = field(default_factory=dict)


class HealthRegistry:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._components: dict[str, ComponentHealth] = {}

    def update(
        self,
        component: str,
        state: str,
        detail: str = "",
        metadata: Mapping[str, Any] | None = None,
    ) -> ComponentHealth:
        if state not in VALID_STATES:
            raise ValueError(f"Unsupported health state: {state}")
        health = ComponentHealth(
            component=component,
            state=state,
            detail=detail,
            metadata=dict(metadata or {}),
        )
        with self._lock:
            self._components[component] = health
        return health

    def get(self, component: str) -> ComponentHealth | None:
        with self._lock:
            return self._components.get(component)

    def snapshot(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return {
                component: asdict(health)
                for component, health in self._components.items()
            }

    def clear(self) -> None:
        with self._lock:
            self._components.clear()


health_registry = HealthRegistry()


def get_logger(name: str) -> logging.Logger:
    """Return a sink logger so diagnostics never create files or extra output."""
    logger = logging.getLogger(f"AIOverlay.{name}")
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())
    logger.propagate = False
    return logger
