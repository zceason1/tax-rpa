import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from tax_rpa.runtime.result import StepResult
from tax_rpa.runtime.text import normalize_text


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
    """动作策略判断结果，记录是否允许、原因和审计证据。"""
    allowed: bool
    label: str
    action_type: str
    decision: str
    error_type: str | None = None
    error_code: str | None = None
    message: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_step_result(self, name: str) -> StepResult:
        """把动作决策转换成步骤结果，便于工作流统一处理。"""
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
    """动作被策略拒绝时抛出的异常，携带拒绝决策。"""
    def __init__(self, decision: ActionDecision) -> None:
        """初始化动作拒绝结果错误实例，保存依赖、配置和运行上下文。"""
        super().__init__(decision.message or "Action denied")
        self.decision = decision


@dataclass(frozen=True)
class ActionAuditLogger:
    """动作审计日志写入器，负责把动作决策写入 JSONL。"""
    path: Path

    def log(self, event: dict[str, Any]) -> None:
        """写入日志事件，记录当前动作或状态。"""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(_to_jsonable(event), ensure_ascii=False) + "\n")


@dataclass(frozen=True)
class ActionPolicy:
    """运行时动作策略，统一判断点击、文件提交和高风险提交是否允许。"""
    run_mode: str
    job_id: str | None = None
    audit_logger: ActionAuditLogger | None = None

    def __post_init__(self) -> None:
        """在 dataclass 初始化后规范化字段，保证后续流程拿到一致的运行值。"""
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
        """在点击前根据标签、风险级别和上下文做动作授权判断。"""
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
        """在任意业务动作前做统一授权判断。"""
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
        """要求动作必须被允许，否则抛出拒绝异常。"""
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
        """对报送等高风险动作执行专门的提交授权判断。"""
        if permit is not None:
            allowed = _consume_permit(permit, label=label, context=context)
            if allowed:
                return self._allowed(
                    label,
                    action_type,
                    context,
                    permit_id=getattr(permit, "permit_id", None),
                )

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
        """构造允许动作的策略决策结果。"""
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
        """生成动作决策的审计证据。"""
        return {
            "job_id": self.job_id,
            "run_mode": self.run_mode,
            "label": label,
            "action_type": action_type,
            "step_name": context.get("step_name"),
            "high_risk": _is_high_risk_label(label),
        }

    def _audit(self, decision: ActionDecision, context: dict[str, Any]) -> None:
        """把动作策略决策写入审计日志。"""
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
    """判断内部条件是否匹配高风险标签。"""
    normalized = normalize_text(label)
    return normalized in {normalize_text(item) for item in HIGH_RISK_LABELS}


def _consume_permit(permit: Any, *, label: str, context: dict[str, Any]) -> bool:
    """执行运行时、动作策略中的内部辅助逻辑：consume许可。"""
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
    """把路径、数据类和嵌套对象转换为可 JSON 序列化结构。"""
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, Path):
        return value.as_posix()
    return value
