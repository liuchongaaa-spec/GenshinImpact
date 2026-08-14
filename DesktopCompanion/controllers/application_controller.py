"""Small controller that runs one AI task in the background."""

from __future__ import annotations

import threading
from typing import Callable

from PyQt5.QtCore import QObject, pyqtSignal

from DesktopCompanion.config import AUDIO_CONFIG
from DesktopCompanion.services.ai_providers import AIRequest
from DesktopCompanion.services.ai_service import AIService
from DesktopCompanion.services.audio_capture import AudioCapture
from DesktopCompanion.services.screenshot import PillowScreenshotProvider
from DesktopCompanion.utils.markdown_renderer import markdown_to_html


class AudioBufferEmpty(RuntimeError):
    pass


class ApplicationController(QObject):
    """Own the services and keep AI work off the GUI thread."""

    task_content_started = pyqtSignal(str)
    task_completed = pyqtSignal(str)
    task_failed = pyqtSignal(str)

    def __init__(
        self,
        ai_service,
        audio_capture,
        screenshot_provider,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.ai_service = ai_service
        self.audio_capture = audio_capture
        self.screenshot_provider = screenshot_provider
        self._lock = threading.RLock()
        self._busy = False
        self._started = False
        self._worker: threading.Thread | None = None

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
        try:
            if self.ai_service.provider_name == "gemini":
                try:
                    self.ai_service.check_availability()
                    print("AI 服务正常")
                except Exception as exc:
                    print(f"AI 服务异常: {exc}")
            self.ai_service.create_session()
            self.audio_capture.start()
        except Exception:
            self.audio_capture.stop()
            self._close_ai()
            raise
        with self._lock:
            self._started = True

    def stop(self) -> None:
        with self._lock:
            if not self._started:
                return
            self._started = False
            worker = self._worker
        if worker is not None and worker is not threading.current_thread():
            worker.join(2.0)
        self.audio_capture.stop()
        if worker is None or not worker.is_alive():
            self._close_ai()

    def request_screenshot(self) -> bool:
        return self._run_once("screenshot", self._run_screenshot)

    def request_audio_capture(self) -> bool:
        return self._run_once("audio", self._run_audio_capture)

    def _run_once(self, kind: str, job: Callable[[], str]) -> bool:
        with self._lock:
            if not self._started:
                raise RuntimeError("Application controller is not running")
            if self._busy:
                return False
            self._busy = True
            self._worker = threading.Thread(
                target=self._run_job,
                args=(kind, job),
                daemon=True,
                name=f"desktop-companion-{kind}-worker",
            )
            worker = self._worker

        worker.start()
        return True

    def _run_job(self, kind: str, job: Callable[[], str]) -> None:
        try:
            html = job()
            self.task_completed.emit(html)
        except Exception as exc:
            self.task_failed.emit(self._format_error(kind, exc))
        finally:
            with self._lock:
                self._busy = False
                self._worker = None

    def _run_screenshot(self) -> str:
        image_bytes = self.screenshot_provider.capture_jpeg()
        self.task_content_started.emit("sending...")
        return self._send_to_ai(
            AIRequest(
                prompt="请识别当前截图中的面试题目，并严格按照系统提示词的要求给出答案。",
                image_bytes=image_bytes,
            )
        )

    def _run_audio_capture(self) -> str:
        audio_bytes = self.audio_capture.get_audio_bytes()
        if not audio_bytes:
            raise AudioBufferEmpty("Audio buffer empty")

        image_bytes = self.screenshot_provider.capture_jpeg()
        self.task_content_started.emit("sending audio...")
        return self._send_to_ai(
            AIRequest(
                prompt=(
                    "请结合双轨音频和当前屏幕截图，判断面试官的真实意图或题目，"
                    "并严格按照系统提示词的要求给出答案。"
                ),
                image_bytes=image_bytes,
                audio_bytes=audio_bytes,
            )
        )

    def _send_to_ai(self, request: AIRequest) -> str:
        markdown = self.ai_service.send(request)
        return markdown_to_html(markdown) if markdown else ""

    @staticmethod
    def _format_error(kind: str, exc: Exception) -> str:
        if isinstance(exc, AudioBufferEmpty):
            return "\u97f3\u9891\u7f13\u51b2\u533a\u4e3a\u7a7a\uff0c\u8bf7\u7a0d\u540e\u518d\u8bd5\u3002"
        prefix = "\u622a\u56fe\u5904\u7406\u9519\u8bef" if kind == "screenshot" else "\u97f3\u9891\u5904\u7406\u9519\u8bef"
        return f"{prefix}: {exc}"

    def _close_ai(self) -> None:
        close = getattr(self.ai_service, "close", None)
        if callable(close):
            close()


def create_default_controller() -> ApplicationController:
    """Build the fixed set of services used by the desktop application."""
    return ApplicationController(
        AIService(),
        AudioCapture(
            buffer_seconds=AUDIO_CONFIG.get("buffer_seconds", 45),
            sample_rate=AUDIO_CONFIG.get("sample_rate", 16000),
        ),
        PillowScreenshotProvider(),
    )
