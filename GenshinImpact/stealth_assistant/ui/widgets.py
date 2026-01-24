# -*- coding: utf-8 -*-
"""
自定义组件模块
"""
import sys
import ctypes
from ctypes import wintypes

from PyQt5.QtWidgets import (
    QProgressBar, QWidget, QHBoxLayout, QVBoxLayout, QLabel, 
    QPushButton, QListWidget, QListWidgetItem, QFrame, QApplication
)
from PyQt5.QtCore import Qt, pyqtSignal, QPoint, QEvent
from .styles import VOLUME_BAR_STYLE, VOLUME_BAR_HIGH_STYLE


class InlineSelector(QWidget):
    
    # 选项改变信号
    currentIndexChanged = pyqtSignal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []  # [(display_name, data), ...]
        self._current_index = -1
        self._expanded = False
        self._setup_ui()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 当前选项按钮
        self.btn_current = QPushButton("请选择...")
        self.btn_current.setFixedHeight(24)
        # self.btn_current.setCursor(Qt.PointingHandCursor)
        self.btn_current.setStyleSheet("""
            QPushButton {
                background: white;
                border: 1px solid #ccc;
                border-radius: 3px;
                padding: 2px 8px;
                text-align: left;
                font-size: 11px;
            }
            QPushButton:hover {
                border-color: #999;
            }
        """)
        self.btn_current.clicked.connect(self._toggle_list)
        layout.addWidget(self.btn_current)
        
        # 下拉列表 (初始隐藏)
        self.list_widget = QListWidget()
        self.list_widget.setMaximumHeight(120)
        self.list_widget.setStyleSheet("""
            QListWidget {
                background: white;
                border: 1px solid #ccc;
                border-top: none;
                border-radius: 0 0 3px 3px;
                font-size: 11px;
            }
            QListWidget::item {
                padding: 5px 8px;
            }
            QListWidget::item:hover {
                background: #e6f7ff;
            }
            QListWidget::item:selected {
                background: #1890ff;
                color: white;
            }
        """)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        self.list_widget.hide()
        # 注意：这里不将 list_widget 添加到 layout，以免占据空间
        # layout.addWidget(self.list_widget)
        
    def _toggle_list(self):
        """切换列表显示状态"""
        self._expanded = not self._expanded
        if self._expanded:
            # 挂载到顶层窗口 (Overlay)
            main_window = self.window()
            self.list_widget.setParent(main_window)
            
            # 计算绝对位置
            # mapToGlobal: 按钮左下角 -> 屏幕坐标
            # mapFromGlobal: 屏幕坐标 -> 主窗口内部坐标
            global_pos = self.btn_current.mapToGlobal(QPoint(0, self.btn_current.height()))
            local_pos = main_window.mapFromGlobal(global_pos)
            
            self.list_widget.move(local_pos)
            self.list_widget.setFixedWidth(self.btn_current.width())
            self.list_widget.show()
            self.list_widget.raise_()
            
            # 更新按钮样式
            self.btn_current.setStyleSheet("""
                QPushButton {
                    background: white;
                    border: 1px solid #1890ff;
                    border-bottom: none;
                    border-radius: 3px 3px 0 0;
                    padding: 2px 8px;
                    text-align: left;
                    font-size: 11px;
                }
            """)
            
            # 安装事件过滤器以监测外部点击
            QApplication.instance().installEventFilter(self)
            
        else:
            self.list_widget.hide()
            self.btn_current.setStyleSheet("""
                QPushButton {
                    background: white;
                    border: 1px solid #ccc;
                    border-radius: 3px;
                    padding: 2px 8px;
                    text-align: left;
                    font-size: 11px;
                }
                QPushButton:hover {
                    border-color: #999;
                }
            """)
            
            # 移除事件过滤器
            QApplication.instance().removeEventFilter(self)
            
    def eventFilter(self, obj, event):
        """事件过滤器：监测点击事件以自动关闭列表"""
        if self._expanded and event.type() == QEvent.MouseButtonPress:
            # 检查点击位置是否在组件外部
            pos = event.globalPos()
            
            # 按钮区域
            btn_global = self.btn_current.mapToGlobal(QPoint(0, 0))
            btn_rect = self.btn_current.rect()
            btn_rect.moveTo(btn_global)
            
            # 列表区域
            list_global = self.list_widget.mapToGlobal(QPoint(0, 0))
            list_rect = self.list_widget.rect()
            list_rect.moveTo(list_global)
            
            if not btn_rect.contains(pos) and not list_rect.contains(pos):
                self._toggle_list() # 关闭列表
                # 不吞噬事件，允许点击传递给其他组件
                
        return super().eventFilter(obj, event)
            
    def _on_item_clicked(self, item):
        """选项被点击"""
        index = self.list_widget.row(item)
        if index != self._current_index:
            self._current_index = index
            self.btn_current.setText(self._items[index][0])
            self.currentIndexChanged.emit(index)
        
        # 收起列表
        self._toggle_list()
        
    def addItem(self, text, data=None):
        """添加选项"""
        self._items.append((text, data))
        self.list_widget.addItem(text)
        
        # 如果是第一个选项，自动选中
        if len(self._items) == 1:
            self._current_index = 0
            self.btn_current.setText(text)
            self.list_widget.setCurrentRow(0)
            
    def clear(self):
        """清空所有选项"""
        self._items = []
        self._current_index = -1
        self.list_widget.clear()
        self.btn_current.setText("请选择...")
        
    def count(self) -> int:
        """获取选项数量"""
        return len(self._items)
        
    def currentIndex(self) -> int:
        """获取当前选中索引"""
        return self._current_index
        
    def currentData(self):
        """获取当前选中项的数据"""
        if 0 <= self._current_index < len(self._items):
            return self._items[self._current_index][1]
        return None
        
    def currentText(self) -> str:
        """获取当前选中项的文本"""
        if 0 <= self._current_index < len(self._items):
            return self._items[self._current_index][0]
        return ""
        
    def setCurrentIndex(self, index: int):
        """设置当前选中索引"""
        if 0 <= index < len(self._items):
            self._current_index = index
            self.btn_current.setText(self._items[index][0])
            self.list_widget.setCurrentRow(index)
            
    def itemData(self, index: int):
        """获取指定索引的数据"""
        if 0 <= index < len(self._items):
            return self._items[index][1]
        return None
        
    def blockSignals(self, block: bool):
        """阻止/允许信号发射"""
        super().blockSignals(block)
        
    def setMinimumWidth(self, width: int):
        """设置最小宽度"""
        super().setMinimumWidth(width)
        self.btn_current.setMinimumWidth(width)
        
    def setFixedHeight(self, height: int):
        """设置按钮高度"""
        self.btn_current.setFixedHeight(height)


class VolumeIndicator(QProgressBar):
    """实时音量指示器"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRange(0, 100)
        self.setTextVisible(False)
        self.setFixedHeight(8)
        self.setStyleSheet(VOLUME_BAR_STYLE)
        self._high_volume = False
        
    def update_level(self, volume: float):
        """
        更新音量显示
        
        Args:
            volume: 音量值 (0.0-1.0)
        """
        level = int(volume * 100)
        self.setValue(min(100, level))
        
        # 高音量时变色
        if level > 80 and not self._high_volume:
            self._high_volume = True
            self.setStyleSheet(VOLUME_BAR_HIGH_STYLE)
        elif level <= 80 and self._high_volume:
            self._high_volume = False
            self.setStyleSheet(VOLUME_BAR_STYLE)
            
    def reset(self):
        """重置音量显示"""
        self.setValue(0)
        self._high_volume = False
        self.setStyleSheet(VOLUME_BAR_STYLE)


class OpacityControl(QWidget):
    """透明度控制组件 (使用加减按钮)"""
    
    def __init__(self, parent=None, on_change=None):
        super().__init__(parent)
        self.on_change = on_change
        self._opacity = 100  # 当前透明度百分比 (40-100)
        self._setup_ui()
        
    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        
        # 减号按钮
        self.btn_minus = QPushButton("−")
        self.btn_minus.setFixedSize(22, 22)
        # self.btn_minus.setCursor(Qt.PointingHandCursor)
        self.btn_minus.setStyleSheet("""
            QPushButton { 
                background: #f0f0f0; 
                border: 1px solid #ccc; 
                border-radius: 3px; 
                font-size: 14px; 
                font-weight: bold;
            }
            QPushButton:hover { background: #e0e0e0; }
        """)
        self.btn_minus.clicked.connect(self._decrease)
        layout.addWidget(self.btn_minus)
        
        # 百分比显示
        self.value_label = QLabel("100%")
        self.value_label.setAlignment(Qt.AlignCenter)
        self.value_label.setFixedWidth(40)
        self.value_label.setStyleSheet("font-size: 11px; color: #555;")
        layout.addWidget(self.value_label)
        
        # 加号按钮
        self.btn_plus = QPushButton("+")
        self.btn_plus.setFixedSize(22, 22)
        # self.btn_plus.setCursor(Qt.PointingHandCursor)
        self.btn_plus.setStyleSheet("""
            QPushButton { 
                background: #f0f0f0; 
                border: 1px solid #ccc; 
                border-radius: 3px; 
                font-size: 14px; 
                font-weight: bold;
            }
            QPushButton:hover { background: #e0e0e0; }
        """)
        self.btn_plus.clicked.connect(self._increase)
        layout.addWidget(self.btn_plus)
        
    def _decrease(self):
        """降低透明度 (每次10%, 最低40%)"""
        if self._opacity > 40:
            self._opacity -= 10
            self._update_display()
            
    def _increase(self):
        """提高透明度 (每次10%, 最高100%)"""
        if self._opacity < 100:
            self._opacity += 10
            self._update_display()
            
    def _update_display(self):
        """更新显示并触发回调"""
        self.value_label.setText(f"{self._opacity}%")
        if self.on_change:
            # 返回 0.0-1.0 的浮点值
            self.on_change(self._opacity / 100.0)
            
    def get_value(self) -> float:
        """获取当前透明度值 (0.0-1.0)"""
        return self._opacity / 100.0


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
