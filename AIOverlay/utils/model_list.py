# -*- coding: utf-8 -*-
"""
工具脚本 - 列出 Google Gemini 可用的所有模型
"""

import os
import sys

# 添加项目根目录的父目录到 sys.path，使得可以作为包解析 AIOverlay
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
parent_dir = os.path.dirname(project_root)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from google import genai
from AIOverlay.config import GEMINI_API_KEY, PROXY_URL


def list_available_models():
    """列出并打印所有可用的 Gemini 模型"""
    if PROXY_URL:
        os.environ['HTTP_PROXY'] = PROXY_URL
        os.environ['HTTPS_PROXY'] = PROXY_URL
        print(f"[Info] 正在使用代理: {PROXY_URL}\n")

    if not GEMINI_API_KEY or GEMINI_API_KEY == "your_api_key_here":
        print("[Error] 错误: 请先在 config.py 中配置有效的 GEMINI_API_KEY")
        return

    try:
        print("[Info] 正在向 Google 服务器请求模型列表，请稍候...")
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        models = list(client.models.list())
        
        if not models:
            print("[Warning] 成功连接，但未找到任何可用模型。")
            return

        print(f"[Success] 成功获取到 {len(models)} 个模型:\n")
        print("=" * 60)
        
        for model in models:
            name = getattr(model, 'name', 'Unknown')
            display_name = getattr(model, 'display_name', '')
            description = getattr(model, 'description', '')
            
            # 高亮最常用的模型
            if "gemini-1.5-pro" in name or "gemini-1.5-flash" in name or "gemini-2.0" in name:
                print(f"[*] 【推荐】模型 ID: {name}")
            else:
                print(f"[-] 模型 ID: {name}")
                
            if display_name:
                print(f"   名称: {display_name}")
            if description:
                print(f"   描述: {description}")
            print("-" * 60)

    except Exception as e:
        print(f"[Error] 获取模型列表失败: {e}")

if __name__ == "__main__":
    list_available_models()
