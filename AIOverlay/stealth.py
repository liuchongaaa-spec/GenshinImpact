# -*- coding: utf-8 -*-
"""
隐蔽性模块 - Windows 11 多层防护实现

提供以下保护层:
- L1: WDA_EXCLUDEFROMCAPTURE 防屏幕捕获
- L2: 系统托盘模式 (任务栏隐藏)
- L3: Alt-Tab隐藏
- L4: 窗口标题伪装
- L5: 透明度控制
- L6: 鼠标穿透 (WS_EX_TRANSPARENT)
"""

import sys
import ctypes
from ctypes import wintypes
import random
from AIOverlay.config import DISGUISE_TITLES


class StealthManager:
    """隐蔽性管理器 - Windows 11优化版"""

    # Windows API 常量
    WDA_NONE = 0x00000000
    WDA_MONITOR = 0x00000001
    WDA_EXCLUDEFROMCAPTURE = 0x00000011  # Windows 10 2004+

    GWL_EXSTYLE = -20
    WS_EX_TOOLWINDOW = 0x00000080      # 从Alt-Tab隐藏
    WS_EX_LAYERED = 0x00080000         # 分层窗口
    WS_EX_TRANSPARENT = 0x00000020     # 鼠标穿透

    LWA_ALPHA = 0x00000002

    def __init__(self):
        """初始化Windows API函数"""
        if sys.platform != "win32":
            self.available = False
            return

        self.available = True
        self.user32 = ctypes.windll.user32

        # SetWindowDisplayAffinity - 防捕获
        self.user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
        self.user32.SetWindowDisplayAffinity.restype = wintypes.BOOL

        # GetWindowLongW / SetWindowLongW - 窗口样式
        self.user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
        self.user32.GetWindowLongW.restype = wintypes.LONG
        self.user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
        self.user32.SetWindowLongW.restype = wintypes.LONG

        # SetLayeredWindowAttributes - 透明度
        self.user32.SetLayeredWindowAttributes.argtypes = [
            wintypes.HWND, wintypes.COLORREF, wintypes.BYTE, wintypes.DWORD
        ]
        self.user32.SetLayeredWindowAttributes.restype = wintypes.BOOL

        # SetWindowTextW - 窗口标题
        self.user32.SetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPCWSTR]
        self.user32.SetWindowTextW.restype = wintypes.BOOL

    def apply_all_protections(self, hwnd: int) -> dict:
        """应用所有隐蔽保护"""
        if not self.available:
            return {"error": "Not available on this platform"}

        results = {}
        results["capture_protection"] = self.set_capture_protection(hwnd, True)
        results["alt_tab_hidden"] = self.hide_from_alt_tab(hwnd)
        results["title_disguised"] = self.set_disguise_title(hwnd)
        results["mouse_passthrough"] = self.set_mouse_passthrough(hwnd)
        return results

    def set_capture_protection(self, hwnd: int, enable: bool = True) -> bool:
        """L1: 防屏幕捕获"""
        if not self.available:
            return False

        flag = self.WDA_EXCLUDEFROMCAPTURE if enable else self.WDA_NONE
        result = self.user32.SetWindowDisplayAffinity(hwnd, flag)

        if result == 0 and enable:
            result = self.user32.SetWindowDisplayAffinity(hwnd, self.WDA_MONITOR)

        return result != 0

    def hide_from_alt_tab(self, hwnd: int) -> bool:
        """L3: 从Alt-Tab切换器隐藏"""
        if not self.available:
            return False

        try:
            style = self.user32.GetWindowLongW(hwnd, self.GWL_EXSTYLE)
            new_style = style | self.WS_EX_TOOLWINDOW
            self.user32.SetWindowLongW(hwnd, self.GWL_EXSTYLE, new_style)
            return True
        except Exception:
            return False

    def set_disguise_title(self, hwnd: int, title: str = None) -> bool:
        """L4: 伪装窗口标题"""
        if not self.available:
            return False

        if title is None:
            title = random.choice(DISGUISE_TITLES)

        try:
            result = self.user32.SetWindowTextW(hwnd, title)
            return result != 0
        except Exception:
            return False

    def set_mouse_passthrough(self, hwnd: int) -> bool:
        """
        L6: 鼠标穿透
        
        设置 WS_EX_TRANSPARENT 使所有鼠标事件穿透到底层窗口。
        窗口将永远不会获得焦点。
        """
        if not self.available:
            return False

        try:
            style = self.user32.GetWindowLongW(hwnd, self.GWL_EXSTYLE)
            new_style = style | self.WS_EX_TRANSPARENT | self.WS_EX_LAYERED
            self.user32.SetWindowLongW(hwnd, self.GWL_EXSTYLE, new_style)
            return True
        except Exception:
            return False

    def set_transparency(self, hwnd: int, alpha: int = 255) -> bool:
        """L5: 设置窗口透明度"""
        if not self.available:
            return False

        try:
            style = self.user32.GetWindowLongW(hwnd, self.GWL_EXSTYLE)
            if not (style & self.WS_EX_LAYERED):
                self.user32.SetWindowLongW(hwnd, self.GWL_EXSTYLE, style | self.WS_EX_LAYERED)

            result = self.user32.SetLayeredWindowAttributes(hwnd, 0, alpha, self.LWA_ALPHA)
            return result != 0
        except Exception:
            return False

    def remove_all_protections(self, hwnd: int) -> bool:
        """移除所有隐蔽保护 (调试用)"""
        if not self.available:
            return False

        self.set_capture_protection(hwnd, False)
        self.set_transparency(hwnd, 255)
        return True


# 全局单例
stealth_manager = StealthManager()
