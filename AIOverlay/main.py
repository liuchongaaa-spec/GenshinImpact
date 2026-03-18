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
        print("Config loaded OK")
    except InitializationError as e:
        print(f"Init failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unknown error: {e}")
        sys.exit(1)

    # AI 服务连接测试
    try:
        from AIOverlay.ai_service import AIService
        print("Testing AI connection...")
        AIService.test_connection(GEMINI_API_KEY)
        print("AI connection OK")
    except InitializationError as e:
        print(f"{e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unknown error: {e}")
        sys.exit(1)

    app = QApplication(sys.argv)

    window = StealthAssistant()
    window.show()

    print("System Ready. Hotkeys active.")
    print("=" * 40 + "\n")

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
