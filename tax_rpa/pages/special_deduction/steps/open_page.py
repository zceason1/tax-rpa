from typing import Any


class OpenSpecialDeductionPageStep:
    def __init__(self, shell: Any) -> None:
        self.shell = shell

    def run(self):
        return self.shell.open_special_deduction_page()
