from dataclasses import dataclass


@dataclass(frozen=True)
class TextTarget:
    text: str
    aliases: tuple[str, ...] = ()
    screenshot_name: str = ""

    @property
    def texts(self) -> tuple[str, ...]:
        return (self.text, *self.aliases)
