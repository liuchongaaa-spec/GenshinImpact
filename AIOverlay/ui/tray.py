# -*- coding: utf-8 -*-
"""
系统托盘管理模块
"""
from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QAction, QApplication
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QObject
import sys
import os


class TrayManager(QObject):
    """系统托盘管理器"""
    
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.tray = None
        self._setup_tray()
        
    def _setup_tray(self):
        """设置系统托盘"""
        # 检查系统是否支持托盘
        if not QSystemTrayIcon.isSystemTrayAvailable():
            print("系统不支持托盘图标")
            return
            
        self.tray = QSystemTrayIcon(self.main_window)
        
        # 使用系统默认图标或简单图标
        icon = self._get_icon()
        self.tray.setIcon(icon)
        
        # 伪装的提示文本
        self.tray.setToolTip("Windows 服务")
        
        # 创建右键菜单
        menu = QMenu()
        
        show_action = QAction("显示", self.main_window)
        show_action.triggered.connect(self._show_window)
        menu.addAction(show_action)
        
        hide_action = QAction("隐藏", self.main_window)
        hide_action.triggered.connect(self._hide_window)
        menu.addAction(hide_action)
        
        menu.addSeparator()
        
        exit_action = QAction("退出", self.main_window)
        exit_action.triggered.connect(self._exit_app)
        menu.addAction(exit_action)
        
        self.tray.setContextMenu(menu)
        
        # 点击托盘图标切换显示/隐藏
        self.tray.activated.connect(self._on_tray_activated)
        
    def _get_icon(self) -> QIcon:
        """获取托盘图标"""
        # 尝试使用系统图标
        if sys.platform == "win32":
            # 使用Windows系统图标
            import ctypes
            try:
                shell32 = ctypes.windll.shell32
                # 这里可以使用系统图标,但为简化起见使用空图标
                pass
            except Exception:
                pass
                
        # 返回默认空图标(托盘会显示一个小点)
        return QIcon()
        
    def _show_window(self):
        """显示主窗口"""
        self.main_window.showNormal()
        self.main_window.activateWindow()
        
    def _hide_window(self):
        """隐藏主窗口"""
        self.main_window.hide()
        
    def _exit_app(self):
        """退出应用"""
        self.hide()
        QApplication.quit()
        
    def _on_tray_activated(self, reason):
        """托盘图标被点击"""
        if reason == QSystemTrayIcon.Trigger:  # 单击
            if self.main_window.isVisible():
                self._hide_window()
            else:
                self._show_window()
                
    def show(self):
        """显示托盘图标"""
        if self.tray:
            self.tray.show()
            
    def hide(self):
        """隐藏托盘图标"""
        if self.tray:
            self.tray.hide()
            
    def show_message(self, title: str, message: str, icon=QSystemTrayIcon.Information, duration: int = 3000):
        """
        显示托盘消息
        
        Args:
            title: 标题
            message: 消息内容
            icon: 图标类型
            duration: 显示时长(毫秒)
        """
        if self.tray:
            self.tray.showMessage(title, message, icon, duration)
