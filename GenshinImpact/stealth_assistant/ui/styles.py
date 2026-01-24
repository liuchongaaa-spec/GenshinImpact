# -*- coding: utf-8 -*-
"""
样式定义模块 - Modern Windows 11 Style
"""

# 全局字体和基础颜色
FONT_FAMILY = "Segoe UI"
PRIMARY_COLOR = "#0078d4"
HOVER_COLOR = "#106ebe"
BG_COLOR = "#ffffff"
BORDER_COLOR = "#e5e5e5"
TEXT_COLOR = "#333333"

# 主窗口样式 (带阴影效果的容器)
MAIN_WINDOW_STYLE = f"""
    QWidget#MainFrame {{
        background-color: rgba(255, 255, 255, 0.98); 
        border: 1px solid #d1d1d1;
        border-radius: 8px;
    }}
    QTextEdit {{
        background-color: #f9f9f9; 
        border: 1px solid transparent;
        border-radius: 6px;
        font-family: "{FONT_FAMILY}"; 
        font-size: 13px; 
        line-height: 1.5;
        padding: 8px;
        selection-background-color: {PRIMARY_COLOR};
        selection-color: white;
    }}
    QTextEdit:focus {{
        background-color: #ffffff;
        border: 1px solid {PRIMARY_COLOR};
    }}
    QLabel {{ 
        color: #444; 
        font-family: "{FONT_FAMILY}";
        font-size: 12px; 
        font-weight: 600; 
    }}
    
    /* 自定义滚动条 */
    QScrollBar:vertical {{
        border: none;
        background: #f0f0f0;
        width: 8px;
        margin: 0px 0px 0px 0px;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical {{
        background: #cdcdcd;
        min-height: 20px;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: #a6a6a6;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
"""

# 下拉框样式
COMBOBOX_STYLE = f"""
    QComboBox {{
        border: 1px solid {BORDER_COLOR}; 
        border-radius: 4px; 
        padding: 4px 10px; 
        background: #fcfcfc; 
        font-family: "{FONT_FAMILY}";
        font-size: 12px; 
        color: #333;
        min-width: 100px;
    }}
    QComboBox:hover {{
        border: 1px solid #bbb;
        background: #fff;
    }}
    QComboBox::drop-down {{ 
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 20px;
        border-left-width: 0px;
        border-top-right-radius: 3px;
        border-bottom-right-radius: 3px;
    }}
    QComboBox::down-arrow {{
        image: none;
        border-left: 5px solid transparent;
        border-right: 5px solid transparent;
        border-top: 5px solid #666;
        margin-right: 6px;
    }}
    QComboBox QAbstractItemView {{
        border: 1px solid {BORDER_COLOR};
        border-radius: 4px;
        background-color: white;
        selection-background-color: #f0f0f0;
        selection-color: #333;
        outline: 0;
    }}
"""

# 关闭按钮样式
CLOSE_BUTTON_STYLE = """
    QPushButton { 
        background-color: transparent; 
        color: #888; 
        font-family: "Segoe UI Symbol";
        font-size: 16px; 
        border: none; 
        border-radius: 12px;
        width: 24px;
        height: 24px;
    }
    QPushButton:hover { 
        background-color: #e81123; 
        color: white; 
    }
"""

# 通用按钮基础样式
_BTN_BASE = f"""
    QPushButton {{ 
        border-radius: 4px; 
        font-family: "{FONT_FAMILY}";
        font-weight: 600;
        font-size: 12px;
        padding: 6px 12px;
        border: none;
    }}
"""

# 主功能按钮样式 (蓝色)
PRIMARY_BUTTON_STYLE = _BTN_BASE + f"""
    QPushButton {{ 
        background-color: {PRIMARY_COLOR}; 
        color: white; 
    }}
    QPushButton:hover {{ 
        background-color: {HOVER_COLOR}; 
    }}
    QPushButton:pressed {{
        background-color: #005a9e;
    }}
"""

# 录音中按钮样式 (红色脉冲感)
RECORDING_BUTTON_STYLE = _BTN_BASE + """
    QPushButton {
        background-color: #e81123; 
        color: white; 
        border: 1px solid #d13438;
    }
    QPushButton:hover {
        background-color: #a8071a;
    }
"""

# 截图按钮样式 (青色)
SCREENSHOT_BUTTON_STYLE = _BTN_BASE + """
    QPushButton { 
        background-color: #0078d4; 
        color: white; 
        background-color: #00897b;
    }
    QPushButton:hover { 
        background-color: #00796b; 
    }
"""

# 滚动/辅助按钮样式 (灰色)
SCROLL_BUTTON_STYLE = _BTN_BASE + f"""
    QPushButton {{ 
        background-color: white; 
        color: #333; 
        border: 1px solid {BORDER_COLOR}; 
    }}
    QPushButton:hover {{ 
        background-color: #f3f3f3; 
        border: 1px solid #ccc;
    }}
"""

# 音量条样式
VOLUME_BAR_STYLE = """
    QProgressBar {
        border: none;
        background-color: #f0f0f0;
        border-radius: 2px;
        text-align: center;
    }
    QProgressBar::chunk {
        background-color: #4CAF50;
        border-radius: 2px;
    }
"""

# 音量条高音量样式
VOLUME_BAR_HIGH_STYLE = """
    QProgressBar {
        border: none;
        background-color: #f0f0f0;
        border-radius: 2px;
    }
    QProgressBar::chunk {
        background-color: #ff5252;
        border-radius: 2px;
    }
"""

# 透明度滑块样式 - 增强可见性
# 透明度滑块样式 - 修复视觉问题
OPACITY_SLIDER_STYLE = f"""
    QSlider::groove:horizontal {{
        border: 1px solid {BORDER_COLOR};
        background: #f0f0f0;
        height: 4px;
        border-radius: 2px;
    }}
    QSlider::sub-page:horizontal {{
        background: {PRIMARY_COLOR};
        border-radius: 2px;
    }}
    QSlider::add-page:horizontal {{
        background: #e0e0e0;
        border-radius: 2px;
    }}
    QSlider::handle:horizontal {{
        background: white;
        border: 1px solid #ccc;
        width: 14px;
        height: 14px;
        margin: -5px 0;
        border-radius: 7px;
    }}
    QSlider::handle:horizontal:hover {{
        border: 1px solid {PRIMARY_COLOR};
    }}
"""
