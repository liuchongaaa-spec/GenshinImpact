"""Small controller that runs one AI task in the background."""

from __future__ import annotations

import asyncio
import concurrent.futures
import threading
from typing import Awaitable, Callable

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
        self._request_id = 0
        self._active_future: concurrent.futures.Future | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._request_gate: asyncio.Lock | None = None
        self._loop_thread: threading.Thread | None = None

    @property
    def current_model_id(self) -> str:
        return self.ai_service.current_model_id

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
        try:
            if self.ai_service.provider_name == "gemini":
                try:
                    self.ai_service.check_availability()
                    print(f"Gemini AI 服务可用，当前优先模型: {self.current_model_id}")
                except Exception as exc:
                    print(f"Gemini AI 服务检查失败，程序将继续启动: {exc}")
            self.ai_service.create_session()
            self.audio_capture.start()
            self._start_request_loop()
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
            self._request_id += 1
            active_future = self._active_future
            loop = self._loop
            loop_thread = self._loop_thread
        if active_future is not None:
            active_future.cancel()
        self.audio_capture.stop()
        if loop is not None and loop.is_running():
            close_future = asyncio.run_coroutine_threadsafe(
                self._close_ai_after_requests(), loop
            )
            try:
                close_future.result(2.0)
            except Exception:
                pass
            loop.call_soon_threadsafe(loop.stop)
        if loop_thread is not None and loop_thread is not threading.current_thread():
            loop_thread.join(2.0)
        if loop is None:
            self._close_ai()
        with self._lock:
            self._active_future = None
            self._busy = False
            self._loop = None
            self._request_gate = None
            self._loop_thread = None

    def request_screenshot(self) -> bool:
        return self._run_once("screenshot", self._run_screenshot)

    def request_audio_capture(self) -> bool:
        return self._run_once("audio", self._run_audio_capture)

    def _run_once(self, kind: str, job: Callable[[], Awaitable[str]]) -> bool:
        with self._lock:
            if not self._started:
                raise RuntimeError("Application controller is not running")
            loop = self._loop
            if loop is None or not loop.is_running():
                raise RuntimeError("AI request loop is not running")
            previous_future = self._active_future
            self._request_id += 1
            request_id = self._request_id
            self._busy = True
            future = asyncio.run_coroutine_threadsafe(
                self._run_job(request_id, kind, job), loop
            )
            self._active_future = future

        if previous_future is not None and not previous_future.done():
            previous_future.cancel()
        return True

    async def _run_job(
        self,
        request_id: int,
        kind: str,
        job: Callable[[], Awaitable[str]],
    ) -> None:
        try:
            request_gate = self._request_gate
            if request_gate is None:
                return
            async with request_gate:
                if not self._is_current_request(request_id):
                    return
                self.task_content_started.emit("sending...")
                html = await job()
                if self._is_current_request(request_id):
                    self.task_completed.emit(html)
        except asyncio.CancelledError:
            return
        except Exception as exc:
            if self._is_current_request(request_id):
                self.task_failed.emit(self._format_error(kind, exc))
        finally:
            with self._lock:
                if request_id == self._request_id:
                    self._busy = False
                    self._active_future = None

    async def _run_screenshot(self) -> str:
        image_bytes = self.screenshot_provider.capture_jpeg()
        return await self._send_to_ai(
            AIRequest(
                prompt="请识别当前截图中的面试题目，并严格按照系统提示词的要求给出答案。",
                image_bytes=image_bytes,
            )
        )

    async def _run_audio_capture(self) -> str:
        audio_bytes = self.audio_capture.get_audio_bytes()
        if not audio_bytes:
            raise AudioBufferEmpty("Audio buffer empty")

        image_bytes = self.screenshot_provider.capture_jpeg()
        return await self._send_to_ai(
            AIRequest(
                prompt=(
                    "请结合双轨音频和当前屏幕截图，判断面试官的真实意图或题目，"
                    "并严格按照系统提示词的要求给出答案。"
                ),
                image_bytes=image_bytes,
                audio_bytes=audio_bytes,
            )
        )

    async def _send_to_ai(self, request: AIRequest) -> str:
        markdown = await self.ai_service.send_async(request)
        return markdown_to_html(markdown) if markdown else ""

    def _start_request_loop(self) -> None:
        ready = threading.Event()
        loop = asyncio.new_event_loop()

        def run_loop() -> None:
            asyncio.set_event_loop(loop)
            self._request_gate = asyncio.Lock()
            ready.set()
            loop.run_forever()
            loop.close()

        loop_thread = threading.Thread(
            target=run_loop,
            daemon=True,
            name="desktop-companion-ai-loop",
        )
        self._loop = loop
        self._loop_thread = loop_thread
        loop_thread.start()
        ready.wait()

    def _is_current_request(self, request_id: int) -> bool:
        with self._lock:
            return self._started and request_id == self._request_id

    async def _close_ai_after_requests(self) -> None:
        request_gate = self._request_gate
        if request_gate is not None:
            async with request_gate:
                close_async = getattr(self.ai_service, "close_async", None)
                if callable(close_async):
                    await close_async()
                    return
        self._close_ai()

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
