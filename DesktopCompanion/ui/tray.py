# -*- coding: utf-8 -*-
"""
系统托盘管理模块
"""
from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QAction, QApplication
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QObject

from DesktopCompanion.config import TRAY_TOOLTIP


class TrayManager(QObject):
    """系统托盘管理器"""

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.tray = None
        self._setup_tray()

    def _setup_tray(self):
        """设置系统托盘"""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            print("系统不支持托盘图标")
            return

        self.tray = QSystemTrayIcon(self.main_window)
        self.tray.setIcon(QIcon())

        self.tray.setToolTip(TRAY_TOOLTIP)

        # 创建右键菜单
        menu = QMenu()

        show_action = QAction("显示/隐藏", self.main_window)
        show_action.triggered.connect(self._toggle_window)
        menu.addAction(show_action)

        menu.addSeparator()

        exit_action = QAction("退出", self.main_window)
        exit_action.triggered.connect(self._exit_app)
        menu.addAction(exit_action)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)

    def _toggle_window(self):
        """切换窗口显示/隐藏"""
        self.main_window.toggle_visibility()

    def _exit_app(self):
        """退出应用"""
        self.main_window.shutdown()
        QApplication.quit()

    def _on_tray_activated(self, reason):
        """托盘图标被点击"""
        if reason == QSystemTrayIcon.Trigger:
            self._toggle_window()

    def show(self):
        """显示托盘图标"""
        if self.tray:
            self.tray.show()

    def hide(self):
        """隐藏托盘图标"""
        if self.tray:
            self.tray.hide()
