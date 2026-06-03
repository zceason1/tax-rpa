import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


REQUIRED_EXECUTE_NO_SEND_STEPS = (
    "login",
    "personnel_import",
    "special_deduction_update",
    "salary_income_import",
    "prefill_deduction",
    "tax_calculation",
    "declaration_submission",
    "export_report",
)
REQUIRED_ELEMENT_FIELDS = {
    "page_name",
    "tax_client_version",
    "element_id",
    "ui_text",
    "aliases",
    "element_type",
    "region_hint",
    "unknown_behavior",
    "sample_screenshot",
    "sample_ocr_json",
    "min_score",
    "owner_module",
}


@dataclass(frozen=True)
class CalibrationGateResult:
    """校准门禁结果结果对象，承载执行状态、证据和后续判断所需字段。"""
    allowed: bool
    status: str
    missing_steps: list[str] = field(default_factory=list)
    missing_elements: list[str] = field(default_factory=list)
    invalid_records: list[str] = field(default_factory=list)
    error_type: str | None = None
    error_code: str | None = None
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """转换为普通字典，便于写入 JSON、日志或回调载荷。"""
        return {
            "allowed": self.allowed,
            "status": self.status,
            "missing_steps": self.missing_steps,
            "missing_elements": self.missing_elements,
            "invalid_records": self.invalid_records,
            "error_type": self.error_type,
            "error_code": self.error_code,
            "message": self.message,
        }


@dataclass(frozen=True)
class CalibrationGate:
    """校准门禁，封装作业、校准相关状态和行为。"""
    calibration_root: Path = Path("artifacts/calibration")

    def evaluate(
        self,
        *,
        run_mode: str,
        tax_client_version: str,
        real_client: bool,
    ) -> CalibrationGateResult:
        """评估生产门禁是否满足，返回允许或拒绝原因。"""
        if not real_client:
            return CalibrationGateResult(
                allowed=True,
                status="skipped_for_fake_driver",
            )

        missing_steps: list[str] = []
        invalid_records: list[str] = []
        for step_name in REQUIRED_EXECUTE_NO_SEND_STEPS:
            elements, error = self._read_elements(tax_client_version, step_name)
            if error == "missing":
                missing_steps.append(step_name)
            elif error:
                invalid_records.append(f"{step_name}:{error}")
            elif not elements:
                invalid_records.append(f"{step_name}:empty")

        missing_elements: list[str] = []
        if run_mode == "submit":
            elements, error = self._read_elements(
                tax_client_version,
                "declaration_submission",
            )
            if error == "missing":
                missing_steps.append("declaration_submission")
            elif error:
                invalid_records.append(f"declaration_submission:{error}")
            elif not _has_submit_result_texts(elements):
                missing_elements.append("declaration_submission.result_text")

        if missing_steps or missing_elements or invalid_records:
            return CalibrationGateResult(
                allowed=False,
                status="blocked",
                missing_steps=missing_steps,
                missing_elements=missing_elements,
                invalid_records=invalid_records,
                error_type="SUBMIT_NOT_AUTHORIZED",
                error_code="calibration_missing",
                message="Real-client run requires current calibration records",
            )

        return CalibrationGateResult(allowed=True, status="passed")

    def _read_elements(
        self,
        tax_client_version: str,
        step_name: str,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """读取元素定义，并处理缺失或异常情况。"""
        path = (
            self.calibration_root
            / tax_client_version
            / step_name
            / "element_calibration.json"
        )
        if not path.exists():
            return [], "missing"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return [], "unreadable"
        if not isinstance(data, list):
            return [], "not_list"
        for item in data:
            error = _validate_element(item, tax_client_version, step_name)
            if error:
                return [], error
        return data, None


def _validate_element(
    item: Any,
    tax_client_version: str,
    step_name: str,
) -> str | None:
    """执行作业、校准中的内部辅助逻辑：validateelement。"""
    if not isinstance(item, dict):
        return "element_not_object"
    missing = sorted(REQUIRED_ELEMENT_FIELDS - set(item))
    if missing:
        return f"missing_fields:{','.join(missing)}"
    if item.get("tax_client_version") != tax_client_version:
        return "version_mismatch"
    if item.get("page_name") != step_name:
        return "page_mismatch"
    if not isinstance(item.get("aliases"), list):
        return "aliases_not_list"
    if not isinstance(item.get("min_score"), (int, float)):
        return "min_score_not_numeric"
    return None


def _has_submit_result_texts(elements: list[dict[str, Any]]) -> bool:
    """执行作业、校准中的内部辅助逻辑：has提交结果texts。"""
    for element in elements:
        if element.get("element_id") != "declaration_submission.result_text":
            continue
        success_texts = element.get("success_texts")
        failure_texts = element.get("failure_texts")
        return bool(success_texts) and bool(failure_texts)
    return False
