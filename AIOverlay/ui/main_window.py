# -*- coding: utf-8 -*-
"""
主窗口模块
"""


import time
import sys
import io
import threading

from PyQt5.QtWidgets import (
    QMainWindow, QTextEdit, QVBoxLayout, QWidget, QPushButton, 
    QLabel, QHBoxLayout, QFrame
)
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QTextCursor
from PIL import ImageGrab
import keyboard

from AIOverlay.config import (
    GLOBAL_HOTKEY, FLASH_MODELS,
    WINDOW_DEFAULT_WIDTH, WINDOW_DEFAULT_HEIGHT,
    WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT,
    SYSTEM_PROMPT
)

from AIOverlay.ai_service import AIService
from AIOverlay.audio_handler import AudioHandler
from AIOverlay.stealth import stealth_manager
from AIOverlay.utils.signals import WorkerSignals
from AIOverlay.utils.markdown_renderer import markdown_to_html, get_markdown_css

from AIOverlay.ui.widgets import VolumeIndicator, OpacityControl, InlineSelector, stealth_warning, stealth_critical
from AIOverlay.ui.tray import TrayManager
from AIOverlay.ui.styles import (
    MAIN_WINDOW_STYLE, CLOSE_BUTTON_STYLE, PRIMARY_BUTTON_STYLE,
    RECORDING_BUTTON_STYLE, SCREENSHOT_BUTTON_STYLE, SCROLL_BUTTON_STYLE,
    COMBOBOX_STYLE
)


class StealthAssistant(QMainWindow):
    """隐蔽AI助手主窗口"""
    
    def __init__(self):
        super().__init__()
        
        # 状态
        self.is_recording = False
        self.old_pos = None
        self._resize_edge = None
        self._start_geometry = None
        
        # Markdown 流式累积缓冲区
        self._markdown_buffer = ""
        
        # 模型配置
        self.current_flash_id = FLASH_MODELS[0][1]
        
        # 索引记录
        self.last_flash_index = 0
        
        # 信号
        self.signals = WorkerSignals()
        
        # 初始化组件
        self.ai_service = AIService()
        self.audio_handler = AudioHandler()
        self.tray_manager = None
        
        # 初始化
        self._init_ai()
        self._init_ui()
        self._connect_signals()
        self._apply_stealth()
        self._setup_hotkeys()
        self._setup_tray()
        
    def _connect_signals(self):
        """连接信号到槽"""
        self.signals.update_left.connect(self._append_html)
        self.signals.stream_left.connect(self._append_stream)
        self.signals.update_status.connect(self._update_status_label)
        self.signals.error.connect(self._show_error)
        self.signals.toggle_visible.connect(self._handle_toggle_visible)
        self.signals.volume_update.connect(self._update_volume)
        self.signals.render_markdown.connect(self._render_markdown_content)
        
    def _setup_hotkeys(self):
        """设置全局快捷键"""
        try:
            keyboard.add_hotkey(GLOBAL_HOTKEY, lambda: self.signals.toggle_visible.emit())
            print(f"快捷键 {GLOBAL_HOTKEY} 已注册")
        except Exception as e:
            print(f"快捷键注册失败: {e}")
            
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
            self.activateWindow()
            
    def _init_ai(self):
        """初始化AI服务"""
        try:
            self.ai_service.create_flash_session(self.current_flash_id)
            print("AI 初始化完成")
        except Exception as e:
            print(f"AI 初始化失败: {e}")
            
    def _apply_stealth(self):
        """应用隐蔽保护"""
        if sys.platform == "win32":
            # 延迟应用以确保窗口已创建
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
            
    def _on_opacity_changed(self, opacity: float):
        """透明度变化回调 (使用Qt内置方法避免冲突)"""
        try:
            self.setWindowOpacity(opacity)
        except Exception:
            pass
            
    def _init_ui(self):
        """初始化UI"""
        # 窗口属性
        self.setWindowFlags(
            Qt.Tool |                    # 不在任务栏显示
            Qt.FramelessWindowHint |     # 无边框
            Qt.WindowStaysOnTopHint      # 置顶
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)  # 启用鼠标跟踪以显示调整大小光标
        self.resize(WINDOW_DEFAULT_WIDTH, WINDOW_DEFAULT_HEIGHT)
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        
        # 全局应用 ComboBox 样式
        self.setStyleSheet(COMBOBOX_STYLE)
        
        # 主容器
        central_widget = QWidget()
        central_widget.setObjectName("MainFrame")
        central_widget.setStyleSheet(MAIN_WINDOW_STYLE)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(12)
        
        # 顶部控制栏 (透明度 + 模型 + 麦克风 + 关闭)
        self._create_header_bar(main_layout)
        
        # 主内容区域 (单屏)
        self._create_main_area(main_layout)
        
        # 底部状态栏
        self._create_status_bar(main_layout)
        
        self.setCentralWidget(central_widget)
        
        # 填充设备列表 (需在UI创建完成后执行)
        self._populate_devices()
        
    def _create_header_bar(self, parent_layout):
        """创建顶部控制栏 (透明度 | 模型 | 麦克风 | 关闭)"""
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 5)
        
        # 1. 透明度 (左侧)
        header_layout.addWidget(QLabel("透明度"))
        self.opacity_control = OpacityControl(on_change=self._on_opacity_changed)
        header_layout.addWidget(self.opacity_control)
        
        header_layout.addStretch()
        
        # 2. 模型选择
        header_layout.addWidget(QLabel("模型"))
        self.combo_flash = InlineSelector()
        self.combo_flash.setMinimumWidth(100)
        self.combo_flash.setFixedHeight(24) # 略微调小
        for name, mid in FLASH_MODELS:
            self.combo_flash.addItem(name, mid)
        self.combo_flash.currentIndexChanged.connect(self._on_flash_changed)
        header_layout.addWidget(self.combo_flash)
        
        header_layout.addSpacing(10)
        
        # 3. 麦克风选择
        header_layout.addWidget(QLabel("麦克风"))
        self.combo_devices = InlineSelector()
        self.combo_devices.setMinimumWidth(120)
        self.combo_devices.setFixedHeight(24) # 略微调小
        header_layout.addWidget(self.combo_devices)
        
        header_layout.addSpacing(15)
        
        # 4. 关闭按钮
        btn_close = QPushButton("×")
        btn_close.setFixedSize(24, 24)
        btn_close.clicked.connect(self.close)
        btn_close.setStyleSheet(CLOSE_BUTTON_STYLE)
        header_layout.addWidget(btn_close)
        
        parent_layout.addLayout(header_layout)
        
    def _create_main_area(self, parent_layout):
        """创建主内容区域"""
        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)
        self.text_area.setPlaceholderText("等待指令... (Flash Model Ready)")
        
        # 注入 Markdown CSS 样式
        css = get_markdown_css().replace("<style>", "").replace("</style>", "")
        self.text_area.document().setDefaultStyleSheet(css)
        
        parent_layout.addWidget(self.text_area)
        

    def _create_status_bar(self, parent_layout):
        """创建状态栏"""
        status_layout = QHBoxLayout()
        
        self.status_label = QLabel("就绪")
        status_layout.addWidget(self.status_label)
        
        # 音量指示器
        self.volume_indicator = VolumeIndicator()
        self.volume_indicator.setFixedWidth(60)
        self.volume_indicator.hide()  # 默认隐藏，录音时显示
        status_layout.addWidget(self.volume_indicator)
        
        status_layout.addStretch()
        
        # 到底部按钮
        self.btn_scroll_bottom = QPushButton("⬇️ 到底部")
        # self.btn_scroll_bottom.setCursor(Qt.PointingHandCursor)
        self.btn_scroll_bottom.setFixedHeight(28) # 缩小高度
        self.btn_scroll_bottom.clicked.connect(self._scroll_to_bottom)
        self.btn_scroll_bottom.setStyleSheet(SCROLL_BUTTON_STYLE)
        status_layout.addWidget(self.btn_scroll_bottom)
        
        # 截屏按钮
        self.btn_screenshot = QPushButton("📸 截屏")
        # self.btn_screenshot.setCursor(Qt.PointingHandCursor)
        self.btn_screenshot.setFixedHeight(28) # 缩小高度
        self.btn_screenshot.clicked.connect(self._handle_screenshot)
        self.btn_screenshot.setStyleSheet(SCREENSHOT_BUTTON_STYLE)
        status_layout.addWidget(self.btn_screenshot)
        
        # 录音按钮
        self.btn_record = QPushButton("🎤 监听")
        # self.btn_record.setCursor(Qt.PointingHandCursor)
        self.btn_record.setFixedHeight(28) # 缩小高度
        self.btn_record.clicked.connect(self._toggle_recording)
        self.btn_record.setStyleSheet(PRIMARY_BUTTON_STYLE)
        status_layout.addWidget(self.btn_record)
        
        parent_layout.addLayout(status_layout)
        
    def _populate_devices(self):
        """填充设备列表"""
        try:
            devices = self.audio_handler.get_devices()
            self.combo_devices.clear()
            for idx, name, is_loopback in devices:
                display_name = f"⭐ {name}" if is_loopback else name
                self.combo_devices.addItem(f"{idx}: {display_name}", idx)
            if self.combo_devices.count() > 0:
                self.combo_devices.setCurrentIndex(0)
                self.audio_handler.set_device(0)
        except Exception as e:
            self._show_error(f"设备加载失败: {e}")
            
    # ========== 模式切换 ==========
    
    def _on_flash_changed(self, index):
        """Flash模型切换"""
        if self.is_recording:
            stealth_warning(self, "操作受限", "禁止切换模型")
            self.combo_flash.blockSignals(True)
            self.combo_flash.setCurrentIndex(self.last_flash_index)
            self.combo_flash.blockSignals(False)
            return
            
        new_id = self.combo_flash.itemData(index)
        if new_id != self.current_flash_id:
            self.current_flash_id = new_id
            if self.ai_service.create_flash_session(new_id):
                self._append_html(
                    f"<div style='color:#888; font-size:10px; text-align:center;'>-- 切换至 {new_id} --</div>"
                )
                self.last_flash_index = index
            else:
                self.combo_flash.blockSignals(True)
                self.combo_flash.setCurrentIndex(self.last_flash_index)
                self.combo_flash.blockSignals(False)
                
    # ========== 录音功能 ==========
    
    def _toggle_recording(self):
        """切换录音状态"""
        if not self.is_recording:
            self.is_recording = True
            self.btn_record.setText("⛔ 停止并处理")
            self.btn_record.setStyleSheet(RECORDING_BUTTON_STYLE)
            self.volume_indicator.show()
            
            self.status_label.setText(f"🎙️ 监听中...")
            
            # 设置设备
            device_idx = self.combo_devices.currentData()
            if device_idx is not None:
                self.audio_handler.set_device(device_idx)
                
            threading.Thread(target=self._bg_record_process, daemon=True).start()
        else:
            self.is_recording = False
            self.btn_record.setText("🎤 开始监听")
            self.btn_record.setStyleSheet(PRIMARY_BUTTON_STYLE)
            self.volume_indicator.hide()
            self.volume_indicator.reset()
            self.status_label.setText("⏳ 处理中...")
            
    def _bg_record_process(self):
        """后台录音处理"""
        import numpy as np
        import soundfile as sf
        import ctypes
        
        try:
            ctypes.windll.ole32.CoInitialize(None)
        except Exception:
            pass
        
        try:
            # 使用预先获取的设备列表
            idx = self.combo_devices.currentData()
            if idx is None:
                return
            
            if idx >= len(self.audio_handler.devices):
                return
            device = self.audio_handler.devices[idx]
            
            samplerate = 44100
            buffer = []
            
            with device.recorder(samplerate=samplerate) as mic:
                while self.is_recording:
                    data = mic.record(numframes=samplerate // 5)
                    buffer.append(data)
                    # 计算并发送音量
                    volume = AudioHandler.calculate_volume(data)
                    self.signals.volume_update.emit(volume)
            
            if not buffer:
                return
            
            self.signals.update_status.emit("转录音频...")
            full_audio = np.concatenate(buffer, axis=0)
            
            if np.max(np.abs(full_audio)) < 0.01:
                self.signals.update_left.emit("<div style='color:#ccc'>(无声)</div>")
                self.signals.update_status.emit("就绪")
                return
            
            temp_file = "temp_capture_stream.wav"
            sf.write(temp_file, full_audio[:, :1], samplerate)
            self._process_audio_request(temp_file)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.signals.error.emit(str(e))
        finally:
            # COM 清理
            try:
                ctypes.windll.ole32.CoUninitialize()
            except Exception:
                pass
            
    def _process_audio_request(self, file_path):
        """处理音频请求"""
        try:
            with open(file_path, "rb") as f:
                audio_bytes = f.read()
                
            self.signals.update_status.emit("正在听并思考...")
            
            # 构建音频数据包
            audio_part = self.ai_service.create_audio_part(audio_bytes)
            prompt = self.ai_service.create_text_part(SYSTEM_PROMPT)
            
            # 清理临时文件
            AudioHandler.cleanup_temp_file(file_path)
            
            # Flash请求 - 只显示最终 Markdown 渲染结果
            try:
                self.signals.update_left.emit(
                    "<div style='background-color:#e6f7ff; padding:8px; border-radius:5px; margin-bottom:5px; margin-top:20px;'><b>⚡ Flash:</b> <i>正在生成回复...</i></div>"
                )
                
                full_response = ""
                for chunk in self.ai_service.send_to_flash_stream([prompt, audio_part]):
                    full_response += chunk
                
                # 通过信号在主线程渲染完整的 Markdown
                if full_response:
                    self.signals.update_left.emit(
                        "<div style='background-color:#e6f7ff; padding:8px; border-radius:5px; margin-bottom:5px;'><b>⚡ Flash:</b>"
                    )
                    self.signals.render_markdown.emit(full_response)
                    self.signals.update_left.emit("</div>")
                    
            except Exception as e:
                self.signals.update_left.emit(f"<div style='color:red'>Flash Err: {e}</div>")
                
            self.signals.update_status.emit("就绪")
            
        except Exception as e:
            self.signals.error.emit(f"处理错误: {e}")
            
    # ========== 截图功能 ==========
    
    def _handle_screenshot(self):
        """处理截图"""
        if self.is_recording:
            stealth_warning(self, "提示", "请先停止录音")
            return
            
        self.hide()
        time.sleep(0.3)
        
        try:
            img = ImageGrab.grab()
            self.show()
            self.status_label.setText("🖼️ 正在分析截图...")
            threading.Thread(target=self._bg_image_process, args=(img,), daemon=True).start()
        except Exception as e:
            self.show()
            self._show_error(f"截图失败: {e}")
            
    def _bg_image_process(self, img):
        """后台图片处理"""
        try:
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='JPEG')
            img_bytes = img_byte_arr.getvalue()
            
            self.signals.update_status.emit("正在发送图片...")
            
            prompt = self.ai_service.create_text_part(SYSTEM_PROMPT)
            image_part = self.ai_service.create_image_part(img_bytes)
            
            html_msg = "<div style='color:#009688; margin-top:10px;'><b>🖼️ [发送截图]</b></div>"
            self.signals.update_left.emit(html_msg)
                
            # Flash请求 - 只显示最终 Markdown 渲染结果
            try:
                self.signals.update_left.emit(
                    "<div style='background-color:#e6f7ff; padding:8px; border-radius:5px; margin-bottom:5px;'><b>⚡ Flash:</b> <i>正在分析图片...</i></div>"
                )
                
                # 流式积累文本（不实时显示）
                full_response = ""
                for chunk in self.ai_service.send_to_flash_stream([prompt, image_part]):
                    full_response += chunk
                
                # 通过信号在主线程渲染完整的 Markdown
                if full_response:
                    self.signals.update_left.emit(
                        "<div style='background-color:#e6f7ff; padding:8px; border-radius:5px; margin-bottom:5px;'><b>⚡ Flash:</b>"
                    )
                    self.signals.render_markdown.emit(full_response)
                    self.signals.update_left.emit("</div>")
                    
            except Exception as e:
                self.signals.update_left.emit(f"<div style='color:red'>Flash Err: {e}</div>")
                
            self.signals.update_status.emit("就绪")
            
        except Exception as e:
            self.signals.error.emit(f"图片处理错误: {e}")
            
    # ========== UI更新 ==========
    
    def _scroll_to_bottom(self):
        """滚动到底部"""
        self.text_area.verticalScrollBar().setValue(
            self.text_area.verticalScrollBar().maximum()
        )

    def _append_html(self, html):
        """添加HTML到主区域"""
        cursor = self.text_area.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.text_area.setTextCursor(cursor)
        self.text_area.insertHtml(html)
        self.text_area.ensureCursorVisible()

    def _append_stream(self, text):
        formatted_text = text.replace("\n", "<br>")
        cursor = self.text_area.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.text_area.setTextCursor(cursor)
        self.text_area.insertHtml(formatted_text)
        
    def _flush_markdown_buffer(self):
        """将缓冲区的 Markdown 转换为 HTML 并显示"""
        if self._markdown_buffer:
            html = markdown_to_html(self._markdown_buffer)
            self._append_html(html)
            self._markdown_buffer = ""  # 清空缓冲区
            
    def _start_markdown_block(self):
        """开始新的 Markdown 块（清空缓冲区）"""
        self._markdown_buffer = ""
    
    def _render_markdown_content(self, md_text):
        """在主线程中渲染 Markdown 内容（通过信号调用，线程安全）"""
        if md_text:
            html = markdown_to_html(md_text)
            self._append_html(html)
        
    def _update_status_label(self, text):
        """更新状态标签"""
        self.status_label.setText(text)
        
    def _update_volume(self, volume):
        """更新音量显示"""
        self.volume_indicator.update_level(volume)
        
    def _show_error(self, err_msg):
        """显示错误"""
        if "加载失败" in err_msg or "NOT_FOUND" in err_msg:
            stealth_critical(self, "错误", err_msg)
        self._append_html(f"<div style='color:red'>❌ {err_msg}</div>")
            
    # ========== 响应式布局 ==========
    
    def resizeEvent(self, event):
        """窗口大小变化事件"""
        super().resizeEvent(event)
        # 单屏模式下无需特殊调整，由Layout自动处理
                
    # ========== 窗口拖动和调整大小 ==========
    
    def _get_edge(self, pos):
        """
        检测鼠标在窗口边缘的位置
        返回: None, 'left', 'right', 'top', 'bottom', 'topleft', 'topright', 'bottomleft', 'bottomright'
        """
        edge_size = 8  # 边缘检测区域大小
        rect = self.rect()
        x, y = pos.x(), pos.y()
        
        on_left = x <= edge_size
        on_right = x >= rect.width() - edge_size
        on_top = y <= edge_size
        on_bottom = y >= rect.height() - edge_size
        
        if on_top and on_left:
            return 'topleft'
        elif on_top and on_right:
            return 'topright'
        elif on_bottom and on_left:
            return 'bottomleft'
        elif on_bottom and on_right:
            return 'bottomright'
        elif on_left:
            return 'left'
        elif on_right:
            return 'right'
        elif on_top:
            return 'top'
        elif on_bottom:
            return 'bottom'
        return None
        
    def _update_cursor(self, edge):
        """根据边缘位置更新鼠标光标"""
        if edge in ('left', 'right'):
            self.setCursor(Qt.SizeHorCursor)
        elif edge in ('top', 'bottom'):
            self.setCursor(Qt.SizeVerCursor)
        elif edge in ('topleft', 'bottomright'):
            self.setCursor(Qt.SizeFDiagCursor)
        elif edge in ('topright', 'bottomleft'):
            self.setCursor(Qt.SizeBDiagCursor)
        else:
            self.setCursor(Qt.ArrowCursor)
    
    def mousePressEvent(self, event):
        """鼠标按下"""
        if event.button() == Qt.LeftButton:
            self._resize_edge = self._get_edge(event.pos())
            self.old_pos = event.globalPos()
            self._start_geometry = self.geometry()
            
    def mouseMoveEvent(self, event):
        """鼠标移动"""
        if event.buttons() == Qt.NoButton:
            # 没有按键按下时，更新光标
            edge = self._get_edge(event.pos())
            self._update_cursor(edge)
            return
            
        if self.old_pos is None:
            return
            
        delta = event.globalPos() - self.old_pos
        
        if self._resize_edge:
            # 调整大小模式
            geo = self._start_geometry
            new_geo = self.geometry()
            
            min_w, min_h = self.minimumWidth(), self.minimumHeight()
            
            if 'left' in self._resize_edge:
                new_x = geo.x() + delta.x()
                new_w = geo.width() - delta.x()
                if new_w >= min_w:
                    new_geo.setX(new_x)
                    new_geo.setWidth(new_w)
            if 'right' in self._resize_edge:
                new_w = geo.width() + delta.x()
                if new_w >= min_w:
                    new_geo.setWidth(new_w)
            if 'top' in self._resize_edge:
                new_y = geo.y() + delta.y()
                new_h = geo.height() - delta.y()
                if new_h >= min_h:
                    new_geo.setY(new_y)
                    new_geo.setHeight(new_h)
            if 'bottom' in self._resize_edge:
                new_h = geo.height() + delta.y()
                if new_h >= min_h:
                    new_geo.setHeight(new_h)
                    
            self.setGeometry(new_geo)
            self.repaint()
        else:
            # 拖动模式
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPos()
            
    def mouseReleaseEvent(self, event):
        """鼠标释放"""
        self.old_pos = None
        self._resize_edge = None
        self._start_geometry = None

