# -*- coding: utf-8 -*-
"""
配置模块 - 统一在 config.py 中配置，不再读取外部 JSON
"""
import os
from AIOverlay.utils.exceptions import InitializationError

# ================= 外部密钥文件路径 =================
EXTERNAL_CONFIG_DIR = r"D:\tmp"
API_KEY_FILE = os.path.join(EXTERNAL_CONFIG_DIR, "GeminiAPIKey.txt")
SYSTEM_PROMPT_FILE = os.path.join(EXTERNAL_CONFIG_DIR, "SYSTEM_PROMPT.txt")

# ================= 核心配置 =================
# 直接在此处修改配置，重启生效
OVERLAY_CONFIG = {
    "window": {
        "x": 600,           # 窗口左上角 X 坐标
        "y": 100,           # 窗口左上角 Y 坐标
        "width": 600,        # 窗口宽度
        "height": 700,       # 窗口高度
        "opacity": 0.7      # 窗口透明度 (0.0 - 1.0)
    },
    "text": {
        "font_color": "#008000",  # 绿色文字
        "bg_color": "rgba(255, 255, 255, 0.7)", # 半透明白色背景
        "font_size": 10,           # 字体大小
        "line_height": 1.1         # 行间距 (1.0 - 2.0)
    },
    "hotkeys": {
        "toggle_visible": "alt+m",
        "screenshot": "alt+s",
        "move_left": "alt+shift+left",
        "move_right": "alt+shift+right",
        "scroll_up": "alt+k",
        "scroll_down": "alt+l",
        "exit": "alt+shift+q"
    },
    "proxy": "http://127.0.0.1:7897", # 网络代理
    "scroll_step": 80,
    "move_step": 50,
    "model": "gemini-2.5-flash"
}

# ================= 伪装配置 =================
DISGUISE_TITLES = [
    "Windows Update",
    "系统配置",
    "设备管理器",
    "服务",
    "Windows 安全中心",
]


def _load_external_secrets():
    """从外部文件加载 API Key 和 System Prompt"""
    global GEMINI_API_KEY, SYSTEM_PROMPT

    # 读取 API Key
    if not os.path.exists(API_KEY_FILE):
        raise InitializationError("请配置 API Key !")

    with open(API_KEY_FILE, 'r', encoding='utf-8') as f:
        GEMINI_API_KEY = f.read().strip()

    if not GEMINI_API_KEY:
        raise InitializationError("请配置 API Key !")

    # 读取系统提示词
    if not os.path.exists(SYSTEM_PROMPT_FILE):
        raise InitializationError("请配置系统提示词！")

    with open(SYSTEM_PROMPT_FILE, 'r', encoding='utf-8') as f:
        SYSTEM_PROMPT = f.read().strip()

    if not SYSTEM_PROMPT:
        raise InitializationError("请配置系统提示词！")


# ================= 初始化 =================
GEMINI_API_KEY = None
SYSTEM_PROMPT = None

# 加载密钥
_load_external_secrets()

# 便捷访问变量
WINDOW_CONFIG = OVERLAY_CONFIG["window"]
TEXT_CONFIG = OVERLAY_CONFIG["text"]
HOTKEY_CONFIG = OVERLAY_CONFIG["hotkeys"]
PROXY_URL = OVERLAY_CONFIG.get("proxy", "")
SCROLL_STEP = OVERLAY_CONFIG["scroll_step"]
MOVE_STEP = OVERLAY_CONFIG["move_step"]
MODEL_ID = OVERLAY_CONFIG["model"]
