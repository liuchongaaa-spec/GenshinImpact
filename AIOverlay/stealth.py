"""Verified Win32 window protection operations."""

from __future__ import annotations

import ctypes
import os
import random
import sys
from ctypes import wintypes
from dataclasses import asdict, dataclass
from typing import Any

from AIOverlay.config import DISGUISE_TITLES
from AIOverlay.utils.diagnostics import get_logger, health_registry


logger = get_logger("window_protection")


@dataclass(frozen=True)
class Win32CallResult:
    success: bool
    value: Any = None
    error: int = 0


class Win32WindowApi:
    """Small testable adapter around the Win32 calls used by the overlay."""

    GWL_EXSTYLE = -20
    GW_OWNER = 4
    SWP_NOSIZE = 0x0001
    SWP_NOMOVE = 0x0002
    SWP_NOZORDER = 0x0004
    SWP_NOACTIVATE = 0x0010
    SWP_FRAMECHANGED = 0x0020

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise OSError("Win32 window APIs are unavailable")
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)
        self._configure_signatures()

    def _configure_signatures(self) -> None:
        pointer_int = ctypes.c_ssize_t
        self.user32.IsWindow.argtypes = [wintypes.HWND]
        self.user32.IsWindow.restype = wintypes.BOOL
        self.user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
        self.user32.GetWindow.restype = wintypes.HWND
        self.user32.GetWindowThreadProcessId.argtypes = [
            wintypes.HWND,
            ctypes.POINTER(wintypes.DWORD),
        ]
        self.user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        self.user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
        self.user32.SetWindowDisplayAffinity.restype = wintypes.BOOL
        self.user32.GetWindowDisplayAffinity.argtypes = [
            wintypes.HWND,
            ctypes.POINTER(wintypes.DWORD),
        ]
        self.user32.GetWindowDisplayAffinity.restype = wintypes.BOOL
        self.user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
        self.user32.GetWindowLongPtrW.restype = pointer_int
        self.user32.SetWindowLongPtrW.argtypes = [
            wintypes.HWND,
            ctypes.c_int,
            pointer_int,
        ]
        self.user32.SetWindowLongPtrW.restype = pointer_int
        self.user32.SetWindowPos.argtypes = [
            wintypes.HWND,
            wintypes.HWND,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.UINT,
        ]
        self.user32.SetWindowPos.restype = wintypes.BOOL
        self.user32.SetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPCWSTR]
        self.user32.SetWindowTextW.restype = wintypes.BOOL
        self.user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        self.user32.GetWindowTextLengthW.restype = ctypes.c_int
        self.user32.GetWindowTextW.argtypes = [
            wintypes.HWND,
            wintypes.LPWSTR,
            ctypes.c_int,
        ]
        self.user32.GetWindowTextW.restype = ctypes.c_int
        self.user32.SetLayeredWindowAttributes.argtypes = [
            wintypes.HWND,
            wintypes.COLORREF,
            wintypes.BYTE,
            wintypes.DWORD,
        ]
        self.user32.SetLayeredWindowAttributes.restype = wintypes.BOOL
        self.dwmapi.DwmIsCompositionEnabled.argtypes = [ctypes.POINTER(wintypes.BOOL)]
        self.dwmapi.DwmIsCompositionEnabled.restype = ctypes.c_long

    @staticmethod
    def _bool_result(value: int) -> Win32CallResult:
        return Win32CallResult(
            bool(value),
            bool(value),
            ctypes.get_last_error() if not value else 0,
        )

    def describe_window(self, hwnd: int) -> dict[str, Any]:
        valid = bool(self.user32.IsWindow(hwnd))
        owner = int(self.user32.GetWindow(hwnd, self.GW_OWNER) or 0) if valid else 0
        process_id = wintypes.DWORD()
        if valid:
            self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
        composition = wintypes.BOOL()
        hr = int(self.dwmapi.DwmIsCompositionEnabled(ctypes.byref(composition)))
        return {
            "valid": valid,
            "top_level": valid and owner == 0,
            "owner_process_id": int(process_id.value),
            "current_process": int(process_id.value) == os.getpid(),
            "windows_build": sys.getwindowsversion().build,
            "dwm_enabled": hr >= 0 and bool(composition.value),
            "dwm_hresult": hr,
        }

    def set_display_affinity(self, hwnd: int, affinity: int) -> Win32CallResult:
        ctypes.set_last_error(0)
        return self._bool_result(self.user32.SetWindowDisplayAffinity(hwnd, affinity))

    def get_display_affinity(self, hwnd: int) -> Win32CallResult:
        affinity = wintypes.DWORD()
        ctypes.set_last_error(0)
        result = self.user32.GetWindowDisplayAffinity(hwnd, ctypes.byref(affinity))
        return Win32CallResult(
            bool(result),
            int(affinity.value) if result else None,
            ctypes.get_last_error() if not result else 0,
        )

    def get_exstyle(self, hwnd: int) -> Win32CallResult:
        ctypes.set_last_error(0)
        value = int(self.user32.GetWindowLongPtrW(hwnd, self.GWL_EXSTYLE))
        error = ctypes.get_last_error()
        return Win32CallResult(value != 0 or error == 0, value, error)

    def set_exstyle(self, hwnd: int, style: int) -> Win32CallResult:
        ctypes.set_last_error(0)
        previous = int(self.user32.SetWindowLongPtrW(hwnd, self.GWL_EXSTYLE, style))
        error = ctypes.get_last_error()
        success = previous != 0 or error == 0
        if success:
            flags = (
                self.SWP_NOSIZE
                | self.SWP_NOMOVE
                | self.SWP_NOZORDER
                | self.SWP_NOACTIVATE
                | self.SWP_FRAMECHANGED
            )
            ctypes.set_last_error(0)
            refreshed = self.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, flags)
            if not refreshed:
                return Win32CallResult(False, previous, ctypes.get_last_error())
        return Win32CallResult(success, previous, error)

    def set_title(self, hwnd: int, title: str) -> Win32CallResult:
        ctypes.set_last_error(0)
        return self._bool_result(self.user32.SetWindowTextW(hwnd, title))

    def get_title(self, hwnd: int) -> Win32CallResult:
        ctypes.set_last_error(0)
        length = self.user32.GetWindowTextLengthW(hwnd)
        length_error = ctypes.get_last_error()
        if length == 0 and length_error:
            return Win32CallResult(False, None, length_error)
        buffer = ctypes.create_unicode_buffer(length + 1)
        ctypes.set_last_error(0)
        copied = self.user32.GetWindowTextW(hwnd, buffer, len(buffer))
        error = ctypes.get_last_error()
        return Win32CallResult(
            copied != 0 or (length == 0 and error == 0),
            buffer.value,
            error,
        )

    def set_layered_alpha(self, hwnd: int, alpha: int, flag: int) -> Win32CallResult:
        ctypes.set_last_error(0)
        return self._bool_result(
            self.user32.SetLayeredWindowAttributes(hwnd, 0, alpha, flag)
        )


class StealthManager:
    """Apply and verify the existing overlay window settings."""

    WDA_NONE = 0x00000000
    WDA_MONITOR = 0x00000001
    WDA_EXCLUDEFROMCAPTURE = 0x00000011
    WS_EX_TOOLWINDOW = 0x00000080
    WS_EX_LAYERED = 0x00080000
    WS_EX_TRANSPARENT = 0x00000020
    LWA_ALPHA = 0x00000002

    def __init__(self, api: Win32WindowApi | None = None) -> None:
        self.api = api
        self.available = api is not None or sys.platform == "win32"
        if self.api is None and self.available:
            try:
                self.api = Win32WindowApi()
            except OSError:
                self.available = False
        self.last_report: dict[str, Any] = {}
        self._titles: dict[int, str] = {}

    @staticmethod
    def _result_data(result: Win32CallResult) -> dict[str, Any]:
        return asdict(result)

    def apply_all_protections(self, hwnd: int) -> dict[str, bool]:
        if not self.available or self.api is None:
            self.last_report = {"available": False}
            return {"error": "Not available on this platform"}

        window = {"hwnd": hwnd, **self.api.describe_window(hwnd)}
        results = {
            "capture_protection": self.set_capture_protection(hwnd, True),
            "alt_tab_hidden": self.hide_from_alt_tab(hwnd),
            "title_disguised": self.set_disguise_title(hwnd),
            "mouse_passthrough": self.set_mouse_passthrough(hwnd),
        }
        self.last_report = {
            **self.last_report,
            "available": True,
            "window": window,
            "results": results,
        }
        state = "healthy" if all(results.values()) else "degraded"
        health_registry.update(
            "window_protection",
            state,
            "Window protection verified"
            if state == "healthy"
            else "Window protection degraded",
            self.last_report,
        )
        logger.info(
            "Window protection result: %s; diagnostics=%s",
            results,
            self.last_report,
            extra={"component": "window_protection", "event": "applied", "task_id": None},
        )
        return results

    def set_capture_protection(self, hwnd: int, enable: bool = True) -> bool:
        if not self.available or self.api is None:
            return False
        requested = self.WDA_EXCLUDEFROMCAPTURE if enable else self.WDA_NONE
        exact_set = self.api.set_display_affinity(hwnd, requested)
        fallback_set = None
        if enable and not exact_set.success:
            fallback_set = self.api.set_display_affinity(hwnd, self.WDA_MONITOR)
        query = self.api.get_display_affinity(hwnd)
        exact = query.success and query.value == requested
        self.last_report["capture"] = {
            "requested": requested,
            "set": self._result_data(exact_set),
            "fallback": self._result_data(fallback_set) if fallback_set else None,
            "query": self._result_data(query),
            "exact": exact,
        }
        return exact

    def _add_styles(self, hwnd: int, required: int, report_key: str) -> bool:
        if not self.available or self.api is None:
            return False
        before = self.api.get_exstyle(hwnd)
        changed = None
        if before.success and before.value & required != required:
            changed = self.api.set_exstyle(hwnd, before.value | required)
        after = self.api.get_exstyle(hwnd)
        verified = after.success and after.value & required == required
        self.last_report[report_key] = {
            "required": required,
            "before": self._result_data(before),
            "set": self._result_data(changed) if changed else None,
            "after": self._result_data(after),
            "verified": verified,
        }
        return verified

    def hide_from_alt_tab(self, hwnd: int) -> bool:
        return self._add_styles(hwnd, self.WS_EX_TOOLWINDOW, "alt_tab")

    def set_mouse_passthrough(self, hwnd: int) -> bool:
        return self._add_styles(
            hwnd,
            self.WS_EX_TRANSPARENT | self.WS_EX_LAYERED,
            "mouse_passthrough",
        )

    def set_disguise_title(self, hwnd: int, title: str | None = None) -> bool:
        if not self.available or self.api is None:
            return False
        expected = title or self._titles.get(hwnd) or random.choice(DISGUISE_TITLES)
        self._titles[hwnd] = expected
        set_result = self.api.set_title(hwnd, expected)
        query = self.api.get_title(hwnd)
        verified = set_result.success and query.success and query.value == expected
        self.last_report["title"] = {
            "set": self._result_data(set_result),
            "query": self._result_data(query),
            "verified": verified,
        }
        return verified

    def set_transparency(self, hwnd: int, alpha: int = 255) -> bool:
        if not self._add_styles(hwnd, self.WS_EX_LAYERED, "transparency_style"):
            return False
        assert self.api is not None
        result = self.api.set_layered_alpha(hwnd, alpha, self.LWA_ALPHA)
        self.last_report["transparency"] = self._result_data(result)
        return result.success

    def verify_or_reapply(self, hwnd: int) -> dict[str, bool]:
        """Low-frequency self-check used after show and before a request."""
        if not self.available or self.api is None:
            return {"error": "Not available on this platform"}
        capture = self.api.get_display_affinity(hwnd)
        styles = self.api.get_exstyle(hwnd)
        title = self.api.get_title(hwnd)
        expected_title = self._titles.get(hwnd)
        required_styles = (
            self.WS_EX_TOOLWINDOW | self.WS_EX_LAYERED | self.WS_EX_TRANSPARENT
        )
        healthy = (
            capture.success
            and capture.value == self.WDA_EXCLUDEFROMCAPTURE
            and styles.success
            and styles.value & required_styles == required_styles
            and expected_title is not None
            and title.success
            and title.value == expected_title
        )
        if healthy:
            results = {
                "capture_protection": True,
                "alt_tab_hidden": True,
                "title_disguised": True,
                "mouse_passthrough": True,
            }
            self.last_report["verification"] = {"healthy": True, "reapplied": False}
            return results
        results = self.apply_all_protections(hwnd)
        self.last_report["verification"] = {
            "healthy": all(results.values()),
            "reapplied": True,
        }
        return results

    def remove_all_protections(self, hwnd: int) -> bool:
        if not self.available:
            return False
        capture_removed = self.set_capture_protection(hwnd, False)
        transparency_reset = self.set_transparency(hwnd, 255)
        return capture_removed and transparency_reset


stealth_manager = StealthManager()
