import argparse
import ctypes
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Any

from tax_rpa.cli.execution_mode import with_execution_mode
from tax_rpa.cli.from_zero_import_person_info import SelfCheckApp
from tax_rpa.config.person_import import PersonImportConfig, load_import_config
from tax_rpa.drivers.logger import RunLogger
from tax_rpa.workflows.combined_tax_workflow import CombinedTaxWorkflow
from tax_rpa.workflows.import_person_info_workflow import ImportPersonInfoWorkflow
from tax_rpa.workflows.import_salary_income_workflow import ImportSalaryIncomeWorkflow
from tax_rpa.workflows.update_special_deduction_workflow import (
    UpdateSpecialDeductionWorkflow,
)


MODULE_NAME = "tax_rpa.cli.run_tax_workflow"
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
        description="Run the composed tax RPA workflow from app lifecycle through business steps."
    )
    parser.add_argument(
        "--config",
        default="config/person_import.json",
        help="Path to the JSON config.",
    )
    parser.add_argument(
        "--submit",
        action="store_true",
        help="Allow real submission actions. Without this flag the workflow runs in debug dry-run mode.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Terminate any running client process before launching and waiting for login.",
    )
    parser.add_argument(
        "--self-check",
        action="store_true",
        help="Run workflow composition with fake app/page objects.",
    )
    parser.add_argument(
        "--no-self-elevate",
        action="store_true",
        help="Do not relaunch this command as administrator when not elevated.",
    )
    return parser.parse_args()


def run_workflow(
    config: PersonImportConfig,
    logger: RunLogger,
    reset: bool = False,
    self_check: bool = False,
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
        workflow_factories=[
            lambda config, logger: ImportPersonInfoWorkflow(config, logger),
            lambda config, logger: UpdateSpecialDeductionWorkflow(config, logger),
            lambda config, logger: ImportSalaryIncomeWorkflow(config, logger),
        ],
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
        summary = run_workflow(
            config,
            logger,
            reset=args.reset,
            self_check=args.self_check,
        )
        summary_path = logger.write_json("tax_workflow_summary.json", summary)
        logger.log("done", summary["status"], summary=summary_path)
        print(summary_path)
    except Exception as exc:
        logger.log("run", "failed", error=str(exc), traceback=traceback.format_exc())
        logger.write_json("failed.json", {"error": str(exc), "traceback": traceback.format_exc()})
        raise


if __name__ == "__main__":
    main()
