import argparse
import sys
import traceback
from typing import Any

from tax_rpa.cli.execution_mode import with_execution_mode
from tax_rpa.cli.windows_admin import is_user_admin, relaunch_module_as_admin
from tax_rpa.config.person_import import PersonImportConfig, load_import_config
from tax_rpa.drivers.logger import RunLogger
from tax_rpa.testing.self_check_app import SelfCheckApp
from tax_rpa.workflows.combined_tax_workflow import CombinedTaxWorkflow
from tax_rpa.workflows.update_special_deduction_workflow import (
    UpdateSpecialDeductionWorkflow,
)


MODULE_NAME = "tax_rpa.cli.update_special_deduction"


def relaunch_as_admin(argv: list[str]) -> None:
    """以管理员权限重新启动当前命令。"""
    relaunch_module_as_admin(MODULE_NAME, argv)


def parse_args() -> argparse.Namespace:
    """解析命令行参数，返回入口函数使用的参数对象。"""
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

def run_workflow(
    config: PersonImportConfig,
    logger: RunLogger,
    self_check: bool,
    reset: bool = False,
) -> dict[str, Any]:
    """执行cli、更新专项扣除中的run工作流逻辑，供业务流程或相邻模块调用。"""
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
            lambda config, logger, **kwargs: UpdateSpecialDeductionWorkflow(
                config,
                logger,
                **kwargs,
            )
        ],
        name="update_special_deduction_entry_workflow",
    )
    result = workflow.run()
    if not result.ok:
        raise RuntimeError(result.error or result.status)
    return {"status": result.status, "workflow": result}


def main() -> None:
    """命令行入口，解析参数并触发对应业务流程。"""
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
