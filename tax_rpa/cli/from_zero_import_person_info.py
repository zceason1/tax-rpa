import argparse
import ctypes
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Any

from tax_rpa.app.tax_client_app import TaxClientApp, build_launch_decision
from tax_rpa.config.person_import import PersonImportConfig, load_import_config
from tax_rpa.drivers.logger import RunLogger
from tax_rpa.drivers.win32_driver import Win32Driver
from tax_rpa.runtime.result import StepResult
from tax_rpa.workflows.import_person_info_workflow import ImportPersonInfoWorkflow


MODULE_NAME = "tax_rpa.cli.from_zero_import_person_info"
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


def find_process_ids(process_name: str) -> list[int]:
    return Win32Driver().find_process_ids(process_name)


def is_process_not_found(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        ("未找到" in message or "not found" in message)
        and ("进程" in message or "process" in message or "epportalits" in message)
    )


def launch_client(app_path: Path, logger: RunLogger):
    return Win32Driver().launch_client(app_path, logger)


def wait_for_process(
    process_name: str,
    timeout_seconds: int,
    logger: RunLogger,
) -> list[int]:
    return Win32Driver().wait_for_process(process_name, timeout_seconds, logger)


def wait_for_main_window(
    process_name: str,
    timeout_seconds: int,
    logger: RunLogger,
) -> dict[str, Any]:
    config = PersonImportConfig(
        person_info_file=Path("placeholder.xlsx"),
        process_name=process_name,
        login_timeout_seconds=timeout_seconds,
    )
    app = TaxClientApp(config, logger)
    result = app.wait_for_login()
    if not result.ok:
        raise RuntimeError(result.error)
    return result.evidence["main_window"]


def configure_base_process_name(process_name: str) -> None:
    Win32Driver().configure_base_process_name(process_name)


def run_from_zero(
    config: PersonImportConfig,
    logger: RunLogger,
    reset: bool = False,
) -> dict[str, Any]:
    workflow = ImportPersonInfoWorkflow(config, logger, reset=reset)
    workflow_result = workflow.run()
    if not workflow_result.ok:
        raise RuntimeError(workflow_result.error or workflow_result.status)
    return {
        "status": workflow_result.status,
        "workflow": workflow_result,
    }


class SelfCheckApp:
    def __init__(self, _config: PersonImportConfig, _logger: Any) -> None:
        pass

    def start_if_needed(self) -> StepResult:
        from tax_rpa.runtime.result import StepResult

        return StepResult(ok=True, name="self_check.start_if_needed", status="self_check_start")

    def wait_for_login(self) -> StepResult:
        from tax_rpa.runtime.result import StepResult

        return StepResult(ok=True, name="self_check.wait_for_login", status="self_check_login")

    def reset(self) -> StepResult:
        from tax_rpa.runtime.result import StepResult

        return StepResult(ok=True, name="self_check.reset", status="self_check_reset")

    def shell(self):
        return SelfCheckShell()


class SelfCheckShell:
    def open_person_info_page(self):
        return SelfCheckPersonInfoPage()

    def open_special_deduction_page(self):
        return SelfCheckSpecialDeductionPage()

    def open_comprehensive_income_page(self):
        return SelfCheckComprehensiveIncomePage()


class SelfCheckPersonInfoPage:
    def step(self, _name: str, **_data: Any):
        from contextlib import nullcontext

        return nullcontext()

    def close_message_dialog_if_present(self):
        from tax_rpa.runtime.result import StepResult

        return StepResult(ok=True, name="self_check.close_message_dialog", status="none")

    def click_import_button(self):
        from tax_rpa.runtime.result import StepResult

        return StepResult(ok=True, name="self_check.click_import_button", status="clicked")

    def choose_import_file_option(self):
        from tax_rpa.runtime.result import StepResult

        return StepResult(
            ok=True,
            name="self_check.choose_import_file_option",
            status="selected",
            evidence={"dialog": {"hwnd": 1}},
        )

    def choose_person_file(self, path: Path, _dropdown_result: StepResult):
        from tax_rpa.runtime.result import StepResult

        return StepResult(
            ok=True,
            name="self_check.choose_person_file",
            status="dry_run",
            evidence={"file_path": str(path)},
        )

    def read_import_result(self):
        from tax_rpa.runtime.result import StepResult

        return StepResult(ok=True, name="self_check.wait_import_result", status="success")


class SelfCheckSpecialDeductionPage:
    def step(self, _name: str, **_data: Any):
        from contextlib import nullcontext

        return nullcontext()

    def click_download_update(self):
        from tax_rpa.runtime.result import StepResult

        return StepResult(ok=True, name="self_check.click_download_update", status="dry_run")

    def click_all_persons(self):
        from tax_rpa.runtime.result import StepResult

        return StepResult(ok=True, name="self_check.click_all_persons", status="dry_run")


class SelfCheckComprehensiveIncomePage:
    def step(self, _name: str, **_data: Any):
        from contextlib import nullcontext

        return nullcontext()

    def click_salary_income_row(self):
        from tax_rpa.runtime.result import StepResult

        return StepResult(ok=True, name="self_check.click_salary_income_row", status="dry_run")

    def click_salary_income_fill(self):
        from tax_rpa.runtime.result import StepResult

        return StepResult(ok=True, name="self_check.click_salary_income_fill", status="dry_run")

    def click_import_button(self):
        from tax_rpa.runtime.result import StepResult

        return StepResult(ok=True, name="self_check.click_import_button", status="dry_run")

    def choose_import_data_option(self):
        from tax_rpa.runtime.result import StepResult

        return StepResult(
            ok=True,
            name="self_check.choose_import_data_option",
            status="dry_run",
            evidence={"dialog": {"hwnd": 1}},
        )

    def choose_salary_income_file(self, path: Path, _import_option_result: StepResult):
        from tax_rpa.runtime.result import StepResult

        return StepResult(
            ok=True,
            name="self_check.choose_salary_income_file",
            status="dry_run",
            evidence={"file_path": str(path)},
        )

    def read_salary_income_import_result(self):
        from tax_rpa.runtime.result import StepResult

        return StepResult(
            ok=True,
            name="self_check.wait_salary_income_import_result",
            status="success",
        )

    def click_prefill_deduction(self):
        from tax_rpa.runtime.result import StepResult

        return StepResult(ok=True, name="self_check.click_prefill_deduction", status="clicked")

    def read_prefill_confirmation_dialog(self):
        from tax_rpa.runtime.result import StepResult

        return StepResult(
            ok=True,
            name="self_check.read_prefill_confirmation_dialog",
            status="ready",
            ui_text=["self_check_prefill_confirmation"],
        )

    def confirm_prefill_options(self, *, allow_skip_personal_pension: bool):
        from tax_rpa.runtime.result import StepResult

        return StepResult(
            ok=True,
            name="self_check.confirm_prefill_options",
            status="confirmed",
            evidence={"allow_skip_personal_pension": allow_skip_personal_pension},
        )

    def read_prefill_result(self):
        from tax_rpa.runtime.result import StepResult

        return StepResult(ok=True, name="self_check.read_prefill_result", status="success")

    def click_tax_calculation_tab(self):
        from tax_rpa.runtime.result import StepResult

        return StepResult(ok=True, name="self_check.click_tax_calculation_tab", status="clicked")

    def read_tax_calculation_popup(self):
        from tax_rpa.runtime.result import StepResult

        return StepResult(ok=True, name="self_check.read_tax_calculation_popup", status="no_popup")

    def confirm_tax_calculation_popup(self):
        from tax_rpa.runtime.result import StepResult

        return StepResult(
            ok=True,
            name="self_check.confirm_tax_calculation_popup",
            status="confirmed",
        )

    def read_tax_calculation_result(self):
        from tax_rpa.runtime.result import StepResult

        return StepResult(ok=True, name="self_check.read_tax_calculation_result", status="success")

    def open_declaration_submission_page(self):
        from tax_rpa.runtime.result import StepResult

        return StepResult(
            ok=True,
            name="self_check.open_declaration_submission_page",
            status="ready",
        )

    def locate_send_declaration_button(self):
        from tax_rpa.runtime.result import StepResult

        return StepResult(
            ok=True,
            name="self_check.locate_send_declaration_button",
            status="ready_to_submit_not_sent",
        )

    def open_export_report_menu(self):
        from tax_rpa.runtime.result import StepResult

        return StepResult(ok=True, name="self_check.open_export_report_menu", status="opened")

    def choose_standard_report_option(self):
        from tax_rpa.runtime.result import StepResult

        return StepResult(
            ok=True,
            name="self_check.choose_standard_report_option",
            status="selected",
        )

    def read_export_result(self, *, run_mode: str):
        from tax_rpa.runtime.result import StepResult

        if run_mode == "execute_no_send":
            return StepResult(
                ok=True,
                name="self_check.read_export_result",
                status="not_available_before_submit",
                evidence={"export_status": "not_available_before_submit"},
            )
        return StepResult(
            ok=True,
            name="self_check.read_export_result",
            status="exported",
            evidence={"export_status": "exported"},
        )


def run_self_check(
    config: PersonImportConfig,
    logger: Any,
) -> dict[str, Any]:
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
