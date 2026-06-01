import ctypes
import subprocess
import time
from ctypes import wintypes
from pathlib import Path
from typing import Any

import psutil

from tax_rpa.constants import FILE_DIALOG_TITLE_HINTS
from tax_rpa.utils import normalize_text


user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
shell32 = ctypes.windll.shell32

try:
    user32.SetProcessDPIAware()
except Exception:
    pass

EnumWindows = user32.EnumWindows
EnumChildWindows = user32.EnumChildWindows
GetWindowThreadProcessId = user32.GetWindowThreadProcessId
GetWindowTextLengthW = user32.GetWindowTextLengthW
GetWindowTextW = user32.GetWindowTextW
GetClassNameW = user32.GetClassNameW
GetWindowRect = user32.GetWindowRect
IsWindowVisible = user32.IsWindowVisible
GetForegroundWindow = user32.GetForegroundWindow
ShowWindow = user32.ShowWindow
BringWindowToTop = user32.BringWindowToTop
SetForegroundWindow = user32.SetForegroundWindow
SetFocus = user32.SetFocus
SetWindowPos = user32.SetWindowPos
AttachThreadInput = user32.AttachThreadInput
GetCurrentThreadId = kernel32.GetCurrentThreadId
SendMessageW = user32.SendMessageW
ShellExecuteW = shell32.ShellExecuteW

SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
ShellExecuteW.argtypes = [
    wintypes.HWND,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    ctypes.c_int,
]
ShellExecuteW.restype = ctypes.c_void_p
SetWindowPos.argtypes = [
    wintypes.HWND,
    wintypes.HWND,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT,
]
AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]

SW_RESTORE = 9
HWND_TOPMOST = wintypes.HWND(-1)
HWND_NOTOPMOST = wintypes.HWND(-2)
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_SHOWWINDOW = 0x0040
WM_SETTEXT = 0x000C


def get_text(hwnd: int) -> str:
    length = GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def get_class(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(256)
    GetClassNameW(hwnd, buf, 256)
    return buf.value


def get_rect(hwnd: int) -> list[int]:
    rect = wintypes.RECT()
    GetWindowRect(hwnd, ctypes.byref(rect))
    return [rect.left, rect.top, rect.right, rect.bottom]


def rect_size(rect: list[int]) -> list[int]:
    return [rect[2] - rect[0], rect[3] - rect[1]]


def rect_area(rect: list[int]) -> int:
    return max(0, rect[2] - rect[0]) * max(0, rect[3] - rect[1])


def rect_center(rect: list[int]) -> list[int]:
    return [round((rect[0] + rect[2]) / 2), round((rect[1] + rect[3]) / 2)]


def window_pid(hwnd: int) -> int:
    pid = wintypes.DWORD()
    GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def window_thread_id(hwnd: int) -> int:
    pid = wintypes.DWORD()
    return int(GetWindowThreadProcessId(hwnd, ctypes.byref(pid)))


def window_info(hwnd: int) -> dict[str, Any]:
    rect = get_rect(hwnd)
    width, height = rect_size(rect)
    return {
        "hwnd": hwnd,
        "pid": window_pid(hwnd),
        "visible": bool(IsWindowVisible(hwnd)),
        "title": get_text(hwnd),
        "class": get_class(hwnd),
        "rect": rect,
        "size": [width, height],
        "area": width * height,
    }


def collect_top_windows() -> list[dict[str, Any]]:
    windows: list[dict[str, Any]] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def enum_top(hwnd: int, _lparam: int) -> bool:
        if IsWindowVisible(hwnd):
            info = window_info(hwnd)
            if info["area"] > 0:
                windows.append(info)
        return True

    EnumWindows(enum_top, 0)
    windows.sort(key=lambda item: item["area"], reverse=True)
    return windows


def collect_top_windows_for_pids(pids: list[int]) -> list[dict[str, Any]]:
    pid_set = set(pids)
    windows = [window for window in collect_top_windows() if window["pid"] in pid_set]
    windows.sort(key=lambda item: (not item["visible"], -item["area"]))
    return windows


def collect_children(hwnd: int) -> list[dict[str, Any]]:
    children: list[dict[str, Any]] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def enum_child(child: int, _lparam: int) -> bool:
        children.append(window_info(child))
        return True

    EnumChildWindows(hwnd, enum_child, 0)
    children.sort(key=lambda item: (not item["visible"], item["rect"][1], item["rect"][0]))
    return children


def find_main_window(pids: list[int], logger: Any = None) -> dict[str, Any]:
    windows = collect_top_windows_for_pids(pids)
    if logger:
        logger.write_json("top_windows_before_find_main.json", windows)

    candidates = [
        window
        for window in windows
        if window["visible"] and window["area"] > 100000 and window["class"] == "Tfrm_MainFrame"
    ]
    if not candidates:
        candidates = [
            window
            for window in windows
            if window["visible"]
            and window["area"] > 100000
            and "自然人电子税务局" in window["title"]
        ]
    if not candidates:
        raise RuntimeError("未找到正式主窗口 Tfrm_MainFrame，请确认客户端主界面可见且权限一致")
    return sorted(candidates, key=lambda item: item["area"], reverse=True)[0]


def set_foreground(hwnd: int) -> None:
    foreground = GetForegroundWindow()
    current_thread = int(GetCurrentThreadId())
    foreground_thread = window_thread_id(foreground) if foreground else 0
    target_thread = window_thread_id(hwnd)

    attached_foreground = False
    attached_target = False
    try:
        if foreground_thread and foreground_thread != current_thread:
            attached_foreground = bool(AttachThreadInput(current_thread, foreground_thread, True))
        if target_thread and target_thread != current_thread:
            attached_target = bool(AttachThreadInput(current_thread, target_thread, True))

        ShowWindow(hwnd, SW_RESTORE)
        SetWindowPos(
            hwnd,
            HWND_TOPMOST,
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW,
        )
        time.sleep(0.05)
        SetWindowPos(
            hwnd,
            HWND_NOTOPMOST,
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW,
        )
        BringWindowToTop(hwnd)
        SetForegroundWindow(hwnd)
        SetFocus(hwnd)
    finally:
        if attached_target:
            AttachThreadInput(current_thread, target_thread, False)
        if attached_foreground:
            AttachThreadInput(current_thread, foreground_thread, False)
    time.sleep(0.4)


def collect_window_texts(hwnd: int) -> list[str]:
    texts = [get_text(hwnd)]
    texts.extend(child["title"] for child in collect_children(hwnd) if child["title"])
    return [text for text in texts if text]


def find_file_dialog(timeout_seconds: int, allowed_pids: set[int] | None = None) -> dict[str, Any] | None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        dialogs = []
        for window in collect_top_windows():
            if allowed_pids is not None and window["pid"] not in allowed_pids:
                continue
            title = window["title"]
            if window["class"] != "#32770":
                continue
            if not any(hint in title for hint in FILE_DIALOG_TITLE_HINTS):
                continue
            dialogs.append(window)
        if dialogs:
            return sorted(dialogs, key=lambda item: item["area"], reverse=True)[0]
        time.sleep(0.4)
    return None


def wait_for_dialog_closed(hwnd: int, timeout_seconds: int) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if not bool(IsWindowVisible(hwnd)):
            return True
        time.sleep(0.3)
    return False


def find_largest_edit_control(dialog_hwnd: int) -> dict[str, Any] | None:
    edits = [
        child
        for child in collect_children(dialog_hwnd)
        if child["visible"] and child["class"] == "Edit" and rect_area(child["rect"]) > 0
    ]
    if not edits:
        return None
    return sorted(edits, key=lambda item: item["area"], reverse=True)[0]


def find_button_by_labels(
    children: list[dict[str, Any]],
    labels: tuple[str, ...],
) -> dict[str, Any] | None:
    normalized_labels = [normalize_text(label).lower() for label in labels]
    matches = []
    for child in children:
        if not child.get("visible") or child.get("class") != "Button":
            continue
        title = normalize_text(str(child.get("title", ""))).lower()
        if not title:
            continue
        if any(label in title for label in normalized_labels):
            matches.append(child)
    if not matches:
        return None
    return sorted(matches, key=lambda item: item["rect"][1], reverse=True)[0]


def set_window_text(hwnd: int, text: str) -> None:
    path_buffer = ctypes.create_unicode_buffer(str(text))
    SendMessageW(hwnd, WM_SETTEXT, 0, ctypes.addressof(path_buffer))


def unique_pids(pids: list[int]) -> list[int]:
    seen = set()
    result = []
    for pid in pids:
        if pid in seen:
            continue
        seen.add(pid)
        result.append(pid)
    return result


def split_pids_by_existence(pids: list[int]) -> tuple[list[int], list[int]]:
    gone = []
    alive = []
    for pid in pids:
        try:
            exists = psutil.pid_exists(pid)
        except psutil.Error:
            exists = True
        if exists:
            alive.append(pid)
        else:
            gone.append(pid)
    return gone, alive


def process_handles_for_pids(pids: list[int]) -> list[psutil.Process]:
    processes = []
    for pid in pids:
        try:
            processes.append(psutil.Process(pid))
        except psutil.NoSuchProcess:
            pass
    return processes


class Win32Driver:
    def find_process_ids(self, process_name: str) -> list[int]:
        expected = process_name.lower()
        pids = []
        for proc in psutil.process_iter(["pid", "name"]):
            if (proc.info.get("name") or "").lower() == expected:
                pids.append(int(proc.info["pid"]))
        return pids

    def configure_base_process_name(self, process_name: str) -> None:
        self.process_name = process_name.lower()

    def launch_client(self, app_path: Path, logger: Any) -> subprocess.Popen | None:
        logger.log("launch_client", "start", app_path=str(app_path))
        if app_path.suffix.lower() == ".lnk":
            result = ShellExecuteW(
                None,
                "open",
                str(app_path),
                None,
                str(app_path.parent),
                1,
            )
            if result <= 32:
                raise RuntimeError(f"Failed to launch shortcut. ShellExecuteW={result}: {app_path}")
            logger.log("launch_client", "started_shortcut", shell_execute=result)
            return None

        process = subprocess.Popen([str(app_path)], cwd=str(app_path.parent))
        logger.log("launch_client", "started", pid=process.pid)
        return process

    def wait_for_process(self, process_name: str, timeout_seconds: int, logger: Any) -> list[int]:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            pids = self.find_process_ids(process_name)
            if pids:
                logger.log("wait_process", "found", pids=pids)
                return pids
            time.sleep(1.0)
        raise RuntimeError(f"Timed out waiting for process: {process_name}")

    def terminate_processes(
        self,
        pids: list[int],
        timeout_seconds: int,
        logger: Any,
    ) -> dict[str, Any]:
        processes = []
        terminated_pids = []
        for pid in pids:
            try:
                proc = psutil.Process(pid)
                proc.terminate()
                processes.append(proc)
            except psutil.NoSuchProcess:
                terminated_pids.append(pid)

        try:
            gone, alive = psutil.wait_procs(processes, timeout=timeout_seconds)
        except psutil.AccessDenied:
            gone_pids, alive_pids = split_pids_by_existence([proc.pid for proc in processes])
            terminated_pids.extend(gone_pids)
            gone = []
            alive = process_handles_for_pids(alive_pids)
        terminated_pids.extend(proc.pid for proc in gone)
        for proc in alive:
            try:
                proc.kill()
            except psutil.NoSuchProcess:
                terminated_pids.append(proc.pid)
            except psutil.AccessDenied:
                pass
        if alive:
            try:
                gone_after_kill, alive_after_kill = psutil.wait_procs(alive, timeout=5)
            except psutil.AccessDenied:
                gone_pids, alive_pids = split_pids_by_existence([proc.pid for proc in alive])
                terminated_pids.extend(gone_pids)
                alive = process_handles_for_pids(alive_pids)
            else:
                terminated_pids.extend(proc.pid for proc in gone_after_kill)
                alive = alive_after_kill
        gone_pids, alive_pids = split_pids_by_existence([proc.pid for proc in alive])
        terminated_pids.extend(gone_pids)
        alive = process_handles_for_pids(alive_pids)

        result = {
            "requested": pids,
            "terminated": unique_pids(terminated_pids),
            "alive": unique_pids([proc.pid for proc in alive]),
            "timeout_seconds": timeout_seconds,
        }
        logger.log(
            "terminate_processes",
            "ok" if not alive else "alive_after_kill",
            **result,
        )
        return result

    def find_main_window(self, pids: list[int], logger: Any) -> dict[str, Any]:
        return find_main_window(pids, logger=logger)

    def set_foreground(self, hwnd: int) -> None:
        set_foreground(hwnd)

    def collect_top_windows(self) -> list[dict[str, Any]]:
        return collect_top_windows()

    def collect_top_windows_for_pids(self, pids: list[int]) -> list[dict[str, Any]]:
        return collect_top_windows_for_pids(pids)

    def collect_children(self, hwnd: int) -> list[dict[str, Any]]:
        return collect_children(hwnd)

    def get_rect(self, hwnd: int) -> list[int]:
        return get_rect(hwnd)

    def collect_window_texts(self, hwnd: int) -> list[str]:
        return collect_window_texts(hwnd)

    def find_file_dialog(
        self,
        timeout_seconds: int,
        allowed_pids: set[int] | None = None,
    ) -> dict[str, Any] | None:
        return find_file_dialog(timeout_seconds, allowed_pids)

    def wait_for_dialog_closed(self, hwnd: int, timeout_seconds: int) -> bool:
        return wait_for_dialog_closed(hwnd, timeout_seconds)

    def find_largest_edit_control(self, dialog_hwnd: int) -> dict[str, Any] | None:
        return find_largest_edit_control(dialog_hwnd)

    def find_button_by_labels(
        self,
        children: list[dict[str, Any]],
        labels: tuple[str, ...],
    ) -> dict[str, Any] | None:
        return find_button_by_labels(children, labels)

    def set_window_text(self, hwnd: int, text: str) -> None:
        set_window_text(hwnd, text)

    def rect_center(self, rect: list[int]) -> list[int]:
        return rect_center(rect)
