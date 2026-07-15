"""Application services, one FIFO worker, and Qt-safe result delivery."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum
import threading
import time
import uuid
from typing import Callable

from PyQt5.QtCore import QObject, pyqtSignal

from AIOverlay.ai_service import AIErrorCategory, AIService, AIServiceError
from AIOverlay.audio_capture import AudioCapture
from AIOverlay.config import AUDIO_CONFIG
from AIOverlay.services.screenshot import PillowScreenshotProvider
from AIOverlay.utils.diagnostics import get_logger, health_registry
from AIOverlay.utils.markdown_renderer import markdown_to_html


logger = get_logger("application_controller")
REQUEST_TOTAL_TIMEOUT_SECONDS = 120.0


class RequestState(str, Enum):
    IDLE = "idle"
    QUEUED = "queued"
    CAPTURING = "capturing"
    SENDING = "sending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


_ALLOWED_TRANSITIONS = {
    RequestState.QUEUED: {
        RequestState.CAPTURING,
        RequestState.FAILED,
        RequestState.CANCELLED,
    },
    RequestState.CAPTURING: {
        RequestState.SENDING,
        RequestState.FAILED,
        RequestState.CANCELLED,
    },
    RequestState.SENDING: {
        RequestState.COMPLETED,
        RequestState.FAILED,
        RequestState.CANCELLED,
    },
}


class RequestCancelled(RuntimeError):
    pass


class RequestDeadlineExceeded(TimeoutError):
    pass


class AudioBufferEmpty(RuntimeError):
    pass


@dataclass
class _Task:
    task_id: str
    kind: str
    runner: Callable[["_Task"], str]
    state: RequestState = RequestState.QUEUED
    cancel_event: threading.Event = field(default_factory=threading.Event)
    deadline: float | None = None


class ApplicationController(QObject):
    """Own external services and serialize all Gemini access."""

    task_started = pyqtSignal(str, str)
    task_content_started = pyqtSignal(str, str)
    task_completed = pyqtSignal(str, str)
    task_failed = pyqtSignal(str, str)
    task_state_changed = pyqtSignal(str, str, str)

    def __init__(
        self,
        ai_service,
        audio_capture,
        screenshot_provider,
        parent=None,
        request_timeout: float = REQUEST_TOTAL_TIMEOUT_SECONDS,
    ) -> None:
        super().__init__(parent)
        self.ai_service = ai_service
        self.audio_capture = audio_capture
        self.screenshot_provider = screenshot_provider
        self._request_timeout = request_timeout
        self._condition = threading.Condition(threading.RLock())
        self._queue: deque[_Task] = deque()
        self._tasks: dict[str, _Task] = {}
        self._active_kinds: set[str] = set()
        self._worker: threading.Thread | None = None
        self._accepting = False
        self._current_state = RequestState.IDLE
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        self.ai_service.create_session()
        try:
            self.audio_capture.start()
            with self._condition:
                self._accepting = True
                self._worker = threading.Thread(
                    target=self._worker_loop,
                    daemon=True,
                    name="aioverlay-request-worker",
                )
                self._worker.start()
        except Exception:
            self.audio_capture.stop()
            self._close_ai()
            raise

        self._started = True
        health_registry.update("controller", "healthy", "Application controller started")
        logger.info(
            "Application controller started",
            extra={"component": "controller", "event": "started", "task_id": None},
        )

    def stop(self) -> None:
        if not self._started:
            return
        with self._condition:
            self._accepting = False
            for task in self._tasks.values():
                task.cancel_event.set()
            self._condition.notify_all()
            worker = self._worker

        if worker is not None and worker is not threading.current_thread():
            worker.join(2.0)
        worker_stopped = worker is None or not worker.is_alive()
        self.audio_capture.stop()
        self._close_ai()
        self._started = False
        health_registry.update(
            "controller",
            "stopped" if worker_stopped else "degraded",
            "Application controller stopped",
            {"request_worker_stopped": worker_stopped},
        )
        logger.info(
            "Application controller stopped; request_worker_stopped=%s",
            worker_stopped,
            extra={"component": "controller", "event": "stopped", "task_id": None},
        )

    def request_screenshot(self) -> str | None:
        return self._submit("screenshot", self._run_screenshot)

    def request_audio_capture(self) -> str | None:
        return self._submit("audio", self._run_audio_capture)

    def active_task_ids(self) -> set[str]:
        with self._condition:
            return set(self._tasks)

    @property
    def request_state(self) -> RequestState:
        with self._condition:
            if not self._tasks:
                return RequestState.IDLE
            return self._current_state

    def wait_for_idle(self, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        with self._condition:
            while self._tasks:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._condition.wait(remaining)
            return True

    def _submit(self, kind: str, runner: Callable[[_Task], str]) -> str | None:
        with self._condition:
            if not self._accepting:
                raise RuntimeError("Application controller is not running")
            if kind in self._active_kinds:
                logger.info(
                    "Duplicate task ignored; kind=%s",
                    kind,
                    extra={"component": "controller", "event": "duplicate_ignored", "task_id": None},
                )
                return None

            task = _Task(uuid.uuid4().hex, kind, runner)
            self._tasks[task.task_id] = task
            self._active_kinds.add(kind)
            self._queue.append(task)

        # Emit started before waking the worker so fast results cannot reach the UI first.
        self._emit_state(task, RequestState.QUEUED)
        self.task_started.emit(task.task_id, task.kind)
        with self._condition:
            self._condition.notify_all()
        return task.task_id

    def _worker_loop(self) -> None:
        while True:
            with self._condition:
                while not self._queue and self._accepting:
                    self._condition.wait()
                if not self._queue and not self._accepting:
                    return
                task = self._queue.popleft()

            try:
                task.deadline = time.monotonic() + self._request_timeout
                self._checkpoint(task)
                html = task.runner(task)
                self._checkpoint(task)
                self._transition(task, RequestState.COMPLETED)
                self.task_completed.emit(task.task_id, html)
            except RequestCancelled:
                self._finish_failed(task, RequestState.CANCELLED, None)
            except AIServiceError as exc:
                if exc.category == AIErrorCategory.CANCELLED:
                    self._finish_failed(task, RequestState.CANCELLED, None)
                else:
                    self._finish_failed(task, RequestState.FAILED, exc)
            except Exception as exc:
                self._finish_failed(task, RequestState.FAILED, exc)
            finally:
                with self._condition:
                    self._tasks.pop(task.task_id, None)
                    self._active_kinds.discard(task.kind)
                    if not self._tasks:
                        self._current_state = RequestState.IDLE
                    elif self._queue:
                        self._current_state = RequestState.QUEUED
                    self._condition.notify_all()

    def _run_screenshot(self, task: _Task) -> str:
        self._transition(task, RequestState.CAPTURING)
        image_bytes = self.screenshot_provider.capture_jpeg()
        prompt = self.ai_service.create_text_part("请分析这张屏幕截图的内容。")
        image_part = self.ai_service.create_image_part(image_bytes)

        self._transition(task, RequestState.SENDING)
        self.task_content_started.emit(task.task_id, "sending...")
        markdown = "".join(
            self.ai_service.send_stream(
                [prompt, image_part],
                cancel_event=task.cancel_event,
                deadline=task.deadline,
            )
        )
        return markdown_to_html(markdown) if markdown else ""

    def _run_audio_capture(self, task: _Task) -> str:
        self._transition(task, RequestState.CAPTURING)
        audio_bytes = self.audio_capture.get_audio_bytes()
        if not audio_bytes:
            raise AudioBufferEmpty("Audio buffer empty")

        prompt = self.ai_service.create_text_part("请分析这段音频内容。")
        audio_part = self.ai_service.create_audio_part(audio_bytes)
        image_part = self.ai_service.create_image_part(
            self.screenshot_provider.capture_jpeg()
        )

        self._transition(task, RequestState.SENDING)
        self.task_content_started.emit(task.task_id, "sending audio...")
        markdown = "".join(
            self.ai_service.send_stream(
                [prompt, audio_part, image_part],
                cancel_event=task.cancel_event,
                deadline=task.deadline,
            )
        )
        return markdown_to_html(markdown) if markdown else ""

    def _transition(self, task: _Task, state: RequestState) -> None:
        self._checkpoint(task)
        if state not in _ALLOWED_TRANSITIONS.get(task.state, set()):
            raise RuntimeError(f"Invalid request state transition: {task.state} -> {state}")
        task.state = state
        self._emit_state(task, state)

    def _checkpoint(self, task: _Task) -> None:
        if task.cancel_event.is_set():
            raise RequestCancelled(f"Task {task.task_id} was cancelled")
        if task.deadline is not None and time.monotonic() >= task.deadline:
            raise RequestDeadlineExceeded(
                f"Task exceeded {self._request_timeout:.0f}s total timeout"
            )

    def _finish_failed(
        self,
        task: _Task,
        state: RequestState,
        exc: Exception | None,
    ) -> None:
        if state in _ALLOWED_TRANSITIONS.get(task.state, set()):
            task.state = state
            self._emit_state(task, state)
        if state == RequestState.CANCELLED:
            return
        assert exc is not None
        self._report_failure(task, exc)

    def _emit_state(self, task: _Task, state: RequestState) -> None:
        with self._condition:
            self._current_state = state
        health_state = {
            RequestState.QUEUED: "starting",
            RequestState.CAPTURING: "starting",
            RequestState.SENDING: "starting",
            RequestState.COMPLETED: "healthy",
            RequestState.FAILED: "failed",
            RequestState.CANCELLED: "degraded",
        }[state]
        health_registry.update(
            "last_task",
            health_state,
            f"{task.kind} task {state.value}",
            {"task_id": task.task_id, "kind": task.kind, "request_state": state.value},
        )
        self.task_state_changed.emit(task.task_id, task.kind, state.value)
        logger.info(
            "Task state changed; kind=%s state=%s",
            task.kind,
            state.value,
            extra={"component": "controller", "event": "task_state", "task_id": task.task_id},
        )

    def _report_failure(self, task: _Task, exc: Exception) -> None:
        health_registry.update(
            "last_task",
            "failed",
            str(exc),
            {"task_id": task.task_id, "kind": task.kind},
        )
        logger.error(
            "Task failed; kind=%s error=%s",
            task.kind,
            exc,
            exc_info=(type(exc), exc, exc.__traceback__),
            extra={"component": "controller", "event": "task_failed", "task_id": task.task_id},
        )
        if isinstance(exc, AudioBufferEmpty):
            message = "音频缓冲区为空，请稍后再试。"
        else:
            prefix = "截图处理错误" if task.kind == "screenshot" else "音频处理错误"
            if isinstance(exc, AIServiceError):
                message = f"{prefix} [{exc.category.value}]: {exc}"
            else:
                message = f"{prefix}: {exc}"
        self.task_failed.emit(task.task_id, message)

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
