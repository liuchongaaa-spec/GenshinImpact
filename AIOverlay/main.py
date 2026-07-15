# -*- coding: utf-8 -*-

import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from AIOverlay.ui.main_window import StealthAssistant
from AIOverlay.controllers.application_controller import create_default_controller
from AIOverlay.utils.diagnostics import get_logger, health_registry


def main():
    """程序入口"""
    # 启用高DPI支持
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    # 配置检查
    try:
        from AIOverlay.config import GEMINI_API_KEY, SYSTEM_PROMPT, InitializationError
        print("Config loaded OK")
    except InitializationError as e:
        print(f"Init failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unknown error: {e}")
        sys.exit(1)

    logger = get_logger("main")
    health_registry.update("config", "healthy", "External configuration loaded")
    logger.info(
        "Application startup",
        extra={"component": "application", "event": "startup", "task_id": None},
    )
    # AI 服务连接测试
    try:
        from AIOverlay.ai_service import AIService
        print("Testing AI connection...")
        health_registry.update("ai", "starting", "Testing Gemini connection")
        AIService.test_connection(GEMINI_API_KEY)
        health_registry.update("ai", "healthy", "Gemini connection test passed")
        print("AI connection OK")
    except InitializationError as e:
        health_registry.update("ai", "failed", str(e))
        logger.exception(
            "AI initialization failed",
            extra={"component": "ai", "event": "connection_failed", "task_id": None},
        )
        print(f"{e}")
        sys.exit(1)
    except Exception as e:
        health_registry.update("ai", "failed", str(e))
        logger.exception(
            "Unexpected AI initialization failure",
            extra={"component": "ai", "event": "connection_failed", "task_id": None},
        )
        print(f"Unknown error: {e}")
        sys.exit(1)

    app = QApplication(sys.argv)

    controller = create_default_controller()
    window = StealthAssistant(controller=controller)
    window.show()

    logger.info(
        "Application ready; health=%s",
        health_registry.snapshot(),
        extra={"component": "application", "event": "ready", "task_id": None},
    )

    print("System Ready. Hotkeys active.")
    print("=" * 40 + "\n")

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
