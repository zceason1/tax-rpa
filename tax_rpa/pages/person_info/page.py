from collections.abc import Callable
from contextlib import nullcontext
from pathlib import Path
from typing import Any

from tax_rpa.drivers.ocr_driver import OcrDriver, find_best_ocr_match, ocr_rect
from tax_rpa.drivers.region_driver import RegionDriver
from tax_rpa.drivers.win32_driver import Win32Driver
from tax_rpa.pages.person_info.components.import_dropdown import ImportDropdownComponent
from tax_rpa.pages.person_info.components.import_result import ImportResultComponent
from tax_rpa.pages.person_info.elements.import_menu import (
    IMPORT_BUTTON,
    IMPORT_FILE_OPTIONS,
    SUBMIT_DATA_BUTTON,
)
from tax_rpa.pages.person_info.elements.page_markers import PERSON_INFO_PAGE_MARKER
from tax_rpa.pages.shared.components.file_dialog import FileDialogComponent
from tax_rpa.pages.shared.components.left_nav import LeftNavComponent
from tax_rpa.pages.shared.components.toolbar import ToolbarComponent
from tax_rpa.pages.shared.dialogs import PageDialogMixin
from tax_rpa.runtime.context import RpaContext
from tax_rpa.runtime.result import StepResult


class PersonInfoPage(PageDialogMixin):
    """人员信息采集页面对象，聚合页面组件并暴露业务动作。"""
    def __init__(
        self,
        context: RpaContext | None,
        hwnd: int,
        toolbar: Any | None = None,
        import_dropdown: Any | None = None,
        file_dialog: Any | None = None,
        message_dialog: Any | None = None,
        import_result_reader: Callable[[], StepResult] | None = None,
        win32: Win32Driver | None = None,
    ) -> None:
        """初始化人员信息页面实例，保存依赖、配置和运行上下文。"""
        self.context = context
        self.hwnd = hwnd
        self.toolbar = toolbar
        self.import_dropdown = import_dropdown
        self.file_dialog = file_dialog
        self.message_dialog = message_dialog
        self.import_result_reader = import_result_reader
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
        rows, image_size, image_path = ocr_rect(content_rect, "person_page_verify", self.context.logger)
        has_page = find_best_ocr_match(
            rows,
            PERSON_INFO_PAGE_MARKER.text,
            image_size,
            self.context.config.ocr_score_threshold,
        )
        has_import = find_best_ocr_match(
            rows,
            IMPORT_BUTTON.text,
            image_size,
            self.context.config.ocr_score_threshold,
        )
        self.context.logger.log(
            "verify_person_page",
            "ok" if has_page and has_import else "not_ready",
            page_match=has_page,
            import_match=has_import,
            screenshot=image_path,
        )
        return {
            "ready": bool(has_page and has_import),
            "page_match": has_page,
            "import_match": has_import,
            "content_rect": content_rect,
            "screenshot": image_path,
        }

    def is_ready(self) -> bool:
        """判断当前页面是否已经打开并具备继续操作的关键标识。"""
        return bool(self.inspect()["ready"])

    def open(self) -> StepResult:
        """打开当前页面并等待页面关键标识出现。"""
        if self.context is None:
            return StepResult(ok=True, name="person_info_page.open", status="assumed_ready")
        before_dialog = self.close_message_dialog_if_present("cancel")
        result = LeftNavComponent(
            self.hwnd,
            self.context.logger,
            self.context.config,
            win32=self.win32,
            action_policy=self.context.action_policy,
        ).open_page(
            PERSON_INFO_PAGE_MARKER.text,
            ready_check=self.is_ready,
        )
        after_dialog = self.close_message_dialog_if_present("cancel")
        return StepResult(
            ok=result.ok,
            name="person_info_page.open",
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
            return step(name, page="person_info_page", **data)
        return nullcontext()

    def _step(self, name: str, **data: Any):
        """创建内部步骤上下文，供页面动作复用统一日志格式。"""
        return self.step(name, **data)

    def click_import_button(self) -> StepResult:
        """点击当前页面的导入按钮，打开导入菜单或文件选择流程。"""
        if self.toolbar is not None:
            return self.toolbar.click_button(IMPORT_BUTTON.text)
        return self.default_toolbar().click_button(IMPORT_BUTTON.text)

    def choose_import_file_option(self) -> StepResult:
        """从人员信息导入菜单中选择导入文件选项。"""
        import_option = IMPORT_FILE_OPTIONS[0].text
        if self.import_dropdown is not None:
            return self.import_dropdown.choose_item(import_option)
        return self.default_import_dropdown().choose_item(import_option)

    def click_submit_data(self) -> StepResult:
        """点击人员信息导入后的提交数据按钮。"""
        if self.toolbar is not None:
            return self.toolbar.click_button(SUBMIT_DATA_BUTTON.text)
        return self.default_toolbar().click_button(SUBMIT_DATA_BUTTON.text)

    def choose_person_file(
        self,
        path: Path,
        dropdown_result: StepResult,
    ) -> StepResult | None:
        """在文件选择框中选择人员信息 Excel 文件。"""
        dialog = dropdown_result.evidence.get("dialog")
        if self.file_dialog is not None:
            return self.file_dialog.choose_file(path)
        if not dialog:
            return None
        return FileDialogComponent(
            dialog,
            self.context.logger,
            self.context.config.dry_run,
            win32=self.win32,
            action_policy=self.context.action_policy,
        ).choose_file(path)

    def read_import_result(self) -> StepResult:
        """读取人员信息导入结果并返回分类后的步骤结果。"""
        if self.import_result_reader is not None:
            return self.import_result_reader()
        return self.default_import_result_component().read_result()

    def default_toolbar(self) -> ToolbarComponent:
        """创建当前页面默认工具栏组件。"""
        if self.context is None:
            raise RuntimeError("Default toolbar requires RpaContext")
        rect = self.win32.get_rect(self.hwnd)
        children = self.win32.collect_children(self.hwnd)
        nav_rect, _ = self.region.detect_left_nav_rect(rect, children)
        content_rect, _ = self.region.detect_content_rect(rect, nav_rect, children)
        return ToolbarComponent(
            content_rect,
            self.context.logger,
            self.context.config.ocr_score_threshold,
            self.context.config.dry_run,
            action_policy=self.context.action_policy,
        )

    def _default_toolbar(self) -> ToolbarComponent:
        """构建当前页面内部使用的默认工具栏组件。"""
        return self.default_toolbar()

    def default_import_dropdown(self) -> ImportDropdownComponent:
        """创建当前页面默认导入下拉组件。"""
        if self.context is None or self.context.main_window is None:
            raise RuntimeError("Default import dropdown requires RpaContext with main_window")
        allowed_pids = {int(self.context.main_window["pid"])}
        return ImportDropdownComponent(
            self.hwnd,
            self.context.logger,
            self.context.config,
            allowed_pids,
            win32=self.win32,
            action_policy=self.context.action_policy,
        )

    def _default_import_dropdown(self) -> ImportDropdownComponent:
        """构建当前页面内部使用的默认导入下拉组件。"""
        return self.default_import_dropdown()

    def default_import_result_component(self) -> ImportResultComponent:
        """创建当前页面默认导入结果组件。"""
        if self.context is None or self.context.main_window is None:
            raise RuntimeError("Default import result requires RpaContext with main_window")
        allowed_pids = {int(self.context.main_window["pid"])}
        return ImportResultComponent(
            self.hwnd,
            self.context.logger,
            self.context.config,
            allowed_pids,
            win32=self.win32,
        )

    def _click_import_button(self) -> StepResult:
        """执行人员信息页面导入按钮点击的内部动作。"""
        return self.click_import_button()

    def _choose_import_file_option(self) -> StepResult:
        """执行人员信息页面选择导入文件菜单项的内部动作。"""
        return self.choose_import_file_option()

    def _click_submit_data(self) -> StepResult:
        """执行人员信息页面提交数据按钮点击的内部动作。"""
        return self.click_submit_data()

    def _choose_person_file(self, path: Path, dropdown_result: StepResult) -> StepResult | None:
        """执行人员信息文件选择框处理的内部动作。"""
        return self.choose_person_file(path, dropdown_result)

    def _read_import_result(self) -> StepResult:
        """执行人员信息导入结果读取的内部动作。"""
        return self.read_import_result()

    def _close_message_dialog_if_present(self) -> StepResult:
        """执行页面弹窗关闭的内部动作。"""
        return self.close_message_dialog_if_present()
