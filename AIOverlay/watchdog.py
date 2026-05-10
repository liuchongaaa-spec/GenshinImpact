# -*- coding: utf-8 -*-
"""
看门狗模块 - 独立进程
用于监听快捷键并管理主程序 (AIOverlay.main) 的生命周期。
"""
import os
import sys
import time
import subprocess
import keyboard
import threading

# 尝试读取配置中的热键
try:
    from AIOverlay.config import HOTKEY_CONFIG
    restart_hotkey = HOTKEY_CONFIG.get("restart", "alt+b")
except Exception:
    restart_hotkey = "alt+b"

PYTHON_EXE = sys.executable
MAIN_PROCESS = None

def start_main_app():
    """启动或重启主程序"""
    global MAIN_PROCESS
    
    # 如果主程序已经在运行，先干掉它
    if MAIN_PROCESS is not None and MAIN_PROCESS.poll() is None:
        print("发现旧的进程，正在强制结束...")
        MAIN_PROCESS.terminate()
        try:
            MAIN_PROCESS.wait(timeout=3)
        except subprocess.TimeoutExpired:
            MAIN_PROCESS.kill()
            
        # 留一点时间让操作系统释放全局热键等资源
        time.sleep(0.5)
        
    print("正在启动 AI 助手主程序...")
    
    # 确保在项目根目录启动
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # 使用无窗口模式启动主程序
    # 0x08000000 是 Windows 的 CREATE_NO_WINDOW 标志
    MAIN_PROCESS = subprocess.Popen(
        [PYTHON_EXE, "-m", "AIOverlay.main"],
        cwd=project_dir,
        creationflags=0x08000000
    )

def on_restart_hotkey():
    """快捷键触发时的回调"""
    print(f"检测到重启快捷键 ({restart_hotkey})，开始重启...")
    threading.Thread(target=start_main_app, daemon=True).start()

def main():
    print("="*40)
    print("AI 助手看门狗已启动")
    print("="*40)
    
    # 首次启动主程序
    start_main_app()
    
    try:
        # 注册全局热键
        keyboard.add_hotkey(restart_hotkey, on_restart_hotkey, suppress=True)
        print(f"看门狗正在后台静默监听，重启快捷键: {restart_hotkey}")
        
        # 阻塞当前线程，保持看门狗存活
        keyboard.wait()
    except Exception as e:
        print(f"看门狗热键注册失败: {e}")
        # 如果注册失败，为了不让看门狗退出导致主程序变成孤儿进程，可以简单睡死
        while True:
            time.sleep(1000)

if __name__ == "__main__":
    main()
