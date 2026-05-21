from typing import Any


class OpenPersonInfoPageStep:
    def __init__(self, shell: Any) -> None:
        self.shell = shell

    def run(self):
        return self.shell.open_person_info_page()

