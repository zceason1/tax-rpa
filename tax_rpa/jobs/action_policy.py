import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from tax_rpa.runtime.result import StepResult
from tax_rpa.utils import normalize_text


RUN_MODES = {"inspect_only", "execute_no_send", "submit"}
READ_ONLY_ACTION_TYPES = {"navigation", "locate", "read_only_click"}
SIDE_EFFECT_ACTION_TYPES = {
    "data_change",
    "file_submit",
    "dialog_confirm",
    "import",
    "update",
    "prefill",
    "calculate",
    "export",
}
HIGH_RISK_LABELS = {
    "发送申报",
    "提交申报",
    "报送",
    "发送",
    "鍙戦€佺敵鎶?",
    "鎶ラ€?",
}


@dataclass(frozen=True)
class ActionDecision:
    allowed: bool
    label: str
    action_type: str
    decision: str
    error_type: str | None = None
    error_code: str | None = None
    message: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_step_result(self, name: str) -> StepResult:
        return StepResult(
            ok=self.allowed,
            name=name,
            status="allowed" if self.allowed else "denied",
            evidence={"action_policy": self.evidence},
            error=self.message,
            error_type=self.error_type,
            error_code=self.error_code,
        )


class ActionDeniedError(RuntimeError):
    def __init__(self, decision: ActionDecision) -> None:
        super().__init__(decision.message or "Action denied")
        self.decision = decision


@dataclass(frozen=True)
class ActionAuditLogger:
    path: Path

    def log(self, event: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(_to_jsonable(event), ensure_ascii=False) + "\n")


@dataclass(frozen=True)
class ActionPolicy:
    run_mode: str
    job_id: str | None = None
    audit_logger: ActionAuditLogger | None = None

    def __post_init__(self) -> None:
        if self.run_mode not in RUN_MODES:
            raise ValueError(f"Unsupported run_mode: {self.run_mode}")

    def before_click(
        self,
        label: str,
        context: dict[str, Any] | None = None,
        *,
        action_type: str = "data_change",
        permit: Any | None = None,
    ) -> ActionDecision:
        return self.before_action(
            label=label,
            action_type=action_type,
            context=context,
            permit=permit,
        )

    def before_action(
        self,
        *,
        label: str,
        action_type: str,
        context: dict[str, Any] | None = None,
        permit: Any | None = None,
    ) -> ActionDecision:
        context = context or {}
        if _is_high_risk_label(label):
            decision = self._decide_high_risk(label, action_type, context, permit)
            self._audit(decision, context)
            return decision

        if action_type in READ_ONLY_ACTION_TYPES:
            return self._allowed(label, action_type, context)

        if action_type in SIDE_EFFECT_ACTION_TYPES:
            if self.run_mode == "inspect_only":
                decision = ActionDecision(
                    allowed=False,
                    label=label,
                    action_type=action_type,
                    decision="denied",
                    error_type="ACTION_DENIED",
                    error_code="run_mode_denied",
                    message=f"Action type {action_type} is denied in inspect_only mode",
                    evidence=self._evidence(label, action_type, context),
                )
                self._audit(decision, context)
                return decision
            return self._allowed(label, action_type, context)

        decision = ActionDecision(
            allowed=False,
            label=label,
            action_type=action_type,
            decision="denied",
            error_type="ACTION_DENIED",
            error_code="unknown_action_type",
            message=f"Unknown action type: {action_type}",
            evidence=self._evidence(label, action_type, context),
        )
        self._audit(decision, context)
        return decision

    def require_allowed(
        self,
        *,
        label: str,
        action_type: str,
        context: dict[str, Any] | None = None,
        permit: Any | None = None,
    ) -> ActionDecision:
        decision = self.before_action(
            label=label,
            action_type=action_type,
            context=context,
            permit=permit,
        )
        if not decision.allowed:
            raise ActionDeniedError(decision)
        return decision

    def _decide_high_risk(
        self,
        label: str,
        action_type: str,
        context: dict[str, Any],
        permit: Any | None,
    ) -> ActionDecision:
        if permit is not None:
            allowed = _consume_permit(permit, label=label, context=context)
            if allowed:
                return self._allowed(label, action_type, context, permit_id=getattr(permit, "permit_id", None))

        return ActionDecision(
            allowed=False,
            label=label,
            action_type=action_type,
            decision="denied",
            error_type="SUBMIT_NOT_AUTHORIZED",
            error_code="submit_not_authorized",
            message="High-risk submit action requires a valid one-time permit",
            evidence=self._evidence(label, action_type, context),
        )

    def _allowed(
        self,
        label: str,
        action_type: str,
        context: dict[str, Any],
        permit_id: str | None = None,
    ) -> ActionDecision:
        evidence = self._evidence(label, action_type, context)
        if permit_id is not None:
            evidence["permit_id"] = permit_id
        return ActionDecision(
            allowed=True,
            label=label,
            action_type=action_type,
            decision="allowed",
            evidence=evidence,
        )

    def _evidence(
        self,
        label: str,
        action_type: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "run_mode": self.run_mode,
            "label": label,
            "action_type": action_type,
            "step_name": context.get("step_name"),
            "high_risk": _is_high_risk_label(label),
        }

    def _audit(self, decision: ActionDecision, context: dict[str, Any]) -> None:
        if self.audit_logger is None:
            return
        event = {
            "time": datetime.now().astimezone().isoformat(timespec="seconds"),
            "job_id": self.job_id,
            "run_mode": self.run_mode,
            "label": decision.label,
            "action_type": decision.action_type,
            "step_name": context.get("step_name"),
            "decision": decision.decision,
            "error_type": decision.error_type,
            "error_code": decision.error_code,
            "message": decision.message,
        }
        self.audit_logger.log(event)


def _is_high_risk_label(label: str) -> bool:
    normalized = normalize_text(label)
    return normalized in {normalize_text(item) for item in HIGH_RISK_LABELS}


def _consume_permit(permit: Any, *, label: str, context: dict[str, Any]) -> bool:
    consume = getattr(permit, "consume", None)
    if callable(consume):
        return bool(
            consume(
                label=label,
                job_id=context.get("job_id"),
                step_name=context.get("step_name"),
            )
        )
    return False


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, Path):
        return value.as_posix()
    return value
