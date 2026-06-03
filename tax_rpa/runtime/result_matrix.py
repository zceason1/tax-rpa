from typing import Any

from tax_rpa.runtime.result import StepResult


UNKNOWN_STATUSES = {"unknown", "timeout"}


DEFAULT_ERROR_TYPES = {
    "personnel_import": "IMPORT_FAILED",
    "salary_income_import": "IMPORT_FAILED",
    "special_deduction_update": "BUSINESS_REJECTED",
    "prefill_deduction": "BUSINESS_REJECTED",
    "tax_calculation": "BUSINESS_REJECTED",
    "declaration_submission_readiness": "UI_ELEMENT_NOT_FOUND",
    "export_report": "EXPORT_ERROR",
}
DEFAULT_UNKNOWN_ERROR_CODES = {
    "personnel_import": "person_import_result_unknown",
    "salary_income_import": "salary_income_import_result_unknown",
    "special_deduction_update": "special_deduction_update_result_unknown",
    "prefill_deduction": "prefill_deduction_result_unknown",
    "tax_calculation": "tax_calculation_result_unknown",
    "declaration_submission_readiness": "declaration_submission_readiness_unknown",
    "export_report": "export_report_result_unknown",
}
DEFAULT_FAILURE_ERROR_CODES = {
    "personnel_import": "person_import_failed",
    "salary_income_import": "salary_income_import_failed",
    "special_deduction_update": "special_deduction_update_failed",
    "prefill_deduction": "prefill_deduction_failed",
    "tax_calculation": "tax_calculation_failed",
    "declaration_submission_readiness": "send_declaration_button_missing",
    "export_report": "export_report_failed",
}


def classify_step_result(matrix_step: str, result: StepResult) -> dict[str, Any]:
    """把步骤结果归一化为结果矩阵记录。"""
    outcome = _outcome(result)
    error_type = result.error_type
    error_code = result.error_code
    if outcome == "unknown":
        error_type = error_type or "UNKNOWN_RESULT"
        error_code = error_code or DEFAULT_UNKNOWN_ERROR_CODES.get(
            matrix_step,
            "result_unknown",
        )
    elif outcome == "blocked":
        error_type = error_type or "BLOCKED_BY_UNEXPECTED_DIALOG"
        error_code = error_code or "unexpected_dialog"
    elif outcome == "failure":
        error_type = error_type or DEFAULT_ERROR_TYPES.get(matrix_step)
        error_code = error_code or DEFAULT_FAILURE_ERROR_CODES.get(
            matrix_step,
            "result_failed",
        )

    return {
        "matrix_step": matrix_step,
        "outcome": outcome,
        "status": result.status,
        "error_type": error_type,
        "error_code": error_code,
        "side_effect_started": result.side_effect_started,
        "side_effect_committed": result.side_effect_committed,
        "retry_allowed": result.retry_allowed,
        "ui_text": result.ui_text,
        "evidence_paths": result.evidence_paths,
    }


def _outcome(result: StepResult) -> str:
    """根据步骤状态和业务标记计算统一结果分类。"""
    if result.ok:
        return "success"
    if result.error_type == "BLOCKED_BY_UNEXPECTED_DIALOG" or result.status == "blocked":
        return "blocked"
    if result.error_type == "UNKNOWN_RESULT" or result.status in UNKNOWN_STATUSES:
        return "unknown"
    return "failure"
