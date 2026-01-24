# -*- coding: utf-8 -*-

import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from stealth_assistant.ui.main_window import StealthAssistant


def main():
    """程序入口"""
    # 启用高DPI支持
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    # 简单的环境检查
    try:
        from stealth_assistant.config import GEMINI_API_KEY
        if not GEMINI_API_KEY or "AIza" not in GEMINI_API_KEY:
            print("❌ API Key Error: Please check config.py")
        else:
            print("✅ API Key configured")
    except Exception:
        print("❌ Config Error")
        
    app = QApplication(sys.argv)
    
    print("⏳ Initializing UI and Services...")
    # 创建并显示主窗口
    window = StealthAssistant()
    window.show()
    
    print("✅ System Ready. Press Alt+Q to toggle.")
    print("="*40 + "\n")
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
