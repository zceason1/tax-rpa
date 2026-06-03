import ctypes
import time
from ctypes import wintypes


mouse_user32 = ctypes.WinDLL("user32", use_last_error=True)

MouseSetCursorPos = mouse_user32.SetCursorPos
MouseGetCursorPos = mouse_user32.GetCursorPos
MouseEvent = mouse_user32.mouse_event
GetSystemMetrics = mouse_user32.GetSystemMetrics

MouseSetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
MouseSetCursorPos.restype = wintypes.BOOL
GetSystemMetrics.argtypes = [ctypes.c_int]
GetSystemMetrics.restype = ctypes.c_int
MouseEvent.argtypes = [
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.DWORD,
    ctypes.c_void_p,
]

SM_CXSCREEN = 0
SM_CYSCREEN = 1
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_ABSOLUTE = 0x8000


class POINT(ctypes.Structure):
    """point，封装底层驱动、鼠标驱动相关状态和行为。"""
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


def get_cursor_point() -> list[int]:
    """执行底层驱动、鼠标驱动中的getcursorpoint逻辑，供业务流程或相邻模块调用。"""
    point = POINT()
    if not MouseGetCursorPos(ctypes.byref(point)):
        raise ctypes.WinError(ctypes.get_last_error())
    return [point.x, point.y]


def point_near(actual: list[int], expected: list[int], tolerance: int = 2) -> bool:
    """执行底层驱动、鼠标驱动中的pointnear逻辑，供业务流程或相邻模块调用。"""
    return (
        abs(int(actual[0]) - int(expected[0])) <= tolerance
        and abs(int(actual[1]) - int(expected[1])) <= tolerance
    )


def to_absolute_mouse_coordinates(point: list[int], screen_size: list[int]) -> list[int]:
    """执行底层驱动、鼠标驱动中的toabsolute鼠标coordinates逻辑，供业务流程或相邻模块调用。"""
    width = max(1, int(screen_size[0]) - 1)
    height = max(1, int(screen_size[1]) - 1)
    return [
        round(max(0, min(int(point[0]), width)) * 65535 / width),
        round(max(0, min(int(point[1]), height)) * 65535 / height),
    ]


class MouseDriver:
    """鼠标驱动驱动，封装底层系统能力，供页面组件调用。"""
    def move_to(self, point: list[int], settle_seconds: float = 0.15) -> dict[str, object]:
        """执行底层驱动、鼠标驱动中的moveto逻辑，供业务流程或相邻模块调用。"""
        attempts = []
        for _attempt in range(5):
            MouseSetCursorPos(int(point[0]), int(point[1]))
            time.sleep(max(0.0, settle_seconds))
            actual = get_cursor_point()
            attempts.append({"method": "SetCursorPos", "actual": actual})
            if point_near(actual, point):
                return {
                    "requested": point,
                    "actual": actual,
                    "move_method": "SetCursorPos",
                    "attempts": attempts,
                }

        screen_size = [GetSystemMetrics(SM_CXSCREEN), GetSystemMetrics(SM_CYSCREEN)]
        absolute = to_absolute_mouse_coordinates(point, screen_size)
        for _attempt in range(5):
            MouseEvent(
                MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE,
                absolute[0],
                absolute[1],
                0,
                None,
            )
            time.sleep(max(0.0, settle_seconds))
            actual = get_cursor_point()
            attempts.append({"method": "mouse_event_absolute_move", "actual": actual})
            if point_near(actual, point):
                return {
                    "requested": point,
                    "actual": actual,
                    "move_method": "mouse_event_absolute_move",
                    "attempts": attempts,
                }

        raise RuntimeError(
            f"Cursor did not move to target. expected={point}, actual={actual}, attempts={attempts}"
        )

    def click(self, point: list[int], press_seconds: float = 0.08) -> dict[str, object]:
        """执行底层驱动、鼠标驱动中的click逻辑，供业务流程或相邻模块调用。"""
        move_result = self.move_to(point)
        MouseEvent(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, None)
        time.sleep(max(0.01, press_seconds))
        MouseEvent(MOUSEEVENTF_LEFTUP, 0, 0, 0, None)
        return move_result
