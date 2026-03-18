# -*- coding: utf-8 -*-
"""
UI模块
"""
def get_stealth_assistant():
    from .main_window import StealthAssistant
    return StealthAssistant

def get_tray_manager():
    from .tray import TrayManager
    return TrayManager

__all__ = ['get_stealth_assistant', 'get_tray_manager']
