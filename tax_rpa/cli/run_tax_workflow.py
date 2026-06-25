import argparse
import sys
import traceback
from typing import Any

from tax_rpa.cli.execution_mode import with_execution_mode
from tax_rpa.cli.windows_admin import is_user_admin, relaunch_module_as_admin
from tax_rpa.testing.self_check_app import SelfCheckApp
from tax_rpa.config.person_import import PersonImportConfig, load_import_config
from tax_rpa.drivers.logger import RunLogger
from tax_rpa.workflows.combined_tax_workflow import CombinedTaxWorkflow
from tax_rpa.workflows.import_person_info_workflow import ImportPersonInfoWorkflow
from tax_rpa.workflows.import_salary_income_workflow import ImportSalaryIncomeWorkflow
from tax_rpa.workflows.update_special_deduction_workflow import (
    UpdateSpecialDeductionWorkflow,
)


MODULE_NAME = "tax_rpa.cli.run_tax_workflow"


class WorkflowExecutionError(RuntimeError):
    """工作流执行错误异常，表示cli、run税务工作流中的特定错误场景。"""
    def __init__(self, result: Any) -> None:
        """初始化工作流执行错误实例，保存依赖、配置和运行上下文。"""
        super().__init__(result.error or result.status)
        self.result = result


def failure_payload(exc: Exception) -> dict[str, Any]:
    """执行cli、run税务工作流中的failure载荷逻辑，供业务流程或相邻模块调用。"""
    payload: dict[str, Any] = {
        "error": str(exc),
        "traceback": traceback.format_exc(),
    }
    if isinstance(exc, WorkflowExecutionError):
        result = exc.result
        payload.update(
            {
                "status": result.status,
                "error_type": result.error_type,
                "error_code": result.error_code,
                "evidence": result.evidence,
            }
        )
    return payload


def relaunch_as_admin(argv: list[str]) -> None:
    """以管理员权限重新启动当前命令。"""
    relaunch_module_as_admin(MODULE_NAME, argv)


def parse_args() -> argparse.Namespace:
    """解析命令行参数，返回入口函数使用的参数对象。"""
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
    """执行cli、run税务工作流中的run工作流逻辑，供业务流程或相邻模块调用。"""
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
            lambda config, logger, **kwargs: ImportPersonInfoWorkflow(config, logger, **kwargs),
            lambda config, logger, **kwargs: UpdateSpecialDeductionWorkflow(config, logger, **kwargs),
            lambda config, logger, **kwargs: ImportSalaryIncomeWorkflow(config, logger, **kwargs),
        ],
    )
    result = workflow.run()
    if not result.ok:
        raise WorkflowExecutionError(result)
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
        logger.write_json("failed.json", failure_payload(exc))
        raise


if __name__ == "__main__":
    main()
