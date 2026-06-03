from contextlib import nullcontext
from pathlib import Path
from typing import Any

from tax_rpa.config.person_import import PersonImportConfig
from tax_rpa.runtime.result import StepResult


class SelfCheckApp:
    """假税务客户端，用于在不启动真实扣缴端时验证工作流编排。"""

    def __init__(self, _config: PersonImportConfig, _logger: Any) -> None:
        """初始化假客户端；参数只用于保持和真实 TaxClientApp 相同的工厂签名。"""

    def start_if_needed(self) -> StepResult:
        """模拟客户端启动成功，让生命周期工作流继续执行。"""
        return StepResult(ok=True, name="self_check.start_if_needed", status="self_check_start")

    def wait_for_login(self) -> StepResult:
        """模拟登录完成，避免自检依赖真实账号、密码或桌面窗口。"""
        return StepResult(ok=True, name="self_check.wait_for_login", status="self_check_login")

    def reset(self) -> StepResult:
        """模拟客户端重置成功，用于覆盖带 --reset 的工作流路径。"""
        return StepResult(ok=True, name="self_check.reset", status="self_check_reset")

    def shell(self) -> "SelfCheckShell":
        """返回假主界面对象，供业务工作流打开各页面。"""
        return SelfCheckShell()


class SelfCheckShell:
    """假主界面，按真实 MainShell 的页面打开接口返回假页面对象。"""

    def open_person_info_page(self) -> "SelfCheckPersonInfoPage":
        """返回假人员信息采集页面。"""
        return SelfCheckPersonInfoPage()

    def open_special_deduction_page(self) -> "SelfCheckSpecialDeductionPage":
        """返回假专项附加扣除页面。"""
        return SelfCheckSpecialDeductionPage()

    def open_comprehensive_income_page(self) -> "SelfCheckComprehensiveIncomePage":
        """返回假综合所得申报页面。"""
        return SelfCheckComprehensiveIncomePage()


class SelfCheckPersonInfoPage:
    """假人员信息页面，覆盖人员 Excel 导入工作流需要的页面动作。"""

    def step(self, _name: str, **_data: Any):
        """返回空步骤上下文，让页面步骤代码可以照常使用 with page.step(...)。"""
        return nullcontext()

    def close_message_dialog_if_present(self):
        """模拟当前没有需要关闭的阻塞弹窗。"""
        return StepResult(ok=True, name="self_check.close_message_dialog", status="none")

    def click_import_button(self):
        """模拟点击人员信息页面的导入按钮。"""
        return StepResult(ok=True, name="self_check.click_import_button", status="clicked")

    def choose_import_file_option(self):
        """模拟从导入菜单选择导入文件，并返回一个假文件对话框句柄。"""
        return StepResult(
            ok=True,
            name="self_check.choose_import_file_option",
            status="selected",
            evidence={"dialog": {"hwnd": 1}},
        )

    def choose_person_file(self, path: Path, _dropdown_result: StepResult):
        """模拟选择人员信息 Excel 文件，不触发真实文件对话框。"""
        return StepResult(
            ok=True,
            name="self_check.choose_person_file",
            status="dry_run",
            evidence={"file_path": str(path)},
        )

    def read_import_result(self):
        """模拟人员信息导入成功。"""
        return StepResult(ok=True, name="self_check.wait_import_result", status="success")


class SelfCheckSpecialDeductionPage:
    """假专项附加扣除页面，覆盖下载更新全部人员的页面动作。"""

    def step(self, _name: str, **_data: Any):
        """返回空步骤上下文，让页面步骤代码可以照常使用 with page.step(...)。"""
        return nullcontext()

    def click_download_update(self):
        """模拟点击下载更新按钮。"""
        return StepResult(ok=True, name="self_check.click_download_update", status="dry_run")

    def click_all_persons(self):
        """模拟选择全部人员更新范围。"""
        return StepResult(ok=True, name="self_check.click_all_persons", status="dry_run")


class SelfCheckComprehensiveIncomePage:
    """假综合所得页面，覆盖工资导入、预填、算税、报送检查和导出流程。"""

    def step(self, _name: str, **_data: Any):
        """返回空步骤上下文，让页面步骤代码可以照常使用 with page.step(...)。"""
        return nullcontext()

    def click_salary_income_row(self):
        """模拟点击工资薪金所得行。"""
        return StepResult(ok=True, name="self_check.click_salary_income_row", status="dry_run")

    def click_salary_income_fill(self):
        """模拟点击工资薪金填写入口。"""
        return StepResult(ok=True, name="self_check.click_salary_income_fill", status="dry_run")

    def click_import_button(self):
        """模拟点击综合所得页面的导入按钮。"""
        return StepResult(ok=True, name="self_check.click_import_button", status="dry_run")

    def choose_import_data_option(self):
        """模拟选择工资薪金导入数据菜单项，并返回假文件对话框句柄。"""
        return StepResult(
            ok=True,
            name="self_check.choose_import_data_option",
            status="dry_run",
            evidence={"dialog": {"hwnd": 1}},
        )

    def choose_salary_income_file(self, path: Path, _import_option_result: StepResult):
        """模拟选择工资薪金 Excel 文件，不触发真实文件对话框。"""
        return StepResult(
            ok=True,
            name="self_check.choose_salary_income_file",
            status="dry_run",
            evidence={"file_path": str(path)},
        )

    def read_salary_income_import_result(self):
        """模拟工资薪金导入成功。"""
        return StepResult(
            ok=True,
            name="self_check.wait_salary_income_import_result",
            status="success",
        )

    def click_prefill_deduction(self):
        """模拟点击专项附加扣除预填入口。"""
        return StepResult(ok=True, name="self_check.click_prefill_deduction", status="clicked")

    def read_prefill_confirmation_dialog(self):
        """模拟读取到可继续的预填确认弹窗。"""
        return StepResult(
            ok=True,
            name="self_check.read_prefill_confirmation_dialog",
            status="ready",
            ui_text=["self_check_prefill_confirmation"],
        )

    def confirm_prefill_options(self, *, allow_skip_personal_pension: bool):
        """模拟确认预填选项，并保留个人养老金跳过配置证据。"""
        return StepResult(
            ok=True,
            name="self_check.confirm_prefill_options",
            status="confirmed",
            evidence={"allow_skip_personal_pension": allow_skip_personal_pension},
        )

    def read_prefill_result(self):
        """模拟预填成功。"""
        return StepResult(ok=True, name="self_check.read_prefill_result", status="success")

    def click_tax_calculation_tab(self):
        """模拟打开税款计算页签。"""
        return StepResult(ok=True, name="self_check.click_tax_calculation_tab", status="clicked")

    def read_tax_calculation_popup(self):
        """模拟没有出现阻塞税款计算的异常弹窗。"""
        return StepResult(ok=True, name="self_check.read_tax_calculation_popup", status="no_popup")

    def confirm_tax_calculation_popup(self):
        """模拟确认税款计算弹窗。"""
        return StepResult(
            ok=True,
            name="self_check.confirm_tax_calculation_popup",
            status="confirmed",
        )

    def read_tax_calculation_result(self):
        """模拟税款计算成功。"""
        return StepResult(ok=True, name="self_check.read_tax_calculation_result", status="success")

    def open_declaration_submission_page(self):
        """模拟打开申报表报送页面。"""
        return StepResult(
            ok=True,
            name="self_check.open_declaration_submission_page",
            status="ready",
        )

    def locate_send_declaration_button(self):
        """模拟定位到发送申报按钮，但不执行真实报送。"""
        return StepResult(
            ok=True,
            name="self_check.locate_send_declaration_button",
            status="ready_to_submit_not_sent",
        )

    def open_export_report_menu(self):
        """模拟打开导出申报表菜单。"""
        return StepResult(ok=True, name="self_check.open_export_report_menu", status="opened")

    def choose_standard_report_option(self):
        """模拟选择标准申报表导出选项。"""
        return StepResult(
            ok=True,
            name="self_check.choose_standard_report_option",
            status="selected",
        )

    def read_export_result(self, *, run_mode: str):
        """模拟导出结果；execute_no_send 下导出在报送前不可用也算可接受。"""
        if run_mode == "execute_no_send":
            return StepResult(
                ok=True,
                name="self_check.read_export_result",
                status="not_available_before_submit",
                evidence={"export_status": "not_available_before_submit"},
            )
        return StepResult(
            ok=True,
            name="self_check.read_export_result",
            status="exported",
            evidence={"export_status": "exported"},
        )

