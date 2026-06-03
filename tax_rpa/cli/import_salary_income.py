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
from tax_rpa.workflows.import_salary_income_workflow import ImportSalaryIncomeWorkflow


MODULE_NAME = "tax_rpa.cli.import_salary_income"
shell32 = ctypes.windll.shell32


def is_user_admin() -> bool:
    """判断当前进程是否具备管理员权限。"""
    try:
        return bool(shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin(argv: list[str]) -> None:
    """以管理员权限重新启动当前命令。"""
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
    """解析命令行参数，返回入口函数使用的参数对象。"""
    parser = argparse.ArgumentParser(
        description="Open comprehensive income declaration and import normal salary income data."
    )
    parser.add_argument(
        "--config",
        default="config/person_import.json",
        help="Path to the JSON config.",
    )
    parser.add_argument(
        "--submit",
        action="store_true",
        help="Submit the file dialog. Without this flag the workflow runs in debug dry-run mode.",
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
    """check客户端，封装cli、导入工资薪金收入相关状态和行为。"""
    def __init__(self, _config: PersonImportConfig, _logger: Any) -> None:
        """初始化check客户端实例，保存依赖、配置和运行上下文。"""
        pass

    def start_if_needed(self) -> StepResult:
        """在客户端未运行时启动客户端，已运行时直接复用。"""
        return StepResult(ok=True, name="self_check.start_if_needed", status="self_check_start")

    def wait_for_login(self) -> StepResult:
        """等待客户端完成登录；配置了自动登录时会尝试自动输入申报密码。"""
        return StepResult(ok=True, name="self_check.wait_for_login", status="self_check_login")

    def reset(self) -> StepResult:
        """重置税务客户端进程，清理旧窗口后准备重新启动。"""
        return StepResult(ok=True, name="self_check.reset", status="self_check_reset")

    def shell(self):
        """返回主界面门面对象，供工作流继续打开业务页面。"""
        return SelfCheckShell()


class SelfCheckShell:
    """check主界面，封装cli、导入工资薪金收入相关状态和行为。"""
    def open_comprehensive_income_page(self):
        """打开综合所得收入页面，并返回后续流程需要的对象或结果。"""
        return SelfCheckComprehensiveIncomePage()


class SelfCheckComprehensiveIncomePage:
    """check综合所得收入页面，封装cli、导入工资薪金收入相关状态和行为。"""
    def step(self, _name: str, **_data: Any):
        """创建页面局部步骤上下文，用于记录日志和截图。"""
        from contextlib import nullcontext

        return nullcontext()

    def click_salary_income_row(self) -> StepResult:
        """点击综合所得页面中的工资薪金所得行。"""
        return StepResult(ok=True, name="self_check.click_salary_income_row", status="dry_run")

    def click_salary_income_fill(self) -> StepResult:
        """点击工资薪金所得的填写入口。"""
        return StepResult(ok=True, name="self_check.click_salary_income_fill", status="dry_run")

    def click_import_button(self) -> StepResult:
        """点击当前页面的导入按钮，打开导入菜单或文件选择流程。"""
        return StepResult(ok=True, name="self_check.click_import_button", status="dry_run")

    def choose_import_data_option(self) -> StepResult:
        """从工资薪金导入菜单中选择导入数据选项。"""
        return StepResult(
            ok=True,
            name="self_check.choose_import_data_option",
            status="dry_run",
            evidence={"dialog": {"hwnd": 1}},
        )

    def choose_salary_income_file(self, path: Path, _import_option_result: StepResult) -> StepResult:
        """在文件选择框中选择工资薪金 Excel 文件。"""
        return StepResult(
            ok=True,
            name="self_check.choose_salary_income_file",
            status="dry_run",
            evidence={"file_path": str(path)},
        )

    def read_salary_income_import_result(self) -> StepResult:
        """读取工资薪金导入结果并返回分类后的步骤结果。"""
        return StepResult(
            ok=True,
            name="self_check.wait_salary_income_import_result",
            status="success",
        )


def run_workflow(
    config: PersonImportConfig,
    logger: RunLogger,
    self_check: bool,
    reset: bool = False,
) -> dict[str, Any]:
    """执行cli、导入工资薪金收入中的run工作流逻辑，供业务流程或相邻模块调用。"""
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
        workflow_factories=[lambda config, logger: ImportSalaryIncomeWorkflow(config, logger)],
        name="import_salary_income_entry_workflow",
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
        summary_path = logger.write_json("import_salary_income_summary.json", summary)
        logger.log("done", summary["status"], summary=summary_path)
        print(summary_path)
    except Exception as exc:
        logger.log("run", "failed", error=str(exc), traceback=traceback.format_exc())
        logger.write_json("failed.json", {"error": str(exc), "traceback": traceback.format_exc()})
        raise


__all__ = ["with_execution_mode"]


if __name__ == "__main__":
    main()
