import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ProductionGateResult:
    allowed: bool
    status: str
    missing_gates: list[str] = field(default_factory=list)
    error_type: str | None = None
    error_code: str | None = None
    message: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "status": self.status,
            "missing_gates": self.missing_gates,
            "error_type": self.error_type,
            "error_code": self.error_code,
            "message": self.message,
            "evidence": self.evidence,
        }


@dataclass(frozen=True)
class ProductionGate:
    checklist_path: Path = Path("config/submit_enablement_checklist.json")
    tax_client_version_reader: Callable[[], str] | None = None

    def evaluate(self) -> ProductionGateResult:
        try:
            checklist = json.loads(self.checklist_path.read_text(encoding="utf-8"))
        except Exception:
            return _denied(
                ["submit_enablement_checklist"],
                "Submit enablement checklist is missing or unreadable",
            )
        if not isinstance(checklist, dict):
            return _denied(["submit_enablement_checklist"], "Submit enablement checklist is invalid")

        missing_gates: list[str] = []
        evidence: dict[str, Any] = {"checklist_path": self.checklist_path.as_posix()}
        if checklist.get("schema_version") != 1:
            missing_gates.append("checklist_schema_version")
        if checklist.get("self_check_passed") is not True:
            missing_gates.append("self_check")
        if checklist.get("calibration_gate_passed") is not True:
            missing_gates.append("calibration_gate")
        if not _review_approved(checklist.get("review")):
            missing_gates.append("checklist_review")

        expected_version = _text_or_unknown(checklist.get("tax_client_version"))
        current_version = _read_version(self.tax_client_version_reader)
        evidence["expected_tax_client_version"] = expected_version
        evidence["current_tax_client_version"] = current_version
        if expected_version != current_version:
            missing_gates.append("tax_client_version")

        for field_name, expected_mode in (
            ("inspect_only_canary_record", "inspect_only"),
            ("execute_no_send_canary_record", "execute_no_send"),
        ):
            record_result = self._evaluate_canary_record(
                checklist.get(field_name),
                expected_mode=expected_mode,
                expected_version=expected_version,
            )
            evidence[field_name] = record_result
            if not record_result["passed"]:
                missing_gates.append(field_name)

        if missing_gates:
            return ProductionGateResult(
                allowed=False,
                status="blocked",
                missing_gates=missing_gates,
                error_type="SUBMIT_NOT_AUTHORIZED",
                error_code="production_gate_not_satisfied",
                message="Submit remains disabled until canary artifacts pass review",
                evidence=evidence,
            )

        return ProductionGateResult(
            allowed=True,
            status="passed",
            evidence=evidence,
        )

    def _evaluate_canary_record(
        self,
        raw_path: Any,
        *,
        expected_mode: str,
        expected_version: str,
    ) -> dict[str, Any]:
        if not isinstance(raw_path, str) or not raw_path.strip():
            return {"passed": False, "reason": "missing_path"}
        path = Path(raw_path)
        if not path.is_absolute():
            path = self.checklist_path.parent / path
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {"passed": False, "path": path.as_posix(), "reason": "unreadable"}
        if not isinstance(record, dict):
            return {"passed": False, "path": path.as_posix(), "reason": "not_object"}
        failures = []
        if record.get("run_mode") != expected_mode:
            failures.append("run_mode")
        if record.get("passed") is not True:
            failures.append("passed")
        if record.get("tax_client_version") != expected_version:
            failures.append("tax_client_version")
        if not _review_approved(record.get("review")):
            failures.append("review")
        return {
            "passed": not failures,
            "path": path.as_posix(),
            "failures": failures,
        }


def _denied(missing_gates: list[str], message: str) -> ProductionGateResult:
    return ProductionGateResult(
        allowed=False,
        status="blocked",
        missing_gates=missing_gates,
        error_type="SUBMIT_NOT_AUTHORIZED",
        error_code="production_gate_not_satisfied",
        message=message,
    )


def _review_approved(value: Any) -> bool:
    return isinstance(value, dict) and value.get("status") == "approved"


def _read_version(reader: Callable[[], str] | None) -> str:
    if reader is None:
        return "unknown"
    try:
        return _text_or_unknown(reader())
    except Exception:
        return "unknown"


def _text_or_unknown(value: Any) -> str:
    text = str(value).strip() if value is not None else ""
    return text or "unknown"
