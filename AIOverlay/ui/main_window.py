# -*- coding: utf-8 -*-
"""
主窗口模块 - 纯快捷键驱动、鼠标穿透的隐蔽覆盖层
"""

import os
import io
import sys
import threading

from PyQt5.QtWidgets import (
    QMainWindow, QTextEdit, QVBoxLayout, QWidget, QApplication, QDesktopWidget
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QTextCursor
from PIL import ImageGrab
import keyboard

from AIOverlay.config import (
    WINDOW_CONFIG, TEXT_CONFIG, HOTKEY_CONFIG,
    SCROLL_STEP, MOVE_STEP, LOAD_TEST_FILE, TEST_FILE_PATH
)
from AIOverlay.ai_service import AIService
from AIOverlay.stealth import stealth_manager
from AIOverlay.utils.signals import WorkerSignals
from AIOverlay.utils.markdown_renderer import markdown_to_html, get_markdown_css
from AIOverlay.ui.tray import TrayManager
from AIOverlay.ui.styles import build_main_style


class StealthAssistant(QMainWindow):
    """隐蔽AI助手主窗口 - 纯展示层"""

    def __init__(self):
        super().__init__()

        # Markdown 流式累积缓冲区
        self._markdown_buffer = ""

        # 截屏锁 (防止重复触发)
        self._screenshot_lock = False

        # 信号
        self.signals = WorkerSignals()

        # 初始化组件
        self.ai_service = AIService()
        self.tray_manager = None

        # 初始化
        self._init_ai()
        self._init_ui()
        self._connect_signals()
        self._apply_stealth()
        self._setup_hotkeys()
        self._setup_tray()
        
        # 启动时加载初始内容
        self._load_initial_content()

    def _load_initial_content(self):
        """如果开启了配置，则加载初始测试文件内容"""
        if LOAD_TEST_FILE and os.path.exists(TEST_FILE_PATH):
            try:
                with open(TEST_FILE_PATH, 'r', encoding='utf-8') as f:
                    content = f.read()
                if content.strip():
                    html = markdown_to_html(content)
                    self.signals.update_output.emit(html)
            except Exception as e:
                print(f"无法加载初始文件: {e}")

    def _connect_signals(self):
        """连接信号到槽"""
        self.signals.update_output.connect(self._append_html)
        self.signals.stream_output.connect(self._append_stream)
        self.signals.update_status.connect(self._update_status)
        self.signals.error.connect(self._show_error)
        self.signals.toggle_visible.connect(self._handle_toggle_visible)
        self.signals.screenshot_requested.connect(self._handle_screenshot)
        self.signals.move_window.connect(self._handle_move_window)
        self.signals.scroll_content.connect(self._handle_scroll_content)
        self.signals.exit_app.connect(self._handle_exit)

    def _setup_hotkeys(self):
        """设置全局快捷键"""
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

        for key, callback in bindings:
            try:
                keyboard.add_hotkey(key, callback)
            except Exception as e:
                print(f"快捷键 {key} 注册失败: {e}")

        print(f"快捷键已注册: {', '.join(h for h, _ in bindings)}")

    def _setup_tray(self):
        """设置系统托盘"""
        self.tray_manager = TrayManager(self)
        self.tray_manager.show()

    def _handle_toggle_visible(self):
        """切换窗口可见性"""
        if self.isVisible():
            self.hide()
        else:
            self.showNormal()

    def _handle_exit(self):
        """紧急退出"""
        if self.tray_manager:
            self.tray_manager.hide()
        QApplication.quit()

    def _init_ai(self):
        """初始化AI服务"""
        try:
            self.ai_service.create_session()
            print("AI 初始化完成")
        except Exception as e:
            print(f"AI 初始化失败: {e}")

    def _apply_stealth(self):
        """应用隐蔽保护"""
        if sys.platform == "win32":
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(100, self._do_apply_stealth)

    def _do_apply_stealth(self):
        """执行隐蔽保护"""
        try:
            hwnd = int(self.winId())
            results = stealth_manager.apply_all_protections(hwnd)
            print(f"隐蔽保护应用结果: {results}")
        except Exception as e:
            print(f"隐蔽保护应用失败: {e}")

    def _init_ui(self):
        """初始化UI - 极简布局"""
        # 窗口属性
        self.setWindowFlags(
            Qt.Tool |                       # 不在任务栏显示
            Qt.FramelessWindowHint |         # 无边框
            Qt.WindowStaysOnTopHint |        # 置顶
            Qt.WindowTransparentForInput     # Qt级别鼠标穿透
        )
        self.setAttribute(Qt.WA_TranslucentBackground)

        # 主容器
        central_widget = QWidget()
        central_widget.setObjectName("MainFrame")

        # 辅助函数：将 #RRGGBB 转换为带透明度的 rgba
        def get_rgba(color, opacity):
            c = color.lstrip('#')
            if len(c) == 3: c = ''.join(x + x for x in c)
            if len(c) == 6:
                r, g, b = tuple(int(c[i:i+2], 16) for i in (0, 2, 4))
                return f"rgba({r}, {g}, {b}, {opacity})"
            return color

        # 应用配置驱动的样式
        final_font_color = get_rgba(TEXT_CONFIG["font_color"], TEXT_CONFIG.get("text_opacity", 1.0))
        style = build_main_style(
            font_color=final_font_color,
            bg_color=TEXT_CONFIG.get("bg_color", "rgba(255, 255, 255, 0.7)"),
            font_size=TEXT_CONFIG["font_size"]
        )
        central_widget.setStyleSheet(style)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 唯一的UI元素：只读输出框
        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)
        self.text_area.setPlaceholderText("Ready. Press Alt+S to capture screen.")
        self.text_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # 注入 Markdown CSS (同步配置的字体颜色、大小、行间距和透明度)
        css = get_markdown_css(
            font_color=TEXT_CONFIG["font_color"],
            font_size=TEXT_CONFIG["font_size"],
            line_height=TEXT_CONFIG.get("line_height", 1.5),
            text_opacity=TEXT_CONFIG.get("text_opacity", 1.0)
        ).replace("<style>", "").replace("</style>", "")
        self.text_area.document().setDefaultStyleSheet(css)

        main_layout.addWidget(self.text_area)
        self.setCentralWidget(central_widget)

        # 最后应用从配置读取的窗口位置、大小和透明度
        wc = WINDOW_CONFIG
        screen = QDesktopWidget().screenGeometry()
        print(f"🖥️ 当前屏幕分辨率: {screen.width()}x{screen.height()}")
        print(f"📐 尝试应用窗口配置: x={wc['x']}, y={wc['y']}, w={wc['width']}, h={wc['height']}, opacity={wc['opacity']}")
        
        self.setGeometry(wc["x"], wc["y"], wc["width"], wc["height"])
        self.setWindowOpacity(wc["opacity"])
        self.raise_()  # 确保在最前面

    # ========== 窗口移动 (内存中直接修改) ==========

    def _handle_move_window(self, delta_x: int):
        """
        移动窗口位置，带屏幕边界钳制
        
        Args:
            delta_x: 水平移动像素 (正=右, 负=左)
        """
        geo = self.geometry()
        screen_geo = QDesktopWidget().availableGeometry(self)

        new_x = geo.x() + delta_x

        # 钳制到屏幕边界
        min_x = screen_geo.x()
        max_x = screen_geo.x() + screen_geo.width() - geo.width()
        new_x = max(min_x, min(new_x, max_x))

        self.move(new_x, geo.y())

    # ========== 内容滚动 ==========

    def _handle_scroll_content(self, delta: int):
        """
        滚动输出框内容
        
        Args:
            delta: 滚动像素 (正=下, 负=上)
        """
        scrollbar = self.text_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.value() + delta)

    # ========== 截图功能 ==========

    def _handle_screenshot(self):
        """处理截图 (快捷键触发)"""
        if self._screenshot_lock:
            return

        self._screenshot_lock = True
        threading.Thread(target=self._bg_screenshot, daemon=True).start()

    def _bg_screenshot(self):
        """后台截图处理"""
        try:
            # 直接截屏，无需 hide/show
            # WDA_EXCLUDEFROMCAPTURE 已保证截图不包含自身
            img = ImageGrab.grab()

            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='JPEG')
            img_bytes = img_byte_arr.getvalue()

            self.signals.update_status.emit("sending...")

            prompt_text = "请分析这张屏幕截图的内容。"
            prompt = self.ai_service.create_text_part(prompt_text)
            image_part = self.ai_service.create_image_part(img_bytes)

            # 发送截图标记与前置填充
            padding = "<br>" * TEXT_CONFIG.get("padding_lines", 0)
            self.signals.update_output.emit(
                f"{padding}<div style='color:#888; font-size:10px; margin-top:15px;'>[screenshot captured]</div>"
            )

            # 流式请求
            self._start_markdown_block()
            for chunk in self.ai_service.send_stream([prompt, image_part]):
                self.signals.stream_output.emit(chunk)
            self._flush_markdown_buffer()
            
            # 后置填充
            self.signals.update_output.emit(padding)

            self.signals.update_status.emit("ready")

        except Exception as e:
            self.signals.error.emit(f"截图处理错误: {e}")
        finally:
            self._screenshot_lock = False

    # ========== UI更新 ==========

    def _append_html(self, html):
        """添加HTML到输出区域"""
        cursor = self.text_area.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.text_area.setTextCursor(cursor)
        self.text_area.insertHtml(html)
        self.text_area.ensureCursorVisible()

    def _append_stream(self, text):
        """流式添加文本到缓冲区"""
        self._markdown_buffer += text

    def _flush_markdown_buffer(self):
        """将缓冲区的 Markdown 转换为 HTML 并显示"""
        if self._markdown_buffer:
            html = markdown_to_html(self._markdown_buffer)
            self._append_html(html)
            self._markdown_buffer = ""

    def _start_markdown_block(self):
        """开始新的 Markdown 块"""
        self._markdown_buffer = ""

    def _update_status(self, text):
        """更新状态 (通过窗口标题，虽然不可见但可用于调试)"""
        print(f"[Status] {text}")

    def _show_error(self, err_msg):
        """在输出区域显示错误"""
        self._append_html(
            f"<div style='color:#ff5555; font-size:11px;'>Error: {err_msg}</div>"
        )
