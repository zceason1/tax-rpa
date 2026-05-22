from typing import TYPE_CHECKING

from tax_rpa.runtime.result import StepResult

if TYPE_CHECKING:
    from tax_rpa.pages.special_deduction.page import SpecialDeductionPage


class DownloadUpdateAllPersonsStep:
    def __init__(self, page: "SpecialDeductionPage") -> None:
        self.page = page

    def run(self) -> StepResult:
        with self.page.step("点击下载更新"):
            download_result = self.page.click_download_update()

        with self.page.step("点击全部人员"):
            all_persons_result = self.page.click_all_persons()

        ok = download_result.ok and all_persons_result.ok
        return StepResult(
            ok=ok,
            name="special_deduction.download_update_all_persons",
            status=all_persons_result.status if ok else "failed",
            evidence={
                "download_update": download_result,
                "all_persons": all_persons_result,
            },
            error=download_result.error or all_persons_result.error,
        )
