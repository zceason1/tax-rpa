from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class StepResult:
    """单个步骤的标准结果对象，记录状态、证据和副作用信息。"""
    ok: bool
    name: str
    status: str
    evidence: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    error_type: str | None = None
    error_code: str | None = None
    side_effect_started: bool = False
    side_effect_committed: bool = False
    retry_allowed: bool = False
    evidence_paths: list[str] = field(default_factory=list)
    ui_text: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class WorkflowResult:
    """工作流的标准结果对象，记录整体状态和步骤链路。"""
    ok: bool
    name: str
    status: str
    steps: list[StepResult] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    error_type: str | None = None
    error_code: str | None = None
    side_effect_started: bool = False
    side_effect_committed: bool = False
    retry_allowed: bool = False
