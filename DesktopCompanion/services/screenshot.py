"""Pillow screenshot adapter."""

from __future__ import annotations

import io
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageGrab


class ScreenshotCaptureError(RuntimeError):
    """Raised when Pillow cannot capture a screenshot."""


class PillowScreenshotProvider:
    """Capture the primary desktop as JPEG bytes."""

    def __init__(
        self,
        grabber: Callable[..., Image.Image] | None = None,
        save_dir: str = "",
    ) -> None:
        self._grabber = grabber or ImageGrab.grab
        self._save_dir = Path(save_dir) if save_dir else None

    def capture_jpeg(self) -> bytes:
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

            if image.mode != "RGB":
                converted = image.convert("RGB")
                image.close()
                image = converted

            with io.BytesIO() as output:
                image.save(output, format="JPEG")
                encoded = output.getvalue()
            if not encoded:
                raise ScreenshotCaptureError("Screenshot JPEG is empty")
            return encoded
        except ScreenshotCaptureError:
            raise
        except Exception as exc:
            raise ScreenshotCaptureError(f"Screenshot capture failed: {exc}") from exc
        finally:
            if image is not None:
                image.close()

    def save_jpeg(self, image_bytes: bytes) -> Path | None:
        if self._save_dir is None:
            return None
        if not image_bytes:
            raise ScreenshotCaptureError("Screenshot JPEG is empty")

        now = datetime.now()
        daily_dir = self._save_dir / now.strftime("%Y-%m-%d")
        daily_dir.mkdir(parents=True, exist_ok=True)

        while True:
            filename = f"{now:%H-%M-%S-%f}-{uuid4().hex[:8]}.jpg"
            output_path = daily_dir / filename
            try:
                with output_path.open("xb") as output:
                    output.write(image_bytes)
                return output_path
            except FileExistsError:
                continue
