# -*- coding: utf-8 -*-
"""
配置模块
"""
import os


APP_ID = "desktop_companion"
APP_DISPLAY_NAME = "Desktop Companion"
WINDOW_TITLE = APP_DISPLAY_NAME
TRAY_TOOLTIP = APP_DISPLAY_NAME


class InitializationError(Exception):
    """Raised when required startup configuration is unavailable."""

# ================= 外部密钥文件路径 =================
EXTERNAL_CONFIG_DIR = r"D:\tmp\GenshinImpact\configs"
API_KEY_FILE = os.path.join(EXTERNAL_CONFIG_DIR, "GeminiAPIKey.txt")
DEEPSEEK_API_KEY_FILE = os.path.join(EXTERNAL_CONFIG_DIR, "DeepSeekAPIKey.txt")
SYSTEM_PROMPT_FILE = os.path.join(EXTERNAL_CONFIG_DIR, "SYSTEM_PROMPT——1.txt")

# ================= 核心配置 =================
OVERLAY_CONFIG = {
    "window": {
        "x": 600,           # 窗口左上角 X 坐标
        "y": 100,           # 窗口左上角 Y 坐标
        "width": 600,        # 窗口宽度
        "height": 700        # 窗口高度
    },
    "text": {
        "font_color": "#3690F7",  # 绿色文字
        "font_size": 11,           # 字体大小
        "line_height": 1.1,        # 行间距 (1.0 - 2.0)
        "text_opacity": 1.0,        # 文字透明度 (0.0 - 1.0)
        "padding_lines": 10        # 回答前后的空行数量
    },  
    "hotkeys": {
        "toggle_visible": "caps lock+m",
        "screenshot": "caps lock+d",
        "move_left": "caps lock+h",
        "move_right": "caps lock+j",
        "scroll_up": "caps lock+l",
        "scroll_down": "caps lock+k",
        "exit": "caps lock+shift+q",
        "restart": "caps lock+b",
        "audio_capture": "caps lock+u"
    },
    "audio": {
        "buffer_seconds": 45,      # 滚动缓冲区保留的秒数
        "sample_rate": 16000       # 采样率 (Hz)
    },
    "load_test_file": True,           # 启动时是否加载测试文件
    "test_file_path": os.path.join(os.path.dirname(__file__), "tests", "test.txt"), # 测试文件路径
    "proxy": "http://127.0.0.1:7897", # 网络代理
    "scroll_step": 80,
    "move_step": 50,
    "ai_provider": "gemini",
    "gemini_models": [
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
    ],
    # 单个模型一次请求允许连续等待响应的时间
    "gemini_model_timeout_seconds": 60,
    "max_history_turns": 6,
    "deepseek_model": "deepseek-chat",
    "deepseek_base_url": "https://api.deepseek.com/v1"
}

def _read_required_file(path: str, message: str) -> str:
    if not os.path.exists(path):
        raise InitializationError(message)
    with open(path, "r", encoding="utf-8") as file:
        value = file.read().strip()
    if not value:
        raise InitializationError(message)
    return value


def _read_optional_file(path: str) -> str:
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as file:
        return file.read().strip()


def _load_external_secrets():
    """Load the selected provider key and the shared system prompt."""
    global GEMINI_API_KEY, DEEPSEEK_API_KEY, SYSTEM_PROMPT

    provider = OVERLAY_CONFIG.get("ai_provider", "gemini").lower()
    SYSTEM_PROMPT = _read_required_file(SYSTEM_PROMPT_FILE, "请配置系统提示词！")

    GEMINI_API_KEY = ""
    DEEPSEEK_API_KEY = ""
    if provider == "gemini":
        GEMINI_API_KEY = _read_required_file(API_KEY_FILE, "请配置 Gemini API Key！")
        DEEPSEEK_API_KEY = _read_optional_file(DEEPSEEK_API_KEY_FILE)
    elif provider == "deepseek":
        DEEPSEEK_API_KEY = _read_required_file(DEEPSEEK_API_KEY_FILE, "请配置 DeepSeek API Key！")
        GEMINI_API_KEY = _read_optional_file(API_KEY_FILE)
    else:
        raise InitializationError(f"未知 AI 服务商: {provider}")


# ================= 运行时变量 =================
GEMINI_API_KEY = ""
DEEPSEEK_API_KEY = ""
SYSTEM_PROMPT = ""

# 加载密钥
_load_external_secrets()

# 便捷访问变量
WINDOW_CONFIG = OVERLAY_CONFIG["window"]
TEXT_CONFIG = OVERLAY_CONFIG["text"]
HOTKEY_CONFIG = OVERLAY_CONFIG["hotkeys"]
PROXY_URL = OVERLAY_CONFIG.get("proxy", "")
SCROLL_STEP = OVERLAY_CONFIG["scroll_step"]
MOVE_STEP = OVERLAY_CONFIG["move_step"]
AI_PROVIDER = OVERLAY_CONFIG.get("ai_provider", "gemini")
GEMINI_MODEL_IDS = tuple(OVERLAY_CONFIG.get("gemini_models", ()))
if not GEMINI_MODEL_IDS:
    raise InitializationError("请至少配置一个 Gemini 模型！")
GEMINI_MODEL_TIMEOUT_SECONDS = max(
    1.0, float(OVERLAY_CONFIG.get("gemini_model_timeout_seconds", 60))
)
MAX_HISTORY_TURNS = max(0, int(OVERLAY_CONFIG.get("max_history_turns", 6)))
DEEPSEEK_MODEL_ID = OVERLAY_CONFIG.get("deepseek_model", "deepseek-chat")
DEEPSEEK_BASE_URL = OVERLAY_CONFIG.get("deepseek_base_url", "https://api.deepseek.com/v1")
LOAD_TEST_FILE = OVERLAY_CONFIG.get("load_test_file", False)
TEST_FILE_PATH = OVERLAY_CONFIG.get("test_file_path", "")
AUDIO_CONFIG = OVERLAY_CONFIG.get("audio", {})
