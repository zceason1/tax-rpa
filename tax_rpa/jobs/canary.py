import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


Probe = Callable[["CanaryTarget"], dict[str, Any]]


@dataclass(frozen=True)
class CanaryTarget:
    target_id: str
    label: str
    target_type: str
    owner_module: str


@dataclass(frozen=True)
class CanaryRunResult:
    passed: bool
    record_path: str
    maintenance_ticket_path: str | None = None


@dataclass(frozen=True)
class CanaryRunner:
    artifacts_root: Path = Path("artifacts")
    timestamp: str | None = None
    tax_client_version_reader: Callable[[], str] | None = None
    probe: Probe | None = None

    def run(
        self,
        *,
        run_mode: str,
        targets: list[CanaryTarget],
    ) -> CanaryRunResult:
        timestamp = self.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
        canary_dir = self.artifacts_root / "canary" / timestamp
        canary_dir.mkdir(parents=True, exist_ok=True)
        tax_client_version = _read_tax_client_version(self.tax_client_version_reader)
        target_results = [self._probe_target(target) for target in targets]
        passed = all(item["found"] for item in target_results)
        record = {
            "schema_version": 1,
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "run_mode": run_mode,
            "tax_client_version": tax_client_version,
            "passed": passed,
            "submit_clicked": False,
            "targets": target_results,
            "review": {"status": "pending"},
        }
        record_path = _write_json(canary_dir / "canary_record.json", record)
        ticket_path: str | None = None
        if not passed:
            failed_targets = [
                {
                    "target_id": item["target_id"],
                    "label": item["label"],
                    "target_type": item["target_type"],
                    "suggested_element_module": item["owner_module"],
                    "score": item.get("score"),
                    "ocr_text": item.get("ocr_text"),
                }
                for item in target_results
                if not item["found"]
            ]
            ticket_path = _write_json(
                canary_dir / "maintenance_ticket.json",
                {
                    "schema_version": 1,
                    "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                    "run_mode": run_mode,
                    "tax_client_version": tax_client_version,
                    "failed_targets": failed_targets,
                },
            )
        return CanaryRunResult(
            passed=passed,
            record_path=record_path.relative_to(self.artifacts_root).as_posix(),
            maintenance_ticket_path=ticket_path.relative_to(self.artifacts_root).as_posix()
            if ticket_path
            else None,
        )

    def _probe_target(self, target: CanaryTarget) -> dict[str, Any]:
        probe = self.probe or _default_probe
        result = probe(target)
        return {
            "target_id": target.target_id,
            "label": target.label,
            "target_type": target.target_type,
            "owner_module": target.owner_module,
            "found": bool(result.get("found")),
            "score": result.get("score"),
            "ocr_text": result.get("ocr_text"),
            "screenshot_path": result.get("screenshot_path"),
            "ocr_json_path": result.get("ocr_json_path"),
        }


def _read_tax_client_version(reader: Callable[[], str] | None) -> str:
    if reader is None:
        return "unknown"
    try:
        value = reader()
    except Exception:
        return "unknown"
    text = str(value).strip() if value is not None else ""
    return text or "unknown"


def _default_probe(_target: CanaryTarget) -> dict[str, Any]:
    return {"found": False, "score": None, "ocr_text": ""}


def _write_json(path: Path, data: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp_path.replace(path)
    return path
