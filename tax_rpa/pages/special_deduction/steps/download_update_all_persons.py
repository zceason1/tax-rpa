from typing import TYPE_CHECKING

from tax_rpa.runtime.result import StepResult

if TYPE_CHECKING:
    from tax_rpa.pages.special_deduction.page import SpecialDeductionPage


class DownloadUpdateAllPersonsStep:
    """下载更新全部人员步骤步骤，封装该页面动作的执行入口。"""
    def __init__(self, page: "SpecialDeductionPage") -> None:
        """初始化下载更新全部人员步骤实例，保存依赖、配置和运行上下文。"""
        self.page = page

    def run(self) -> StepResult:
        """执行当前步骤或工作流的主流程，并返回标准结果。"""
        with self.page.step("鐐瑰嚮涓嬭浇鏇存柊"):
            download_result = self.page.click_download_update()

        with self.page.step("鐐瑰嚮鍏ㄩ儴浜哄憳"):
            try:
                all_persons_result = self.page.click_all_persons()
            except RuntimeError as exc:
                all_persons_result = self.page.click_all_persons_fallback(download_result, exc)

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
            error_type=download_result.error_type or all_persons_result.error_type,
            error_code=download_result.error_code or all_persons_result.error_code,
            side_effect_started=all_persons_result.ok or all_persons_result.side_effect_started,
            side_effect_committed=all_persons_result.ok or all_persons_result.side_effect_committed,
            retry_allowed=False if all_persons_result.ok else all_persons_result.retry_allowed,
        )
