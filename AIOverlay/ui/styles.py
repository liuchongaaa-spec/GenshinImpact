# -*- coding: utf-8 -*-
"""
样式定义模块 - 极简隐蔽风格
"""

FONT_FAMILY = "Consolas"


def build_main_style(font_color: str = "#333333", bg_color: str = "rgba(255, 255, 255, 0.7)", font_size: int = 13) -> str:
    """
    构建主窗口样式
    
    Args:
        font_color: 文字颜色 (hex)
        bg_color: 背景颜色 (rgba)
        font_size: 字体大小 (px)
    """
    return f"""
        QWidget#MainFrame {{
            background-color: transparent;
            border: none;
        }}
        QTextEdit {{
            background-color: {bg_color};
            color: {font_color};
            border: none;
            border-radius: 4px;
            font-family: "{FONT_FAMILY}", "Cascadia Code", "Consolas", monospace;
            font-size: {font_size}px;
            line-height: 1.5;
            padding: 10px;
            selection-background-color: {font_color};
            selection-color: black;
        }}

        /* 自定义滚动条 - 极细低调 */
        QScrollBar:vertical {{
            border: none;
            background: transparent;
            width: 4px;
            margin: 0px;
        }}
        QScrollBar::handle:vertical {{
            background: rgba(255, 255, 255, 0.2);
            min-height: 20px;
            border-radius: 2px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: rgba(255, 255, 255, 0.4);
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
    """
