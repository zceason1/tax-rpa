import argparse
import ctypes
import json
import subprocess
import sys
import traceback
from dataclasses import replace
from pathlib import Path
from typing import Any

from tax_rpa.app.tax_client_app import TaxClientApp
from tax_rpa.config.person_import import PersonImportConfig, load_import_config
from tax_rpa.drivers.logger import RunLogger, to_jsonable
from tax_rpa.pages.person_info.page import PersonInfoPage
from tax_rpa.runtime.result import StepResult


MODULE_NAME = "tax_rpa.cli.debug_person_info_page"
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
        description="Attach to the withholding client and debug the personnel information page."
    )
    parser.add_argument(
        "action",
        choices=("inspect", "open", "import-flow"),
        help="Page debug action. import-flow defaults to dry-run unless --submit is provided.",
    )
    parser.add_argument(
        "--config",
        default="config/person_import.json",
        help="Path to the JSON config.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=20,
        help="Short timeout in seconds for attach/page debugging.",
    )
    parser.add_argument(
        "--launch",
        action="store_true",
        help="Launch the client if it is not already running.",
    )
    parser.add_argument(
        "--submit",
        action="store_true",
        help="Allow import-flow to submit the file dialog. Without this flag import-flow is dry-run.",
    )
    parser.add_argument(
        "--no-self-elevate",
        action="store_true",
        help="Do not relaunch this debug command as administrator when not elevated.",
    )
    return parser.parse_args()


def with_debug_options(
    config: PersonImportConfig,
    timeout_seconds: int,
    force_dry_run: bool,
) -> PersonImportConfig:
    timeout = max(1, int(timeout_seconds))
    return replace(
        config,
        dry_run=force_dry_run or config.dry_run,
        login_timeout_seconds=timeout,
        window_timeout_seconds=timeout,
        import_timeout_seconds=timeout,
        result_timeout_seconds=timeout,
    )


def attach_app(config: PersonImportConfig, logger: RunLogger, launch: bool) -> TaxClientApp:
    app = TaxClientApp(config, logger)
    if launch:
        start_result = app.start_if_needed()
        if not start_result.ok:
            raise RuntimeError(start_result.error or start_result.status)
    elif not app.win32.find_process_ids(config.process_name):
        raise RuntimeError(
            f"Client process is not running: {config.process_name}. "
            "Start it manually or pass --launch."
        )

    login_result = app.wait_for_login()
    if not login_result.ok:
        raise RuntimeError(login_result.error or login_result.status)
    return app


def run_debug_action(
    action: str,
    config: PersonImportConfig,
    logger: RunLogger,
    launch: bool,
) -> dict[str, Any]:
    app = attach_app(config, logger, launch=launch)
    if app.context.hwnd is None:
        raise RuntimeError("Main window is not available")

    page = PersonInfoPage(app.context, app.context.hwnd)
    if action == "inspect":
        return {
            "action": action,
            "result": page.inspect(),
        }
    if action == "open":
        result = page.open()
        return {
            "action": action,
            "result": result,
        }
    if action == "import-flow":
        open_result = page.open()
        if not open_result.ok:
            return {
                "action": action,
                "open": open_result,
                "result": StepResult(
                    ok=False,
                    name="debug_person_info_page.import_flow",
                    status="open_failed",
                    error=open_result.error,
                ),
            }
        import_result = page.import_person_file(config.person_info_file)
        return {
            "action": action,
            "open": open_result,
            "result": import_result,
        }
    raise ValueError(f"Unsupported debug action: {action}")


def main() -> None:
    args = parse_args()
    if not args.no_self_elevate and not is_user_admin():
        relaunch_as_admin(sys.argv[1:])
        print("已请求管理员权限运行，请在 UAC 弹窗中确认。")
        return

    logger = RunLogger()
    try:
        config = load_import_config(args.config)
        config = with_debug_options(
            config,
            timeout_seconds=args.timeout,
            force_dry_run=args.action == "import-flow" and not args.submit,
        )
        summary = run_debug_action(args.action, config, logger, launch=args.launch)
        summary_path = logger.write_json(f"debug_{args.action}.json", summary)
        print(json.dumps(to_jsonable(summary), ensure_ascii=False, indent=2))
        print(summary_path)
    except Exception as exc:
        logger.log("debug_person_info_page", "failed", error=str(exc), traceback=traceback.format_exc())
        logger.write_json("debug_failed.json", {"error": str(exc), "traceback": traceback.format_exc()})
        raise


if __name__ == "__main__":
    main()
