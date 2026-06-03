import argparse
import ctypes
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Any

from tax_rpa.config.person_import import PersonImportConfig, load_import_config
from tax_rpa.drivers.logger import RunLogger
from tax_rpa.testing.self_check_app import SelfCheckApp
from tax_rpa.workflows.import_person_info_workflow import ImportPersonInfoWorkflow


MODULE_NAME = "tax_rpa.cli.from_zero_import_person_info"
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

def run_from_zero(
    config: PersonImportConfig,
    logger: RunLogger,
    reset: bool = False,
) -> dict[str, Any]:
    """从启动客户端开始执行人员信息导入工作流。"""
    workflow = ImportPersonInfoWorkflow(config, logger, reset=reset)
    workflow_result = workflow.run()
    if not workflow_result.ok:
        raise RuntimeError(workflow_result.error or workflow_result.status)
    return {
        "status": workflow_result.status,
        "workflow": workflow_result,
    }

def run_self_check(
    config: PersonImportConfig,
    logger: Any,
) -> dict[str, Any]:
    """使用假的页面对象跑通完整工作流结构，不依赖真实客户端。"""
    workflow = ImportPersonInfoWorkflow(
        config,
        logger,
        app_factory=lambda config, logger: SelfCheckApp(config, logger),
    )
    workflow_result = workflow.run()
    if not workflow_result.ok:
        raise RuntimeError(workflow_result.error or workflow_result.status)
    return {
        "status": workflow_result.status,
        "workflow": workflow_result,
    }


def parse_args() -> argparse.Namespace:
    """解析命令行参数，返回入口函数使用的参数对象。"""
    parser = argparse.ArgumentParser(
        description="Launch the withholding client, wait for login, then import personnel information."
    )
    parser.add_argument(
        "--config",
        default="config/person_import.json",
        help="Path to the JSON config with person_info_file and optional app_path.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Launch/wait and locate targets without submitting the file dialog.",
    )
    parser.add_argument(
        "--no-self-elevate",
        action="store_true",
        help="Do not relaunch this script as administrator when not elevated.",
    )
    parser.add_argument(
        "--self-check",
        action="store_true",
        help="Run the workflow composition with fake app/page objects to verify the framework wiring.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Terminate any running client process before launching and waiting for login.",
    )
    return parser.parse_args()


def with_dry_run(config: PersonImportConfig) -> PersonImportConfig:
    """从原配置派生 dry-run 配置，保证自检不触发真实提交。"""
    return PersonImportConfig(
        person_info_file=config.person_info_file,
        imports=config.imports,
        app_path=config.app_path,
        process_name=config.process_name,
        dry_run=True,
        launch_timeout_seconds=config.launch_timeout_seconds,
        login_timeout_seconds=config.login_timeout_seconds,
        window_timeout_seconds=config.window_timeout_seconds,
        import_timeout_seconds=config.import_timeout_seconds,
        result_timeout_seconds=config.result_timeout_seconds,
        ocr_score_threshold=config.ocr_score_threshold,
        config_path=config.config_path,
        login=config.login,
    )


def main() -> None:
    """命令行入口，解析参数并触发对应业务流程。"""
    args = parse_args()
    if not args.no_self_elevate and not is_user_admin():
        relaunch_as_admin(sys.argv[1:])
        print("已请求管理员权限运行，请在 UAC 弹窗中确认。")
        return

    logger = RunLogger()
    try:
        config = load_import_config(args.config)
        if args.dry_run:
            config = with_dry_run(config)
        summary = (
            run_self_check(config, logger)
            if args.self_check
            else run_from_zero(config, logger, reset=args.reset)
        )
        summary_path = logger.write_json("summary.json", summary)
        logger.log("done", summary["status"], summary=summary_path)
        print(summary_path)
    except Exception as exc:
        logger.log("run", "failed", error=str(exc), traceback=traceback.format_exc())
        logger.write_json("failed.json", {"error": str(exc), "traceback": traceback.format_exc()})
        raise


if __name__ == "__main__":
    main()
