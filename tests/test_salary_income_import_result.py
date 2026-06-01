import unittest
from types import SimpleNamespace

from tax_rpa.pages.comprehensive_income.components.import_result import (
    SalaryIncomeImportResultComponent,
)
from tax_rpa.pages.comprehensive_income.elements.import_result import (
    classify_salary_income_import_result,
)
from tax_rpa.pages.comprehensive_income.page import ComprehensiveIncomePage
from tax_rpa.runtime.result import StepResult


class FakeLogger:
    def screenshot(self, *_args, **_kwargs):
        return "screenshot.png"

    def log(self, *_args, **_kwargs):
        pass


class FixedSalaryImportResultComponent(SalaryIncomeImportResultComponent):
    def __init__(self, status):
        super().__init__(
            hwnd=100,
            logger=FakeLogger(),
            config=SimpleNamespace(dry_run=False, result_timeout_seconds=1),
            allowed_pids={1},
        )
        self.fixed_status = status

    def wait_for_import_result(self):
        return {"status": self.fixed_status, "source": "test"}


class SalaryIncomeImportResultTests(unittest.TestCase):
    def test_classify_success(self):
        self.assertEqual(
            classify_salary_income_import_result(["工资薪金导入成功"]),
            "success",
        )

    def test_classify_failed(self):
        self.assertEqual(
            classify_salary_income_import_result(["导入失败", "金额格式错误"]),
            "failed",
        )

    def test_classify_unknown(self):
        self.assertEqual(
            classify_salary_income_import_result(["请选择导入文件"]),
            "unknown",
        )

    def test_unknown_result_is_not_ok(self):
        result = FixedSalaryImportResultComponent("unknown").read_result()

        self.assertFalse(result.ok)
        self.assertEqual(result.status, "unknown")
        self.assertEqual(result.error_type, "UNKNOWN_RESULT")
        self.assertEqual(result.error_code, "salary_income_import_result_unknown")

    def test_page_uses_injected_salary_import_result_reader(self):
        expected = StepResult(
            ok=True,
            name="salary_income.wait_import_result",
            status="success",
        )
        page = ComprehensiveIncomePage(
            context=None,
            hwnd=100,
            salary_import_result_reader=lambda: expected,
        )

        self.assertIs(page.read_salary_income_import_result(), expected)


if __name__ == "__main__":
    unittest.main()
