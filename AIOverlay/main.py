# -*- coding: utf-8 -*-

import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from AIOverlay.ui.main_window import StealthAssistant


def main():
    """程序入口"""
    # 启用高DPI支持
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    # 配置检查
    try:
        from AIOverlay.config import GEMINI_API_KEY, SYSTEM_PROMPT
        from AIOverlay.utils.exceptions import InitializationError
        print("✅ 配置加载成功")
    except InitializationError as e:
        print(f"❌ 初始化失败: {e}")
        print("程序将退出...")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 未知错误: {e}")
        print("程序将退出...")
        sys.exit(1)
    
    # AI 服务连接测试
    try:
        from AIOverlay.ai_service import AIService
        print("⏳ 测试 AI 服务连接...")
        AIService.test_connection(GEMINI_API_KEY)
        print("✅ AI 服务连接成功")
    except InitializationError as e:
        print(f"❌ {e}")
        print("程序将退出...")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 未知错误: {e}")
        print("程序将退出...")
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
