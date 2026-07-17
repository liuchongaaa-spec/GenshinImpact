# -*- coding: utf-8 -*-
"""
看门狗模块 - 独立进程
用于监听快捷键并管理主程序 (DesktopCompanion.main) 的生命周期。
"""
import sys
import time
import subprocess
import keyboard
import threading
import ctypes
from ctypes import wintypes
from pathlib import Path

if __package__ in {None, ""}:
    project_root = str(Path(__file__).resolve().parents[2])
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

# 尝试读取配置中的热键
try:
    from DesktopCompanion.config import APP_DISPLAY_NAME, HOTKEY_CONFIG
    restart_hotkey = HOTKEY_CONFIG.get("restart", "alt+b")
except Exception:
    APP_DISPLAY_NAME = "Desktop Companion"
    restart_hotkey = "alt+b"



_pythonw = Path(sys.executable).with_name("pythonw.exe")
PYTHON_EXE = str(_pythonw if _pythonw.exists() else Path(sys.executable))
MAIN_PROCESS = None
RESTART_LOCK = threading.Lock()
RESTART_THREAD = None
CHILD_JOB = None


class _IoCounters(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_ulonglong),
        ("WriteOperationCount", ctypes.c_ulonglong),
        ("OtherOperationCount", ctypes.c_ulonglong),
        ("ReadTransferCount", ctypes.c_ulonglong),
        ("WriteTransferCount", ctypes.c_ulonglong),
        ("OtherTransferCount", ctypes.c_ulonglong),
    ]


class _BasicLimitInformation(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _ExtendedLimitInformation(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _BasicLimitInformation),
        ("IoInfo", _IoCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class _ChildProcessJob:
    """Kill watchdog-owned child processes when the watchdog handle closes."""

    JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000

    def __init__(self) -> None:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        kernel32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        kernel32.SetInformationJobObject.restype = wintypes.BOOL
        kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        self.kernel32 = kernel32

        self.handle = kernel32.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())

        limits = _ExtendedLimitInformation()
        limits.BasicLimitInformation.LimitFlags = self.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        configured = kernel32.SetInformationJobObject(
            self.handle,
            self.JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
            ctypes.byref(limits),
            ctypes.sizeof(limits),
        )
        if not configured:
            error = ctypes.get_last_error()
            self.close()
            raise ctypes.WinError(error)

    def assign(self, process: subprocess.Popen) -> None:
        if not self.kernel32.AssignProcessToJobObject(
            self.handle,
            wintypes.HANDLE(process._handle),
        ):
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self) -> None:
        if self.handle:
            self.kernel32.CloseHandle(self.handle)
            self.handle = None


def _get_child_job():
    global CHILD_JOB
    if sys.platform == "win32" and CHILD_JOB is None:
        CHILD_JOB = _ChildProcessJob()
    return CHILD_JOB


def _stop_main_app_locked():
    global MAIN_PROCESS
    process = MAIN_PROCESS
    MAIN_PROCESS = None
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=1)

def start_main_app():
    """启动或重启主程序"""
    global MAIN_PROCESS
    with RESTART_LOCK:
        if MAIN_PROCESS is not None and MAIN_PROCESS.poll() is None:
            print("发现旧的进程，正在强制结束...")
        _stop_main_app_locked()
        time.sleep(0.5)

        print(f"正在启动 {APP_DISPLAY_NAME}...")
        project_dir = str(Path(__file__).resolve().parents[2])
        process = subprocess.Popen(
            [PYTHON_EXE, "-m", "DesktopCompanion.main"],
            cwd=project_dir,
            creationflags=0x08000000,
        )
        try:
            job = _get_child_job()
            if job is not None:
                job.assign(process)
        except Exception:
            process.terminate()
            process.wait(timeout=3)
            raise
        MAIN_PROCESS = process


def stop_main_app():
    with RESTART_LOCK:
        _stop_main_app_locked()


def _run_restart():
    global RESTART_THREAD
    try:
        start_main_app()
    finally:
        RESTART_THREAD = None

def on_restart_hotkey():
    """快捷键触发时的回调"""
    global RESTART_THREAD
    if RESTART_THREAD is not None and RESTART_THREAD.is_alive():
        return
    print(f"检测到重启快捷键 ({restart_hotkey})，开始重启...")
    RESTART_THREAD = threading.Thread(target=_run_restart, daemon=True)
    RESTART_THREAD.start()

def main():
    print("="*40)
    print(f"{APP_DISPLAY_NAME} 看门狗已启动")
    print("="*40)
    
    # 首次启动主程序
    start_main_app()
    
    hotkey_handle = None
    try:
        # 注册全局热键
        hotkey_handle = keyboard.add_hotkey(
            restart_hotkey,
            on_restart_hotkey,
            suppress=True,
        )
        print(f"看门狗正在后台静默监听，重启快捷键: {restart_hotkey}")
        keyboard.wait()
    except Exception as e:
        print(f"看门狗热键注册失败: {e}")
    finally:
        if hotkey_handle is not None:
            try:
                keyboard.remove_hotkey(hotkey_handle)
            except Exception:
                pass
        stop_main_app()
        if CHILD_JOB is not None:
            CHILD_JOB.close()

if __name__ == "__main__":
    main()
