# -*- coding: utf-8 -*-
"""
配置模块 - 集中管理所有配置项
"""

# ================= API配置 =================
GEMINI_API_KEY = "*****"

# ================= 快捷键配置 =================
GLOBAL_HOTKEY = "alt+q"  # 隐藏/显示快捷键 (左手单手操作)

# ================= 模型配置 =================
# Flash 模型列表 (快速响应)
FLASH_MODELS = [
    ("Gemini 2.5 Flash", "gemini-2.5-flash"),
    ("Gemini 3 Flash Preview", "gemini-3-flash-preview"),
    ("Gemini Flash Latest", "gemini-flash-latest"),
]

# 自定义系统提示词 (每次启动会话时的背景设定)
SYSTEM_PROMPT = """如果你接收到了图片，那么你需要从图片中准确地找出算法题的题目，然后清晰的说出解题思路并说明时间/空间复杂度，最后使用java代码来实现这个算法题；
                   如果接收到了音频文件，那么你需要作为一名"java开发工程师应聘者"来回答你所听到的内容；
                   你所有的回答都需要使用中文。
                """

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
