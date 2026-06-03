from dataclasses import dataclass


@dataclass(frozen=True)
class TextTarget:
    """文本目标，封装页面、shared、元素定义、目标相关状态和行为。"""
    text: str
    aliases: tuple[str, ...] = ()
    screenshot_name: str = ""

    @property
    def texts(self) -> tuple[str, ...]:
        """返回文本目标的主文本和别名，供 OCR 或 UIA 匹配。"""
        return (self.text, *self.aliases)
