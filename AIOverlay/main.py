# -*- coding: utf-8 -*-

import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from AIOverlay.ui.main_window import StealthAssistant
from AIOverlay.config import GEMINI_API_KEY


def main():
    """程序入口"""
    # 启用高DPI支持
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    # 简单的环境检查
    config_ok = False
    try:
        if not GEMINI_API_KEY or "AIza" not in GEMINI_API_KEY:
            print("❌ API Key Error: Please check config.py")
            print("程序将退出...")
        else:
            print("✅ API Key configured")
            config_ok = True
    except Exception as e:
        print(f"❌ Config Error: {e}")
        print("程序将退出...")
    
    # 如果配置检查失败，立即退出
    if not config_ok:
        sys.exit(1)
        
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
