# -*- coding: utf-8 -*-
"""Transparent overlay window. All QWidget access stays on the GUI thread."""

import ctypes
import os
import sys
import time
from ctypes import wintypes

import keyboard
import mouse
from PyQt5.QtCore import QEvent, QObject, QThread, QTimer, Qt, pyqtSignal
from PyQt5.QtGui import QTextCursor
from PyQt5.QtWidgets import (
    QApplication,
    QDesktopWidget,
    QMainWindow,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from DesktopCompanion.config import (
    HOTKEY_CONFIG,
    LOAD_TEST_FILE,
    MOVE_STEP,
    SCROLL_STEP,
    TEST_FILE_PATH,
    TEXT_CONFIG,
    TRIPLE_CLICK_INTERVAL_MS,
    WINDOW_CONFIG,
    WINDOW_TITLE,
)
from DesktopCompanion.controllers.application_controller import create_default_controller
from DesktopCompanion.platform.window_protection import window_protection_manager
from DesktopCompanion.ui.tray import TrayManager
from DesktopCompanion.utils.markdown_renderer import get_markdown_css, markdown_to_html


class WorkerSignals(QObject):
    toggle_visible = pyqtSignal()
    screenshot_requested = pyqtSignal()
    move_window = pyqtSignal(int)
    scroll_content = pyqtSignal(int)
    exit_app = pyqtSignal()
    audio_capture_requested = pyqtSignal()


FONT_FAMILY = "Consolas"


def build_main_style(font_color: str = "#333333", font_size: int = 13) -> str:
    return f"""
        QWidget#MainFrame {{
            background-color: transparent;
            border: none;
        }}
        QTextEdit {{
            background-color: transparent;
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


def _to_rgba(color, opacity):
    value = color.lstrip("#")
    if len(value) == 3:
        value = "".join(character + character for character in value)
    if len(value) == 6:
        red, green, blue = tuple(
            int(value[index:index + 2], 16) for index in (0, 2, 4)
        )
        return f"rgba({red}, {green}, {blue}, {opacity})"
    return color


class OverlayAssistant(QMainWindow):
    """UI-only overlay backed by an ApplicationController."""

    PROTECTION_CHECK_INTERVAL_MS = 100
    PROTECTION_NATIVE_MESSAGES = frozenset(
        {
            0x001A,  # WM_SETTINGCHANGE
            0x007E,  # WM_DISPLAYCHANGE
            0x0218,  # WM_POWERBROADCAST
            0x0219,  # WM_DEVICECHANGE
            0x02B1,  # WM_WTSSESSION_CHANGE
            0x02E0,  # WM_DPICHANGED
            0x031E,  # WM_DWMCOMPOSITIONCHANGED
        }
    )
    PROTECTION_EVENT_TYPES = frozenset(
        event_type
        for event_type in (
            getattr(QEvent, "WinIdChange", None),
            getattr(QEvent, "ScreenChangeInternal", None),
            getattr(QEvent, "WindowStateChange", None),
            getattr(QEvent, "ApplicationStateChange", None),
        )
        if event_type is not None
    )

    def __init__(self, controller=None):
        super().__init__()
        self.signals = WorkerSignals()
        self.tray_manager = None
        self.protection_service = window_protection_manager
        self.controller = controller or create_default_controller()
        self._target_window_opacity = 1.0
        self._protection_healthy = sys.platform != "win32"
        self._visibility_requested = False
        self._protected_hwnd = None
        self._protection_timer = None
        self._protection_check_scheduled = False
        self._content_fragments = []
        self._surface_content_rendered = False
        self._hotkey_handles = []
        self._mouse_hook = None
        self._left_click_times = []
        self._shutdown_started = False

        self.controller.start()
        print(f"初始化完成！当前优先模型是: {self.controller.current_model_id}")
        self._init_ui()
        self._connect_signals()
        self._setup_window_protection()
        self._setup_hotkeys()
        self._setup_mouse_listener()
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
                handle = keyboard.add_hotkey(key, callback, suppress=True)
                self._hotkey_handles.append(handle)
            except Exception as exc:
                print(f"快捷键 {key} 注册失败: {exc}")

        print(f"快捷键已注册: {', '.join(key for key, _ in bindings)}")

    def _setup_mouse_listener(self):
        try:
            self._mouse_hook = mouse.hook(self._handle_global_mouse_event)
        except Exception as exc:
            print(f"鼠标左键三击注册失败: {exc}")

    def _handle_global_mouse_event(self, event):
        if not isinstance(event, mouse.ButtonEvent):
            return
        if event.button != mouse.LEFT or event.event_type not in (
            mouse.DOWN,
            mouse.DOUBLE,
        ):
            return

        now = time.monotonic()
        interval_seconds = TRIPLE_CLICK_INTERVAL_MS / 1000.0
        self._left_click_times = [
            click_time
            for click_time in self._left_click_times
            if now - click_time <= interval_seconds
        ]
        self._left_click_times.append(now)
        if len(self._left_click_times) >= 3:
            self._left_click_times.clear()
            self.signals.screenshot_requested.emit()

    def _setup_tray(self):
        self.tray_manager = TrayManager(self)
        self.tray_manager.show()

    def toggle_visibility(self):
        self._handle_toggle_visible()

    def _handle_toggle_visible(self):
        self._assert_gui_thread()
        if self._visibility_requested:
            self._visibility_requested = False
            self.hide()
        else:
            self.show_protected()

    def _handle_exit(self):
        self._assert_gui_thread()
        self.shutdown()
        QApplication.quit()

    def shutdown(self):
        """Release resources for normal Qt, tray, and hotkey exits."""
        if self._shutdown_started:
            return
        self._shutdown_started = True
        self._visibility_requested = False
        if self._protection_timer is not None:
            self._protection_timer.stop()

        handles, self._hotkey_handles = self._hotkey_handles, []
        for handle in handles:
            try:
                keyboard.remove_hotkey(handle)
            except Exception:
                pass

        mouse_hook, self._mouse_hook = self._mouse_hook, None
        if mouse_hook is not None:
            try:
                mouse.unhook(mouse_hook)
            except Exception:
                pass
        self._left_click_times.clear()

        if self.tray_manager:
            self.tray_manager.hide()
        try:
            self.controller.stop()
        finally:
            self.setWindowOpacity(0.0)
            self._clear_sensitive_surface()

    def closeEvent(self, event):
        self.shutdown()
        super().closeEvent(event)

    def _setup_window_protection(self):
        if sys.platform != "win32":
            return

        self._protection_timer = QTimer(self)
        self._protection_timer.setTimerType(Qt.PreciseTimer)
        self._protection_timer.setInterval(self.PROTECTION_CHECK_INTERVAL_MS)
        self._protection_timer.timeout.connect(self._protection_tick)
        self._protection_timer.start()

        desktop = QApplication.desktop()
        for signal_name in ("screenCountChanged", "resized", "workAreaResized"):
            signal = getattr(desktop, signal_name, None)
            if signal is not None:
                signal.connect(lambda *_args: self._schedule_protection_check())

        # winId() creates the native HWND while the widget is still hidden.
        self._verify_window_protection(force_apply=True)

    def show_protected(self):
        """Show only after the native window has exact capture exclusion."""
        self._assert_gui_thread()
        self._visibility_requested = True
        self.setWindowOpacity(0.0)
        if self._verify_window_protection():
            self._show_after_precheck()

    def _show_after_precheck(self):
        if not self._visibility_requested or self.isVisible():
            return
        self.setWindowOpacity(0.0)
        super().showNormal()

    def _protection_tick(self):
        self._assert_gui_thread()
        if not self._visibility_requested and not self.isVisible():
            return
        healthy = self._verify_window_protection()
        if not healthy or not self._visibility_requested:
            return
        if self.isVisible():
            self._activate_protected_surface(already_verified=True)
        else:
            self._show_after_precheck()

    def _schedule_protection_check(self):
        if sys.platform != "win32" or self._protection_check_scheduled:
            return
        self._protection_check_scheduled = True
        QTimer.singleShot(0, self._run_scheduled_protection_check)

    def _run_scheduled_protection_check(self):
        self._protection_check_scheduled = False
        if not self._visibility_requested and not self.isVisible():
            return
        healthy = self._verify_window_protection()
        if not healthy or not self._visibility_requested:
            return
        if self.isVisible():
            self._activate_protected_surface(already_verified=True)
        else:
            self._show_after_precheck()

    def _activate_protected_surface(self, already_verified: bool = False):
        if not self._visibility_requested or not self.isVisible():
            return
        if not already_verified and not self._verify_window_protection():
            return
        needs_activation = not self._surface_content_rendered
        if not self._surface_content_rendered:
            self._render_all_content()
        if abs(self.windowOpacity() - self._target_window_opacity) > 0.001:
            self.setWindowOpacity(self._target_window_opacity)
            needs_activation = True
        if needs_activation:
            self.raise_()

    def _enter_fail_closed(self):
        self._protection_healthy = False
        self.setWindowOpacity(0.0)
        self._clear_sensitive_surface()
        if self.isVisible():
            super().hide()

    def _init_ui(self):
        self.setWindowTitle(WINDOW_TITLE)
        self.setWindowFlags(
            Qt.Tool
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAutoFillBackground(False)

        central_widget = QWidget()
        central_widget.setObjectName("MainFrame")
        central_widget.setAutoFillBackground(False)

        final_font_color = _to_rgba(
            TEXT_CONFIG["font_color"],
            TEXT_CONFIG.get("text_opacity", 1.0),
        )
        style = build_main_style(
            font_color=final_font_color,
            font_size=TEXT_CONFIG["font_size"],
        )
        central_widget.setStyleSheet(style)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.text_area = QTextEdit()
        self.text_area.setAutoFillBackground(False)
        self.text_area.viewport().setAutoFillBackground(False)
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
            "尝试应用窗口配置: "
            f"x={window_config['x']}, y={window_config['y']}, "
            f"w={window_config['width']}, h={window_config['height']}"
        )
        self.setGeometry(
            window_config["x"],
            window_config["y"],
            window_config["width"],
            window_config["height"],
        )
        # Keep the native surface transparent until capture protection is verified.
        self.setWindowOpacity(0.0)

    def _handle_move_window(self, delta_x: int):
        self._assert_gui_thread()
        geometry = self.geometry()
        screen_geometry = QDesktopWidget().availableGeometry(self)
        minimum_x = screen_geometry.x()
        maximum_x = screen_geometry.x() + screen_geometry.width() - geometry.width()
        new_x = max(minimum_x, min(geometry.x() + delta_x, maximum_x))
        self.move(new_x, geometry.y())
        self._schedule_protection_check()

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
            self.setWindowOpacity(0.0)
            self._schedule_protection_check()
        else:
            self._activate_protected_surface(already_verified=True)

    def event(self, event):
        result = super().event(event)
        if (
            sys.platform == "win32"
            and hasattr(self, "_protection_check_scheduled")
            and event.type() in self.PROTECTION_EVENT_TYPES
        ):
            self._schedule_protection_check()
        return result

    def nativeEvent(self, event_type, message):
        result = super().nativeEvent(event_type, message)
        if sys.platform != "win32":
            return result
        try:
            native_message = ctypes.cast(
                int(message),
                ctypes.POINTER(wintypes.MSG),
            ).contents.message
            if native_message in self.PROTECTION_NATIVE_MESSAGES:
                self._schedule_protection_check()
        except Exception:
            pass
        return result

    def _verify_window_protection(self, force_apply: bool = False) -> bool:
        self._assert_gui_thread()
        if sys.platform != "win32":
            self._protection_healthy = True
            return True

        verifier = getattr(self.protection_service, "verify_or_reapply", None)
        try:
            hwnd = int(self.winId())
            if hwnd != self._protected_hwnd:
                previous_hwnd = self._protected_hwnd
                self._protected_hwnd = hwnd
                force_apply = True
                if previous_hwnd is not None:
                    forgetter = getattr(self.protection_service, "forget_window", None)
                    if forgetter is not None:
                        forgetter(previous_hwnd)

            if force_apply or verifier is None:
                results = self.protection_service.apply_all_protections(hwnd)
            else:
                results = verifier(hwnd)

            health_checker = getattr(
                self.protection_service,
                "results_are_healthy",
                None,
            )
            if health_checker is not None:
                healthy = bool(health_checker(results))
            else:
                required = (
                    "capture_protection",
                    "desktop_duplication_exclusion",
                    "alt_tab_hidden",
                    "title_set",
                    "mouse_passthrough",
                )
                healthy = all(results.get(key) is True for key in required)
        except Exception:
            healthy = False

        if healthy:
            self._protection_healthy = True
            return True

        self._enter_fail_closed()
        return False

    def _handle_task_content_started(self, _status: str):
        self._assert_gui_thread()
        self._append_html(self._task_padding())

    def _handle_task_completed(self, html: str):
        self._assert_gui_thread()
        if html:
            self._append_html(html)
        self._append_html(self._task_padding())

    def _handle_task_failed(self, error_message: str):
        self._assert_gui_thread()
        self._show_error(error_message)

    @staticmethod
    def _task_padding() -> str:
        return "<br>" * TEXT_CONFIG.get("padding_lines", 0)

    def _append_html(self, html: str):
        self._assert_gui_thread()
        if not html:
            return
        self._content_fragments.append(html)
        if not self._visibility_requested or not self.isVisible():
            self._surface_content_rendered = False
            return
        if not self._verify_window_protection():
            return
        if not self._surface_content_rendered:
            self._render_all_content()
            return
        self._insert_html_into_surface(html)

    def _insert_html_into_surface(self, html: str):
        cursor = self.text_area.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.text_area.setTextCursor(cursor)
        self.text_area.insertHtml(html)
        self.text_area.ensureCursorVisible()

    def _render_all_content(self):
        self.text_area.clear()
        for fragment in self._content_fragments:
            self._insert_html_into_surface(fragment)
        self._surface_content_rendered = True

    def _clear_sensitive_surface(self):
        self.text_area.clear()
        self._surface_content_rendered = False

    def _show_error(self, error_message: str):
        self._assert_gui_thread()
        font_color = _to_rgba(
            TEXT_CONFIG.get("font_color", "#ff5555"),
            TEXT_CONFIG.get("text_opacity", 1.0),
        )
        font_size = TEXT_CONFIG.get("font_size", 11)
        self._append_html(
            f"<div style='color:{font_color}; font-size:{font_size}px;'>"
            f"Error: {error_message}</div>"
        )

    def _assert_gui_thread(self):
        if QThread.currentThread() is not self.thread():
            raise RuntimeError("QWidget access attempted outside the GUI thread")
