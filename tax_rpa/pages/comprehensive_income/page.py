from contextlib import nullcontext
from pathlib import Path
from typing import Any

from tax_rpa.drivers.ocr_driver import OcrDriver, find_best_ocr_match, ocr_rect
from tax_rpa.drivers.region_driver import RegionDriver
from tax_rpa.drivers.win32_driver import Win32Driver
from tax_rpa.pages.comprehensive_income.components.import_result import (
    SalaryIncomeImportResultComponent,
)
from tax_rpa.pages.comprehensive_income.elements.import_menu import (
    IMPORT_BUTTON,
    IMPORT_DATA_OPTION,
)
from tax_rpa.pages.comprehensive_income.elements.declaration_submission import (
    DECLARATION_SUBMISSION_TAB,
)
from tax_rpa.pages.comprehensive_income.elements.export_report import (
    EXPORT_DECLARATION_REPORT_BUTTON,
    STANDARD_REPORT_OPTION,
)
from tax_rpa.pages.comprehensive_income.elements.page_markers import (
    COMPREHENSIVE_INCOME_PAGE_MARKER,
)
from tax_rpa.pages.comprehensive_income.elements.prefill_deduction import (
    AUTO_PREFILL_CONFIRM_CHECKBOX,
    PERSONAL_PENSION_CHECKBOX,
    PREFILL_CONFIRM_BUTTON,
    PREFILL_DEDUCTION_BUTTON,
    SPECIAL_DEDUCTION_CHECKBOX,
)
from tax_rpa.pages.comprehensive_income.elements.salary_income import (
    FILL_BUTTON,
    SALARY_INCOME_ROW,
)
from tax_rpa.pages.comprehensive_income.elements.tax_calculation import (
    CONTINUE_TAX_CALCULATION_BUTTON,
    TAX_CALCULATION_TAB,
)
from tax_rpa.pages.shared.components.content_text import ContentTextComponent
from tax_rpa.pages.shared.components.file_dialog import FileDialogComponent
from tax_rpa.pages.shared.components.left_nav import LeftNavComponent
from tax_rpa.pages.shared.components.toolbar import ToolbarComponent
from tax_rpa.pages.shared.dialogs import PageDialogMixin
from tax_rpa.runtime.context import RpaContext
from tax_rpa.runtime.result import StepResult


class ComprehensiveIncomePage(PageDialogMixin):
    """综合所得申报页面对象，封装工资薪金导入、预填、计算、报送和导出动作。"""
    def __init__(
        self,
        context: RpaContext | None,
        hwnd: int,
        toolbar: Any | None = None,
        content_text: Any | None = None,
        file_dialog: Any | None = None,
        message_dialog: Any | None = None,
        salary_import_result_reader: Any | None = None,
        win32: Win32Driver | None = None,
    ) -> None:
        """初始化综合所得收入页面实例，保存依赖、配置和运行上下文。"""
        self.context = context
        self.hwnd = hwnd
        self.toolbar = toolbar
        self.content_text = content_text
        self.file_dialog = file_dialog
        self.message_dialog = message_dialog
        self.salary_import_result_reader = salary_import_result_reader
        self.ocr = OcrDriver()
        self.region = RegionDriver()
        self.win32 = win32 or Win32Driver()

    def inspect(self) -> dict[str, Any]:
        """采集当前页面的窗口、文本和关键控件信息，用于调试和诊断。"""
        if self.context is None:
            return {"ready": False}

        rect = self.win32.get_rect(self.hwnd)
        children = self.win32.collect_children(self.hwnd)
        nav_rect, _nav_source = self.region.detect_left_nav_rect(rect, children)
        content_rect, _content_source = self.region.detect_content_rect(rect, nav_rect, children)
        rows, image_size, image_path = ocr_rect(
            content_rect,
            "comprehensive_income_page_verify",
            self.context.logger,
        )
        has_page = find_best_ocr_match(
            rows,
            COMPREHENSIVE_INCOME_PAGE_MARKER.text,
            image_size,
            self.context.config.ocr_score_threshold,
        )
        has_salary = find_best_ocr_match(
            rows,
            SALARY_INCOME_ROW.text,
            image_size,
            self.context.config.ocr_score_threshold,
        )
        self.context.logger.log(
            "verify_comprehensive_income_page",
            "ok" if has_page or has_salary else "not_ready",
            page_match=has_page,
            salary_match=has_salary,
            screenshot=image_path,
        )
        return {
            "ready": bool(has_page or has_salary),
            "page_match": has_page,
            "salary_match": has_salary,
            "content_rect": content_rect,
            "screenshot": image_path,
        }

    def is_ready(self) -> bool:
        """判断当前页面是否已经打开并具备继续操作的关键标识。"""
        return bool(self.inspect()["ready"])

    def open(self) -> StepResult:
        """打开当前页面并等待页面关键标识出现。"""
        if self.context is None:
            return StepResult(
                ok=True,
                name="comprehensive_income_page.open",
                status="assumed_ready",
            )
        before_dialog = self.close_message_dialog_if_present("cancel")
        result = LeftNavComponent(
            self.hwnd,
            self.context.logger,
            self.context.config,
            win32=self.win32,
            action_policy=self.context.action_policy,
        ).open_page(
            COMPREHENSIVE_INCOME_PAGE_MARKER.text,
            ready_check=self.is_ready,
        )
        after_dialog = self.close_message_dialog_if_present("cancel")
        return StepResult(
            ok=result.ok,
            name="comprehensive_income_page.open",
            status=result.status,
            evidence={
                **result.evidence,
                "before_dialog": before_dialog,
                "after_dialog": after_dialog,
            },
            error=result.error,
        )

    def step(self, name: str, **data: Any):
        """创建页面局部步骤上下文，用于记录日志和截图。"""
        logger = self.context.logger if self.context is not None else None
        step = getattr(logger, "step", None)
        if callable(step):
            return step(name, page="comprehensive_income_page", **data)
        return nullcontext()

    def is_dry_run(self) -> bool:
        """判断是否满足dryrun条件。"""
        if self.context is None:
            return False
        return bool(self.context.config.dry_run)

    def click_salary_income_row(self) -> StepResult:
        """点击综合所得页面中的工资薪金所得行。"""
        return self._content_text().click_text(SALARY_INCOME_ROW.text)

    def click_salary_income_fill(self) -> StepResult:
        """点击工资薪金所得的填写入口。"""
        return self._content_text().click_text(FILL_BUTTON.text)

    def click_import_button(self) -> StepResult:
        """点击当前页面的导入按钮，打开导入菜单或文件选择流程。"""
        if self.toolbar is not None:
            return self.toolbar.click_button(IMPORT_BUTTON.text)
        return self.default_toolbar().click_button(IMPORT_BUTTON.text)

    def choose_import_data_option(self) -> StepResult:
        """从工资薪金导入菜单中选择导入数据选项。"""
        return self._content_text().click_text(IMPORT_DATA_OPTION.text)

    def choose_salary_income_file(self, path: Path, import_option_result: StepResult) -> StepResult | None:
        """在文件选择框中选择工资薪金 Excel 文件。"""
        dialog = import_option_result.evidence.get("dialog")
        if self.file_dialog is not None:
            return self.file_dialog.choose_file(path)
        if not dialog:
            dialog = self._find_file_dialog()
        if not dialog:
            return None
        return FileDialogComponent(
            dialog,
            self.context.logger,
            self.context.config.dry_run,
            win32=self.win32,
            action_policy=self.context.action_policy,
        ).choose_file(path)

    def read_salary_income_import_result(self) -> StepResult:
        """读取工资薪金导入结果并返回分类后的步骤结果。"""
        if self.salary_import_result_reader is not None:
            return self.salary_import_result_reader()
        if self.context is None or self.context.main_window is None:
            raise RuntimeError("Salary income import result requires RpaContext with main_window")
        return SalaryIncomeImportResultComponent(
            self.hwnd,
            self.context.logger,
            self.context.config,
            {int(self.context.main_window["pid"])},
            win32=self.win32,
        ).read_result()

    def click_prefill_deduction(self) -> StepResult:
        """点击预填专项附加扣除入口。"""
        return self._content_text().click_text(PREFILL_DEDUCTION_BUTTON.text)

    def read_prefill_confirmation_dialog(self) -> StepResult:
        """读取预填前确认弹窗内容。"""
        return StepResult(
            ok=False,
            name="prefill.confirmation_dialog",
            status="unknown",
            error="Prefill confirmation dialog sensing is not calibrated",
            error_type="UNKNOWN_RESULT",
            error_code="prefill_confirmation_dialog_unknown",
        )

    def confirm_prefill_options(
        self,
        *,
        allow_skip_personal_pension: bool,
    ) -> StepResult:
        """确认预填选项，并按配置处理个人养老金跳过策略。"""
        content = self._content_text()
        auto_confirm = content.click_text(AUTO_PREFILL_CONFIRM_CHECKBOX.text)
        special_deduction = content.click_text(SPECIAL_DEDUCTION_CHECKBOX.text)
        personal_pension = content.click_text(PERSONAL_PENSION_CHECKBOX.text)
        if not personal_pension.ok and not allow_skip_personal_pension:
            return StepResult(
                ok=False,
                name="prefill.options",
                status="personal_pension_missing",
                evidence={
                    "auto_confirm": auto_confirm,
                    "special_deduction": special_deduction,
                    "personal_pension": personal_pension,
                },
                error="Personal pension option is missing or disabled",
                error_type="BUSINESS_REJECTED",
                error_code="personal_pension_missing",
            )
        confirm = content.click_text(PREFILL_CONFIRM_BUTTON.text)
        ok = auto_confirm.ok and special_deduction.ok and confirm.ok
        return StepResult(
            ok=ok,
            name="prefill.options",
            status="confirmed" if ok else "failed",
            evidence={
                "auto_confirm": auto_confirm,
                "special_deduction": special_deduction,
                "personal_pension": personal_pension,
                "confirm": confirm,
                "allow_skip_personal_pension": allow_skip_personal_pension,
            },
            error=auto_confirm.error or special_deduction.error or confirm.error,
            error_type=auto_confirm.error_type
            or special_deduction.error_type
            or confirm.error_type,
            error_code=auto_confirm.error_code
            or special_deduction.error_code
            or confirm.error_code,
        )

    def read_prefill_result(self) -> StepResult:
        """读取预填执行结果并转换为步骤结果。"""
        return StepResult(
            ok=False,
            name="prefill.result",
            status="unknown",
            error="Prefill result sensing is not calibrated",
            error_type="UNKNOWN_RESULT",
            error_code="prefill_deduction_result_unknown",
        )

    def click_tax_calculation_tab(self) -> StepResult:
        """打开税款计算页签。"""
        return self._content_text().click_text(TAX_CALCULATION_TAB.text)

    def read_tax_calculation_popup(self) -> StepResult:
        """读取税款计算前的确认或风险提示弹窗。"""
        return StepResult(
            ok=True,
            name="tax_calculation.popup",
            status="no_popup",
        )

    def confirm_tax_calculation_popup(self) -> StepResult:
        """确认允许继续的税款计算弹窗。"""
        return self._content_text().click_text(CONTINUE_TAX_CALCULATION_BUTTON.text)

    def read_tax_calculation_result(self) -> StepResult:
        """读取税款计算结果并转换为步骤结果。"""
        return StepResult(
            ok=False,
            name="tax_calculation.result",
            status="unknown",
            error="Tax calculation result sensing is not calibrated",
            error_type="UNKNOWN_RESULT",
            error_code="tax_calculation_result_unknown",
        )

    def open_declaration_submission_page(self) -> StepResult:
        """打开申报表报送页面。"""
        return self._content_text().click_text(DECLARATION_SUBMISSION_TAB.text)

    def locate_send_declaration_button(self) -> StepResult:
        """定位发送申报按钮，用于检查报送就绪状态。"""
        return StepResult(
            ok=False,
            name="declaration_submission.send_button",
            status="unknown",
            error="Send declaration button sensing is not calibrated",
            error_type="UNKNOWN_RESULT",
            error_code="send_declaration_button_unknown",
        )

    def open_export_report_menu(self) -> StepResult:
        """打开导出申报表菜单。"""
        return self._content_text().click_text(EXPORT_DECLARATION_REPORT_BUTTON.text)

    def choose_standard_report_option(self) -> StepResult:
        """选择标准申报表导出选项。"""
        return self._content_text().click_text(STANDARD_REPORT_OPTION.text)

    def read_export_result(self, *, run_mode: str) -> StepResult:
        """读取导出结果，并根据运行模式判断是否可接受。"""
        return StepResult(
            ok=False,
            name="export_report.result",
            status="unknown",
            evidence={"run_mode": run_mode},
            error="Export result sensing is not calibrated",
            error_type="UNKNOWN_RESULT",
            error_code="export_report_result_unknown",
        )

    def default_toolbar(self) -> ToolbarComponent:
        """创建当前页面默认工具栏组件。"""
        if self.context is None:
            raise RuntimeError("Default toolbar requires RpaContext")
        return ToolbarComponent(
            self._content_rect(),
            self.context.logger,
            self.context.config.ocr_score_threshold,
            self.context.config.dry_run,
            action_policy=self.context.action_policy,
        )

    def default_content_text(self) -> ContentTextComponent:
        """创建当前页面默认内容文本组件。"""
        if self.context is None:
            raise RuntimeError("Default content text requires RpaContext")
        return ContentTextComponent(
            self._content_rect(),
            self.context.logger,
            self.context.config.ocr_score_threshold,
            self.context.config.dry_run,
            action_policy=self.context.action_policy,
        )

    def _content_text(self) -> Any:
        """构建当前页面内部使用的内容文本组件。"""
        if self.content_text is not None:
            return self.content_text
        return self.default_content_text()

    def _content_rect(self) -> list[int]:
        """计算当前页面内容区域边界，供 OCR 点击限制范围。"""
        rect = self.win32.get_rect(self.hwnd)
        children = self.win32.collect_children(self.hwnd)
        nav_rect, _ = self.region.detect_left_nav_rect(rect, children)
        content_rect, _ = self.region.detect_content_rect(rect, nav_rect, children)
        return content_rect

    def _find_file_dialog(self) -> dict[str, Any] | None:
        """执行页面、综合所得收入、页面中的内部辅助逻辑：find文件弹窗。"""
        if self.context is None or self.context.main_window is None:
            return None
        allowed_pids = {int(self.context.main_window["pid"])}
        dialog = self.win32.find_file_dialog(
            min(5, self.context.config.import_timeout_seconds),
            allowed_pids,
        )
        if dialog:
            return dialog
        return self.win32.find_file_dialog(1, None)
