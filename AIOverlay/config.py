# -*- coding: utf-8 -*-
"""
配置模块 - 集中管理所有配置项
"""
import os
from AIOverlay.utils.exceptions import InitializationError

# ================= 外部配置文件路径 =================
EXTERNAL_CONFIG_DIR = r"D:\tmp"
API_KEY_FILE = os.path.join(EXTERNAL_CONFIG_DIR, "GeminiAPIKey.txt")
SYSTEM_PROMPT_FILE = os.path.join(EXTERNAL_CONFIG_DIR, "SYSTEM_PROMPT.txt")

def load_external_config():
    """从外部文件加载配置"""
    global GEMINI_API_KEY, SYSTEM_PROMPT
    
    # 读取 API Key
    if not os.path.exists(API_KEY_FILE):
        raise InitializationError(f"请配置 API Key !")
    
    with open(API_KEY_FILE, 'r', encoding='utf-8') as f:
        GEMINI_API_KEY = f.read().strip()
    
    if not GEMINI_API_KEY:
        raise InitializationError("请配置 API Key !")
    
    # 读取系统提示词
    if not os.path.exists(SYSTEM_PROMPT_FILE):
        raise InitializationError(f"请配置系统提示词！")
    
    with open(SYSTEM_PROMPT_FILE, 'r', encoding='utf-8') as f:
        SYSTEM_PROMPT = f.read().strip()
    
    if not SYSTEM_PROMPT:
        raise InitializationError("请配置系统提示词！")

# 初始化配置变量
GEMINI_API_KEY = None
SYSTEM_PROMPT = None

# 模块加载时自动读取配置
load_external_config()

# ================= 快捷键配置 =================
GLOBAL_HOTKEY = "alt+q"  # 隐藏/显示快捷键 (左手单手操作)

# ================= 模型配置 =================
# Flash 模型列表 (快速响应)
FLASH_MODELS = [
    ("Gemini Flash Latest", "gemini-flash-latest"),
    ("Gemini 3 Flash Preview", "gemini-3-flash-preview"),
    ("Gemini 2.5 Flash", "gemini-2.5-flash"),
]

# ================= 模式常量 =================
# 仅保留 Flash 模式，移除其他模式定义

# ================= 伪装配置 =================
DISGUISE_TITLES = [
    "Windows Update",
    "系统配置",
    "设备管理器",
    "服务",
    "Windows 安全中心",
]

# ================= 音频配置 =================
AUDIO_SAMPLE_RATE = 44100
AUDIO_CHUNK_FRAMES = AUDIO_SAMPLE_RATE // 5  # 每0.2秒一个chunk

# ================= UI配置 =================
WINDOW_DEFAULT_WIDTH = 950
WINDOW_DEFAULT_HEIGHT = 750
WINDOW_MIN_WIDTH = 400
WINDOW_MIN_HEIGHT = 300
