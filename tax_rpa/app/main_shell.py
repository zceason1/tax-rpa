from tax_rpa.pages.person_info_page import PersonInfoPage
from tax_rpa.runtime.context import RpaContext


class MainShell:
    def __init__(self, context: RpaContext) -> None:
        self.context = context

    def open_person_info_page(self) -> PersonInfoPage:
        if self.context.hwnd is None:
            raise RuntimeError("Main window is not available")
        page = PersonInfoPage(self.context, self.context.hwnd)
        page.open()
        return page
