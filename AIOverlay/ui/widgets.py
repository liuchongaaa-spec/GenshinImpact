# -*- coding: utf-8 -*-
"""
自定义组件模块 - 精简版
"""
import sys
import ctypes
from ctypes import wintypes


# ========== 隐蔽式对话框工具函数 ==========

def _apply_stealth_to_dialog(dialog):
    """为对话框窗口应用防捕获保护"""
    if sys.platform != "win32":
        return

    try:
        user32 = ctypes.windll.user32
        user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
        user32.SetWindowDisplayAffinity.restype = wintypes.BOOL

        hwnd = int(dialog.winId())
        user32.SetWindowDisplayAffinity(hwnd, 0x00000011)  # WDA_EXCLUDEFROMCAPTURE
    except Exception:
        pass


def stealth_warning(parent, title, message):
    """显示受保护的警告对话框"""
    from PyQt5.QtWidgets import QMessageBox

    msg_box = QMessageBox(QMessageBox.Warning, title, message, QMessageBox.Ok, parent)
    _apply_stealth_to_dialog(msg_box)
    return msg_box.exec_()


def stealth_critical(parent, title, message):
    """显示受保护的错误对话框"""
    from PyQt5.QtWidgets import QMessageBox

    msg_box = QMessageBox(QMessageBox.Critical, title, message, QMessageBox.Ok, parent)
    _apply_stealth_to_dialog(msg_box)
    return msg_box.exec_()
