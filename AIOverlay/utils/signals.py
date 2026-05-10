# -*- coding: utf-8 -*-
"""
Qt信号定义模块
"""
from PyQt5.QtCore import pyqtSignal, QObject


class WorkerSignals(QObject):
    """工作线程信号集"""

    # 更新输出区域 (HTML)
    update_output = pyqtSignal(str)

    # 流式更新 (原始文本)
    stream_output = pyqtSignal(str)

    # 更新状态栏
    update_status = pyqtSignal(str)

    # 错误信号
    error = pyqtSignal(str)

    # 切换可见性
    toggle_visible = pyqtSignal()

    # 截屏请求
    screenshot_requested = pyqtSignal()

    # 窗口移动 (正数=右移, 负数=左移)
    move_window = pyqtSignal(int)

    # 内容滚动 (正数=下滚, 负数=上滚)
    scroll_content = pyqtSignal(int)

    # 退出程序
    exit_app = pyqtSignal()

    # 音频捕获请求
    audio_capture_requested = pyqtSignal()
