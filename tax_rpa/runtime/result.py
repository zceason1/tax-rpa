from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class StepResult:
    ok: bool
    name: str
    status: str
    evidence: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class WorkflowResult:
    ok: bool
    name: str
    status: str
    steps: list[StepResult] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
