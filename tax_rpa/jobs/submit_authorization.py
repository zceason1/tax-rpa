import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from tax_rpa.jobs.manifest import JobManifest
from tax_rpa.runtime.action_policy import ActionAuditLogger
from tax_rpa.runtime.text import normalize_text


@dataclass
class SubmitPermit:
    """提交许可，封装作业、提交授权相关状态和行为。"""
    job_id: str
    step_name: str
    label: str
    expires_at: str
    permit_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    consumed: bool = False

    def consume(self, *, label: str, job_id: str | None, step_name: str | None) -> bool:
        """消费一次性提交许可，防止同一许可被重复用于高风险动作。"""
        if self.consumed:
            return False
        if job_id != self.job_id:
            return False
        if step_name != self.step_name:
            return False
        if normalize_text(label) != normalize_text(self.label):
            return False
        if datetime.now().astimezone() > datetime.fromisoformat(self.expires_at):
            return False
        self.consumed = True
        return True


@dataclass(frozen=True)
class SubmitAuthorizationResult:
    """提交授权结果结果对象，承载执行状态、证据和后续判断所需字段。"""
    allowed: bool
    error_type: str | None = None
    error_code: str | None = None
    message: str | None = None
    missing_gates: list[str] = field(default_factory=list)
    permit: SubmitPermit | None = None
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SubmitAuthorization:
    """提交授权服务，负责合并运行模式、门禁和一次性许可。"""
    production_switch_path: Path = Path("config/production_submit_enabled.json")
    cli_submit: bool = False
    windows_user: str | None = None
    audit_logger: ActionAuditLogger | None = None
    permit_ttl_seconds: int = 300
    production_gate: Any | None = None

    def authorize(
        self,
        manifest: JobManifest,
        *,
        step_name: str,
        label: str,
    ) -> SubmitAuthorizationResult:
        """综合运行模式、生产门禁和一次性许可，判断是否允许真实提交。"""
        switch = self._read_production_switch()
        missing_gates: list[str] = []

        if manifest.run_mode != "submit":
            missing_gates.append("manifest.run_mode")
        if not manifest.submit_enabled:
            missing_gates.append("manifest.submit_enabled")
        if not self.cli_submit:
            missing_gates.append("cli_submit")
        if not switch["enabled"]:
            missing_gates.append("production_switch")
        production_gate_result = None
        if self.production_gate is not None:
            production_gate_result = self.production_gate.evaluate()
            if not production_gate_result.allowed:
                missing_gates.append("production_gate")

        evidence = {
            "job_id": manifest.job_id,
            "run_mode": manifest.run_mode,
            "submit_enabled": manifest.submit_enabled,
            "cli_submit": self.cli_submit,
            "production_switch": switch,
            "windows_user": self.windows_user,
            "step_name": step_name,
            "label": label,
            "production_gate": _gate_to_dict(production_gate_result),
        }

        if missing_gates:
            result = SubmitAuthorizationResult(
                allowed=False,
                error_type="SUBMIT_NOT_AUTHORIZED",
                error_code="submit_not_authorized",
                message="Submit authorization gates are not all satisfied",
                missing_gates=missing_gates,
                evidence=evidence,
            )
            self._audit(result, manifest, step_name, label)
            return result

        permit = SubmitPermit(
            job_id=manifest.job_id,
            step_name=step_name,
            label=label,
            expires_at=(
                datetime.now().astimezone() + timedelta(seconds=self.permit_ttl_seconds)
            ).isoformat(timespec="seconds"),
        )
        result = SubmitAuthorizationResult(
            allowed=True,
            permit=permit,
            evidence={**evidence, "permit_id": permit.permit_id},
        )
        self._audit(result, manifest, step_name, label)
        return result

    def _read_production_switch(self) -> dict[str, Any]:
        """读取生产提交开关配置。"""
        try:
            data = json.loads(self.production_switch_path.read_text(encoding="utf-8"))
        except Exception:
            return {"enabled": False, "valid": False, "reason": "missing_or_unreadable"}

        if not isinstance(data, dict):
            return {"enabled": False, "valid": False, "reason": "not_object"}
        if data.get("enabled") is not True:
            return {"enabled": False, "valid": True, "reason": "disabled"}
        approved_by = data.get("approved_by")
        approved_at = data.get("approved_at")
        if not isinstance(approved_by, str) or not approved_by.strip():
            return {"enabled": False, "valid": False, "reason": "missing_approved_by"}
        if not isinstance(approved_at, str) or not approved_at.strip():
            return {"enabled": False, "valid": False, "reason": "missing_approved_at"}
        return {
            "enabled": True,
            "valid": True,
            "approved_by": approved_by.strip(),
            "approved_at": approved_at.strip(),
        }

    def _audit(
        self,
        result: SubmitAuthorizationResult,
        manifest: JobManifest,
        step_name: str,
        label: str,
    ) -> None:
        """把动作策略决策写入审计日志。"""
        if self.audit_logger is None:
            return
        self.audit_logger.log(
            {
                "time": datetime.now().astimezone().isoformat(timespec="seconds"),
                "job_id": manifest.job_id,
                "run_mode": manifest.run_mode,
                "label": label,
                "action_type": "submit_authorization",
                "step_name": step_name,
                "decision": "allowed" if result.allowed else "denied",
                "error_type": result.error_type,
                "error_code": result.error_code,
                "message": result.message,
                "missing_gates": result.missing_gates,
                "permit_id": result.permit.permit_id if result.permit else None,
                "windows_user": self.windows_user,
            }
        )


def _gate_to_dict(result: Any | None) -> dict[str, Any] | None:
    """执行作业、提交授权中的内部辅助逻辑：门禁todict。"""
    if result is None:
        return None
    to_dict = getattr(result, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    if isinstance(result, dict):
        return result
    return {"allowed": bool(getattr(result, "allowed", False))}
