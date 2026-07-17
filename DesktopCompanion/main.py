# -*- coding: utf-8 -*-

import sys
from pathlib import Path

if __package__ in {None, ""}:
    project_root = str(Path(__file__).resolve().parent.parent)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from DesktopCompanion.controllers.application_controller import create_default_controller
from DesktopCompanion.ui.main_window import OverlayAssistant


def main():
    """程序入口"""
    # 启用高DPI支持
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    # 配置检查
    try:
        from DesktopCompanion.config import (
            APP_DISPLAY_NAME,
            APP_ID,
            InitializationError,
        )
        print("Config loaded OK")
    except InitializationError as e:
        print(f"Init failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unknown error: {e}")
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_ID)
    app.setApplicationDisplayName(APP_DISPLAY_NAME)

    controller = create_default_controller()
    window = OverlayAssistant(controller=controller)
    app.aboutToQuit.connect(window.shutdown)
    window.show_protected()


    print("System Ready. Hotkeys active.")
    print("=" * 40 + "\n")

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
