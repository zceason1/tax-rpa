def clamp_rect(rect: list[int]) -> list[int]:
    """执行底层驱动、区域驱动中的clamp矩形区域逻辑，供业务流程或相邻模块调用。"""
    return [
        int(min(rect[0], rect[2])),
        int(min(rect[1], rect[3])),
        int(max(rect[0], rect[2])),
        int(max(rect[1], rect[3])),
    ]


class RegionDriver:
    """区域驱动驱动，封装底层系统能力，供页面组件调用。"""
    def detect_left_nav_rect(
        self,
        main_rect: list[int],
        children: list[dict],
    ) -> tuple[list[int], dict]:
        """执行底层驱动、区域驱动中的detect左侧导航矩形区域逻辑，供业务流程或相邻模块调用。"""
        left, top, right, bottom = main_rect
        window_width = right - left
        window_height = bottom - top

        candidates = []
        for child in children:
            x1, y1, x2, y2 = child["rect"]
            width = x2 - x1
            height = y2 - y1
            if width <= 0 or height <= 0:
                continue

            near_left = x1 <= left + window_width * 0.05
            reasonable_width = window_width * 0.08 <= width <= window_width * 0.25
            tall = height >= window_height * 0.45
            below_header = y1 >= top + window_height * 0.08

            if near_left and reasonable_width and tall and below_header:
                candidates.append((width * height, child["rect"], child))

        if candidates:
            _, rect, child = sorted(candidates, key=lambda item: item[0], reverse=True)[0]
            return clamp_rect(rect), child

        return clamp_rect(
            [
                left,
                top + round(window_height * 0.13),
                left + round(window_width * 0.16),
                top + round(window_height * 0.96),
            ]
        ), {"fallback": True}

    def detect_content_rect(
        self,
        main_rect: list[int],
        nav_rect: list[int],
        children: list[dict],
    ) -> tuple[list[int], dict]:
        """执行底层驱动、区域驱动中的detect内容矩形区域逻辑，供业务流程或相邻模块调用。"""
        left, top, right, bottom = main_rect
        nav_right = nav_rect[2]
        window_width = right - left
        window_height = bottom - top

        candidates = []
        for child in children:
            x1, y1, x2, y2 = child["rect"]
            width = x2 - x1
            height = y2 - y1
            if width <= 0 or height <= 0:
                continue

            starts_after_nav = x1 >= nav_right - 2
            wide = width >= window_width * 0.45
            tall = height >= window_height * 0.45
            below_header = y1 >= top + window_height * 0.08

            if starts_after_nav and wide and tall and below_header:
                candidates.append((width * height, child["rect"], child))

        if candidates:
            _, rect, child = sorted(candidates, key=lambda item: item[0], reverse=True)[0]
            return clamp_rect(rect), child

        return clamp_rect([nav_right, nav_rect[1], right, nav_rect[3]]), {"fallback": True}
