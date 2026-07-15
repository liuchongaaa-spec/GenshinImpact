# -*- coding: utf-8 -*-
"""Transparent overlay window. All QWidget access stays on the GUI thread."""

import os
import sys

import keyboard
from PyQt5.QtCore import QObject, QThread, Qt, pyqtSignal
from PyQt5.QtGui import QTextCursor
from PyQt5.QtWidgets import (
    QApplication,
    QDesktopWidget,
    QMainWindow,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from AIOverlay.config import (
    HOTKEY_CONFIG,
    LOAD_TEST_FILE,
    MODEL_ID,
    MOVE_STEP,
    SCROLL_STEP,
    TEST_FILE_PATH,
    TEXT_CONFIG,
    WINDOW_CONFIG,
)
from AIOverlay.controllers.application_controller import (
    ApplicationController,
    create_default_controller,
)
from AIOverlay.stealth import stealth_manager
from AIOverlay.ui.tray import TrayManager
from AIOverlay.utils.diagnostics import get_logger, health_registry
from AIOverlay.utils.markdown_renderer import get_markdown_css, markdown_to_html


class WorkerSignals(QObject):
    toggle_visible = pyqtSignal()
    screenshot_requested = pyqtSignal()
    move_window = pyqtSignal(int)
    scroll_content = pyqtSignal(int)
    exit_app = pyqtSignal()
    audio_capture_requested = pyqtSignal()


FONT_FAMILY = "Consolas"


def build_main_style(font_color: str = "#333333", bg_color: str = "rgba(255, 255, 255, 0.7)", font_size: int = 13) -> str:
    return f"""
        QWidget#MainFrame {{
            background-color: transparent;
            border: none;
        }}
        QTextEdit {{
            background-color: {bg_color};
            color: {font_color};
            border: none;
            border-radius: 4px;
            font-family: "{FONT_FAMILY}", "Cascadia Code", "Consolas", monospace;
            font-size: {font_size}px;
            line-height: 1.5;
            padding: 10px;
            selection-background-color: {font_color};
            selection-color: black;
        }}

        /* 自定义滚动条 - 极细低调 */
        QScrollBar:vertical {{
            border: none;
            background: transparent;
            width: 4px;
            margin: 0px;
        }}
        QScrollBar::handle:vertical {{
            background: rgba(255, 255, 255, 0.2);
            min-height: 20px;
            border-radius: 2px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: rgba(255, 255, 255, 0.4);
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
    """


logger = get_logger("main_window")


class StealthAssistant(QMainWindow):
    """UI-only overlay backed by an ApplicationController."""

    def __init__(
        self,
        ai_service=None,
        audio_capture=None,
        screenshot_provider=None,
        protection_service=None,
        controller=None,
    ):
        super().__init__()
        self._active_task_ids: set[str] = set()
        self.signals = WorkerSignals()
        self.tray_manager = None
        self.protection_service = (
            protection_service if protection_service is not None else stealth_manager
        )

        self.controller = controller
        if self.controller is None:
            legacy_services = (ai_service, audio_capture, screenshot_provider)
            if any(service is not None for service in legacy_services):
                if not all(service is not None for service in legacy_services):
                    raise ValueError(
                        "ai_service, audio_capture, and screenshot_provider must be provided together"
                    )
                self.controller = ApplicationController(
                    ai_service,
                    audio_capture,
                    screenshot_provider,
                )
            else:
                self.controller = create_default_controller()

        # Compatibility aliases used by diagnostics and later lifecycle work.
        self.ai_service = self.controller.ai_service
        self.audio_capture = self.controller.audio_capture
        self.screenshot_provider = self.controller.screenshot_provider

        self.controller.start()
        print(f"初始化完成！当前使用的模型是: {MODEL_ID}")
        self._init_ui()
        self._connect_signals()
        self._apply_stealth()
        self._setup_hotkeys()
        self._setup_tray()
        self._load_initial_content()

    def _load_initial_content(self):
        if LOAD_TEST_FILE and os.path.exists(TEST_FILE_PATH):
            try:
                with open(TEST_FILE_PATH, "r", encoding="utf-8") as file:
                    content = file.read()
                if content.strip():
                    self._append_html(markdown_to_html(content))
            except Exception as exc:
                print(f"无法加载初始文件: {exc}")

    def _connect_signals(self):
        self.signals.toggle_visible.connect(self._handle_toggle_visible)
        self.signals.screenshot_requested.connect(self._handle_screenshot)
        self.signals.move_window.connect(self._handle_move_window)
        self.signals.scroll_content.connect(self._handle_scroll_content)
        self.signals.exit_app.connect(self._handle_exit)
        self.signals.audio_capture_requested.connect(self._handle_audio_capture)

        self.controller.task_started.connect(self._handle_task_started)
        self.controller.task_content_started.connect(self._handle_task_content_started)
        self.controller.task_completed.connect(self._handle_task_completed)
        self.controller.task_failed.connect(self._handle_task_failed)

    def _setup_hotkeys(self):
        hotkeys = HOTKEY_CONFIG
        bindings = [
            (hotkeys["toggle_visible"], lambda: self.signals.toggle_visible.emit()),
            (hotkeys["screenshot"], lambda: self.signals.screenshot_requested.emit()),
            (hotkeys["move_left"], lambda: self.signals.move_window.emit(-MOVE_STEP)),
            (hotkeys["move_right"], lambda: self.signals.move_window.emit(MOVE_STEP)),
            (hotkeys["scroll_up"], lambda: self.signals.scroll_content.emit(-SCROLL_STEP)),
            (hotkeys["scroll_down"], lambda: self.signals.scroll_content.emit(SCROLL_STEP)),
            (hotkeys["exit"], lambda: self.signals.exit_app.emit()),
        ]

        audio_key = hotkeys.get("audio_capture")
        if audio_key:
            bindings.append(
                (audio_key, lambda: self.signals.audio_capture_requested.emit())
            )

        for key, callback in bindings:
            try:
                keyboard.add_hotkey(key, callback, suppress=True)
            except Exception as exc:
                print(f"快捷键 {key} 注册失败: {exc}")

        print(f"快捷键已注册: {', '.join(key for key, _ in bindings)}")
        health_registry.update(
            "hotkeys",
            "healthy",
            "Global hotkeys registered",
            {"count": len(bindings)},
        )
        logger.info(
            "Global hotkeys registered; count=%d",
            len(bindings),
            extra={"component": "hotkeys", "event": "registered", "task_id": None},
        )

    def _setup_tray(self):
        self.tray_manager = TrayManager(self)
        self.tray_manager.show()

    def _handle_toggle_visible(self):
        self._assert_gui_thread()
        if self.isVisible():
            self.hide()
        else:
            self.showNormal()

    def _handle_exit(self):
        self._assert_gui_thread()
        if self.tray_manager:
            self.tray_manager.hide()
        QApplication.quit()

    def _apply_stealth(self):
        if sys.platform == "win32":
            from PyQt5.QtCore import QTimer

            QTimer.singleShot(100, self._do_apply_stealth)

    def _do_apply_stealth(self):
        self._assert_gui_thread()
        try:
            hwnd = int(self.winId())
            results = self.protection_service.apply_all_protections(hwnd)
            print(f"隐蔽保护应用结果: {results}")
        except Exception as exc:
            print(f"隐蔽保护应用失败: {exc}")

    def _init_ui(self):
        self.setWindowFlags(
            Qt.Tool
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground)

        central_widget = QWidget()
        central_widget.setObjectName("MainFrame")

        def get_rgba(color, opacity):
            value = color.lstrip("#")
            if len(value) == 3:
                value = "".join(character + character for character in value)
            if len(value) == 6:
                red, green, blue = tuple(
                    int(value[index:index + 2], 16) for index in (0, 2, 4)
                )
                return f"rgba({red}, {green}, {blue}, {opacity})"
            return color

        final_font_color = get_rgba(
            TEXT_CONFIG["font_color"],
            TEXT_CONFIG.get("text_opacity", 1.0),
        )
        style = build_main_style(
            font_color=final_font_color,
            bg_color=TEXT_CONFIG.get("bg_color", "rgba(255, 255, 255, 0.7)"),
            font_size=TEXT_CONFIG["font_size"],
        )
        central_widget.setStyleSheet(style)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)
        self.text_area.setPlaceholderText("Ready. Press Alt+S to capture screen.")
        self.text_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.text_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.text_area.setFrameStyle(0)

        css = get_markdown_css(
            font_color=TEXT_CONFIG["font_color"],
            font_size=TEXT_CONFIG["font_size"],
            line_height=TEXT_CONFIG.get("line_height", 1.5),
            text_opacity=TEXT_CONFIG.get("text_opacity", 1.0),
        ).replace("<style>", "").replace("</style>", "")
        self.text_area.document().setDefaultStyleSheet(css)

        main_layout.addWidget(self.text_area)
        self.setCentralWidget(central_widget)

        window_config = WINDOW_CONFIG
        screen = QDesktopWidget().screenGeometry()
        print(f"当前屏幕分辨率: {screen.width()}x{screen.height()}")
        print(
            "📐 尝试应用窗口配置: "
            f"x={window_config['x']}, y={window_config['y']}, "
            f"w={window_config['width']}, h={window_config['height']}, "
            f"opacity={window_config['opacity']}"
        )
        self.setGeometry(
            window_config["x"],
            window_config["y"],
            window_config["width"],
            window_config["height"],
        )
        self.setWindowOpacity(window_config["opacity"])
        self.raise_()

    def _handle_move_window(self, delta_x: int):
        self._assert_gui_thread()
        geometry = self.geometry()
        screen_geometry = QDesktopWidget().availableGeometry(self)
        minimum_x = screen_geometry.x()
        maximum_x = screen_geometry.x() + screen_geometry.width() - geometry.width()
        new_x = max(minimum_x, min(geometry.x() + delta_x, maximum_x))
        self.move(new_x, geometry.y())

    def _handle_scroll_content(self, delta: int):
        self._assert_gui_thread()
        scrollbar = self.text_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.value() + delta)

    def _handle_screenshot(self):
        self._assert_gui_thread()
        self._verify_window_protection()
        self.controller.request_screenshot()

    def _handle_audio_capture(self):
        self._assert_gui_thread()
        self._verify_window_protection()
        self.controller.request_audio_capture()

    def showEvent(self, event):
        super().showEvent(event)
        if sys.platform == "win32":
            from PyQt5.QtCore import QTimer

            QTimer.singleShot(0, self._verify_window_protection)

    def _verify_window_protection(self):
        self._assert_gui_thread()
        verifier = getattr(self.protection_service, "verify_or_reapply", None)
        if verifier is None:
            return
        try:
            verifier(int(self.winId()))
        except Exception:
            logger.exception(
                "Window protection verification failed",
                extra={
                    "component": "window_protection",
                    "event": "verification_failed",
                    "task_id": None,
                },
            )

    def _handle_task_started(self, task_id: str, _kind: str):
        self._assert_gui_thread()
        self._active_task_ids.add(task_id)

    def _handle_task_content_started(self, task_id: str, status: str):
        self._assert_gui_thread()
        if task_id not in self._active_task_ids:
            return
        self._append_html(self._task_padding())
        self._update_status(status, task_id)

    def _handle_task_completed(self, task_id: str, html: str):
        self._assert_gui_thread()
        if task_id not in self._active_task_ids:
            return
        if html:
            self._append_html(html)
        self._append_html(self._task_padding())
        self._active_task_ids.discard(task_id)
        self._update_status("ready", task_id)

    def _handle_task_failed(self, task_id: str, error_message: str):
        self._assert_gui_thread()
        if task_id not in self._active_task_ids:
            return
        self._active_task_ids.discard(task_id)
        self._show_error(error_message, task_id)

    @staticmethod
    def _task_padding() -> str:
        return "<br>" * TEXT_CONFIG.get("padding_lines", 0)

    def _append_html(self, html: str):
        self._assert_gui_thread()
        cursor = self.text_area.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.text_area.setTextCursor(cursor)
        self.text_area.insertHtml(html)
        self.text_area.ensureCursorVisible()

    def _update_status(self, text: str, task_id: str | None = None):
        self._assert_gui_thread()
        print(f"[Status] {text}")
        logger.info(
            "UI task status: %s",
            text,
            extra={"component": "ui", "event": "task_status", "task_id": task_id},
        )

    def _show_error(self, error_message: str, task_id: str | None = None):
        self._assert_gui_thread()
        health_registry.update("last_task", "failed", error_message)
        logger.error(
            "UI task error: %s",
            error_message,
            extra={"component": "ui", "event": "task_error", "task_id": task_id},
        )
        font_color = TEXT_CONFIG.get("font_color", "#ff5555")
        self._append_html(
            f"<div style='color:{font_color}; font-size:11px;'>"
            f"Error: {error_message}</div>"
        )

    def _assert_gui_thread(self):
        if QThread.currentThread() is not self.thread():
            raise RuntimeError("QWidget access attempted outside the GUI thread")
