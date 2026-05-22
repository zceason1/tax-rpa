import argparse
import ctypes
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Any

from tax_rpa.cli.execution_mode import with_execution_mode
from tax_rpa.config.person_import import PersonImportConfig, load_import_config
from tax_rpa.drivers.logger import RunLogger
from tax_rpa.runtime.result import StepResult
from tax_rpa.workflows.combined_tax_workflow import CombinedTaxWorkflow
from tax_rpa.workflows.update_special_deduction_workflow import (
    UpdateSpecialDeductionWorkflow,
)


MODULE_NAME = "tax_rpa.cli.update_special_deduction"
shell32 = ctypes.windll.shell32


def is_user_admin() -> bool:
    try:
        return bool(shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin(argv: list[str]) -> None:
    params = subprocess.list2cmdline(["-m", MODULE_NAME, *argv])
    result = shell32.ShellExecuteW(
        None,
        "runas",
        sys.executable,
        params,
        str(Path.cwd()),
        1,
    )
    if result <= 32:
        raise RuntimeError(f"Failed to relaunch as administrator. ShellExecuteW={result}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Open special deduction information collection and run download update for all persons."
    )
    parser.add_argument(
        "--config",
        default="config/person_import.json",
        help="Path to the JSON config.",
    )
    parser.add_argument(
        "--submit",
        action="store_true",
        help="Allow real clicks. Without this flag the workflow runs in debug dry-run mode.",
    )
    parser.add_argument(
        "--self-check",
        action="store_true",
        help="Run workflow composition with fake app/page objects.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Terminate any running client process before launching and waiting for login.",
    )
    parser.add_argument(
        "--no-self-elevate",
        action="store_true",
        help="Do not relaunch this command as administrator when not elevated.",
    )
    return parser.parse_args()


class SelfCheckApp:
    def __init__(self, _config: PersonImportConfig, _logger: Any) -> None:
        pass

    def start_if_needed(self) -> StepResult:
        return StepResult(ok=True, name="self_check.start_if_needed", status="self_check_start")

    def wait_for_login(self) -> StepResult:
        return StepResult(ok=True, name="self_check.wait_for_login", status="self_check_login")

    def reset(self) -> StepResult:
        return StepResult(ok=True, name="self_check.reset", status="self_check_reset")

    def shell(self):
        return SelfCheckShell()


class SelfCheckShell:
    def open_special_deduction_page(self):
        return SelfCheckSpecialDeductionPage()


class SelfCheckSpecialDeductionPage:
    def step(self, _name: str, **_data: Any):
        from contextlib import nullcontext

        return nullcontext()

    def click_download_update(self) -> StepResult:
        return StepResult(ok=True, name="self_check.click_download_update", status="dry_run")

    def click_all_persons(self) -> StepResult:
        return StepResult(ok=True, name="self_check.click_all_persons", status="dry_run")


def run_workflow(
    config: PersonImportConfig,
    logger: RunLogger,
    self_check: bool,
    reset: bool = False,
) -> dict[str, Any]:
    app_factory = (
        (lambda config, logger: SelfCheckApp(config, logger))
        if self_check
        else None
    )
    workflow = CombinedTaxWorkflow(
        config=config,
        logger=logger,
        reset=reset,
        app_factory=app_factory,
        workflow_factories=[lambda config, logger: UpdateSpecialDeductionWorkflow(config, logger)],
        name="update_special_deduction_entry_workflow",
    )
    result = workflow.run()
    if not result.ok:
        raise RuntimeError(result.error or result.status)
    return {"status": result.status, "workflow": result}


def main() -> None:
    args = parse_args()
    if not args.no_self_elevate and not is_user_admin():
        relaunch_as_admin(sys.argv[1:])
        print("已请求管理员权限运行，请在 UAC 弹窗中确认。")
        return

    logger = RunLogger()
    try:
        config = with_execution_mode(load_import_config(args.config), submit=args.submit)
        summary = run_workflow(config, logger, self_check=args.self_check, reset=args.reset)
        summary_path = logger.write_json("update_special_deduction_summary.json", summary)
        logger.log("done", summary["status"], summary=summary_path)
        print(summary_path)
    except Exception as exc:
        logger.log("run", "failed", error=str(exc), traceback=traceback.format_exc())
        logger.write_json("failed.json", {"error": str(exc), "traceback": traceback.format_exc()})
        raise


__all__ = ["with_execution_mode"]


if __name__ == "__main__":
    main()
