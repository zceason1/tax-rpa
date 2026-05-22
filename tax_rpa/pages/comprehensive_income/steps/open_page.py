from typing import Any


class OpenComprehensiveIncomePageStep:
    def __init__(self, shell: Any) -> None:
        self.shell = shell

    def run(self):
        return self.shell.open_comprehensive_income_page()
