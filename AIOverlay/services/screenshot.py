"""Pillow screenshot adapter with lightweight capture validation."""

from __future__ import annotations

import io
import time
from collections.abc import Callable

from PIL import Image, ImageGrab

from AIOverlay.utils.diagnostics import get_logger, health_registry


logger = get_logger("screenshot")


class ScreenshotCaptureError(RuntimeError):
    """Raised when Pillow cannot produce a valid JPEG screenshot."""


class PillowScreenshotProvider:
    """Capture the primary desktop using the application's existing semantics."""

    def __init__(
        self,
        grabber: Callable[..., Image.Image] | None = None,
        expected_size: tuple[int, int] | None = None,
    ) -> None:
        self._grabber = grabber or ImageGrab.grab
        self._expected_size = expected_size

    @property
    def expected_size(self) -> tuple[int, int] | None:
        return self._expected_size

    def capture_jpeg(self) -> bytes:
        started = time.perf_counter()
        image: Image.Image | None = None
        try:
            image = self._grabber(
                all_screens=False,
                include_layered_windows=False,
            )
            if not isinstance(image, Image.Image):
                raise ScreenshotCaptureError("Screenshot grabber returned no image")
            if image.width <= 0 or image.height <= 0:
                raise ScreenshotCaptureError("Screenshot has invalid dimensions")

            capture_size = image.size
            capture_mode = image.mode
            if image.mode != "RGB":
                converted = image.convert("RGB")
                image.close()
                image = converted

            with io.BytesIO() as output:
                image.save(output, format="JPEG")
                encoded = output.getvalue()
            self._validate_jpeg(encoded, capture_size)
        except ScreenshotCaptureError:
            self._record_failure(started)
            raise
        except Exception as exc:
            self._record_failure(started)
            raise ScreenshotCaptureError(f"Screenshot capture failed: {exc}") from exc
        finally:
            if image is not None:
                image.close()

        size_changed = (
            self._expected_size is not None and capture_size != self._expected_size
        )
        if self._expected_size is None:
            self._expected_size = capture_size

        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        metadata = {
            "width": capture_size[0],
            "height": capture_size[1],
            "source_mode": capture_mode,
            "jpeg_bytes": len(encoded),
            "duration_ms": duration_ms,
            "size_changed": size_changed,
        }
        state = "degraded" if size_changed else "healthy"
        detail = "Screenshot size changed" if size_changed else "Screenshot captured"
        health_registry.update("screenshot", state, detail, metadata)
        logger.info(
            "%s; width=%d height=%d mode=%s bytes=%d duration_ms=%.2f",
            detail,
            capture_size[0],
            capture_size[1],
            capture_mode,
            len(encoded),
            duration_ms,
            extra={"component": "screenshot", "event": "captured", "task_id": None},
        )
        return encoded

    @staticmethod
    def _validate_jpeg(encoded: bytes, expected_size: tuple[int, int]) -> None:
        if not encoded:
            raise ScreenshotCaptureError("Screenshot JPEG is empty")
        try:
            with Image.open(io.BytesIO(encoded)) as decoded:
                decoded.verify()
            with Image.open(io.BytesIO(encoded)) as decoded:
                if decoded.format != "JPEG" or decoded.size != expected_size:
                    raise ScreenshotCaptureError("Screenshot JPEG validation failed")
        except ScreenshotCaptureError:
            raise
        except Exception as exc:
            raise ScreenshotCaptureError("Screenshot JPEG validation failed") from exc

    @staticmethod
    def _record_failure(started: float) -> None:
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        health_registry.update(
            "screenshot",
            "failed",
            "Screenshot capture failed",
            {"duration_ms": duration_ms},
        )
        logger.error(
            "Screenshot capture failed; duration_ms=%.2f",
            duration_ms,
            extra={"component": "screenshot", "event": "capture_failed", "task_id": None},
        )
