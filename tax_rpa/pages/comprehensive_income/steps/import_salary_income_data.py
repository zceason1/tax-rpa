from pathlib import Path
from typing import TYPE_CHECKING

from tax_rpa.runtime.result import StepResult

if TYPE_CHECKING:
    from tax_rpa.pages.comprehensive_income.page import ComprehensiveIncomePage


class ImportSalaryIncomeDataStep:
    def __init__(self, page: "ComprehensiveIncomePage") -> None:
        self.page = page

    def run(self, path: Path) -> StepResult:
        with self.page.step("点击导入按钮"):
            import_button_result = self.page.click_import_button()

        with self.page.step("选择导入数据"):
            import_option_result = self.page.choose_import_data_option()

        with self.page.step("选择工资薪金导入文件", file_path=str(path)):
            file_result = self.page.choose_salary_income_file(path, import_option_result)
            if file_result is None:
                if self._is_dry_run():
                    return StepResult(
                        ok=True,
                        name="comprehensive_income.import_salary_income_data",
                        status="debug_verified",
                        evidence={
                            "import_button": import_button_result,
                            "import_option": import_option_result,
                            "file_path": str(path),
                            "file_dialog": None,
                        },
                    )
                return StepResult(
                    ok=False,
                    name="comprehensive_income.import_salary_income_data",
                    status="file_dialog_missing",
                    evidence={
                        "import_button": import_button_result,
                        "import_option": import_option_result,
                    },
                    error="Import data file dialog was not opened",
                )

        if not file_result.ok:
            return StepResult(
                ok=False,
                name="comprehensive_income.import_salary_income_data",
                status=file_result.status,
                evidence={
                    "import_button": import_button_result,
                    "import_option": import_option_result,
                    "file_dialog": file_result,
                },
                error=file_result.error,
                error_type=file_result.error_type,
                error_code=file_result.error_code,
                side_effect_started=True,
                side_effect_committed=True,
                retry_allowed=False,
            )

        with self.page.step("wait_salary_income_import_result"):
            import_result = self.page.read_salary_income_import_result()

        return StepResult(
            ok=import_result.ok,
            name="comprehensive_income.import_salary_income_data",
            status=import_result.status,
            evidence={
                "import_button": import_button_result,
                "import_option": import_option_result,
                "file_dialog": file_result,
                "import_result": import_result,
            },
            error=import_result.error,
            error_type=import_result.error_type,
            error_code=import_result.error_code,
            side_effect_started=True,
            side_effect_committed=True,
            retry_allowed=False,
        )

    def _is_dry_run(self) -> bool:
        checker = getattr(self.page, "is_dry_run", None)
        if callable(checker):
            return bool(checker())
        return bool(getattr(self.page, "dry_run", False))
