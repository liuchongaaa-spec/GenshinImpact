# -*- coding: utf-8 -*-
"""
Qt信号定义模块
"""
from PyQt5.QtCore import pyqtSignal, QObject


class WorkerSignals(QObject):
    """工作线程信号集"""
    
    # 更新左侧面板(Flash)
    update_left = pyqtSignal(str)
    
    # 更新右侧面板(Pro)
    update_right = pyqtSignal(str)
    
    # 流式更新左侧
    stream_left = pyqtSignal(str)
    
    # 流式更新右侧
    stream_right = pyqtSignal(str)
    
    # 更新状态栏
    update_status = pyqtSignal(str)
    
    # 错误信号
    error = pyqtSignal(str)
    
    # 切换可见性
    toggle_visible = pyqtSignal()
    
    # 音量更新信号
    volume_update = pyqtSignal(float)
