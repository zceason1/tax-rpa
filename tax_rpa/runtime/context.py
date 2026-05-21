from dataclasses import dataclass
from typing import Any

from tax_rpa.config.person_import import PersonImportConfig


@dataclass
class RpaContext:
    config: PersonImportConfig
    logger: Any
    main_window: dict[str, Any] | None = None

    @property
    def hwnd(self) -> int | None:
        if not self.main_window:
            return None
        return int(self.main_window["hwnd"])
