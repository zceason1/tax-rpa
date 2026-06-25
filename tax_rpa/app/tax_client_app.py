import time
from dataclasses import replace
from pathlib import Path, PureWindowsPath
from typing import Any

from tax_rpa.app.main_shell import MainShell
from tax_rpa.app.login import LoginComponent
from tax_rpa.config.person_import import PersonImportConfig
from tax_rpa.drivers.win32_driver import Win32Driver
from tax_rpa.runtime.context import RpaContext
from tax_rpa.runtime.result import StepResult


AUTO_LOGIN_MAX_FAILURES = 3
LOGIN_WINDOW_CLASSES = ("Tfrm_LoginViewer",)


def build_launch_decision(pids: list[int], app_path: Path | None) -> dict[str, Any]:
    """根据进程状态和应用路径判断本次是否需要启动客户端。"""
    if pids:
        return {"action": "reuse_running_process", "pids": pids}
    if app_path is None:
        return {"action": "missing_app_path"}
    return {"action": "launch", "app_path": str(PureWindowsPath(str(app_path)))}


def choose_login_window(windows: list[dict[str, Any]]) -> dict[str, Any]:
    """从候选窗口中选择最可能是真实登录界面的窗口。"""
    for class_name in LOGIN_WINDOW_CLASSES:
        for window in windows:
            if window.get("class") == class_name:
                return window
    return windows[0]


class TaxClientApp:
    """税务客户端应用门面，负责启动、重置、登录等待和主界面入口。"""
    def __init__(
        self,
        config: PersonImportConfig,
        logger: Any,
        win32: Win32Driver | None = None,
    ) -> None:
        """初始化税务客户端实例，保存依赖、配置和运行上下文。"""
        self.config = config
        self.logger = logger
        self.win32 = win32 or Win32Driver()
        self.context = RpaContext(config=config, logger=logger)

    def reset(self) -> StepResult:
        """重置税务客户端进程，清理旧窗口后准备重新启动。"""
        self.win32.configure_base_process_name(self.config.process_name)
        pids = self.win32.find_process_ids(self.config.process_name)
        if not pids:
            self.logger.log("reset_client", "not_running", process_name=self.config.process_name)
            return StepResult(
                ok=True,
                name="tax_client_app.reset",
                status="not_running",
                evidence={"pids": []},
            )

        result = self.win32.terminate_processes(
            pids,
            self.config.launch_timeout_seconds,
            self.logger,
        )
        ok = not result.get("alive")
        return StepResult(
            ok=ok,
            name="tax_client_app.reset",
            status="terminated" if ok else "alive_after_kill",
            evidence={"result": result},
            error=None if ok else f"Client processes still alive: {result.get('alive')}",
        )

    def start_if_needed(self) -> StepResult:
        """在客户端未运行时启动客户端，已运行时直接复用。"""
        self.win32.configure_base_process_name(self.config.process_name)
        pids = self.win32.find_process_ids(self.config.process_name)
        decision = build_launch_decision(pids, self.config.app_path)
        self.logger.log("launch_decision", decision["action"], decision=decision)

        if decision["action"] == "missing_app_path":
            return StepResult(
                ok=False,
                name="tax_client_app.start_if_needed",
                status="missing_app_path",
                evidence={"decision": decision},
                error="Client is not running and config.app_path is not configured",
            )
        if decision["action"] == "launch":
            self.win32.launch_client(Path(decision["app_path"]), self.logger)
            pids = self.win32.wait_for_process(
                self.config.process_name,
                self.config.launch_timeout_seconds,
                self.logger,
            )
            decision = {**decision, "pids": pids}

        return StepResult(
            ok=True,
            name="tax_client_app.start_if_needed",
            status=decision["action"],
            evidence={"decision": decision},
        )

    def wait_for_login(self) -> StepResult:
        """等待客户端完成登录；配置了自动登录时会尝试自动输入申报密码。"""
        deadline = time.time() + self.config.login_timeout_seconds
        last_error = None
        last_log_at = 0.0
        auto_login_attempted = False
        auto_login_failures = 0
        while time.time() < deadline:
            pids = self.win32.find_process_ids(self.config.process_name)
            if pids:
                try:
                    main_window = self.win32.find_main_window(pids, self.logger)
                    self.win32.set_foreground(main_window["hwnd"])
                    self.context.main_window = main_window
                    self.logger.log("wait_main_window", "found", main_window=main_window)
                    return StepResult(
                        ok=True,
                        name="tax_client_app.wait_for_login",
                        status="main_window_found",
                        evidence={"main_window": main_window},
                    )
                except Exception as exc:
                    last_error = str(exc)
                    if not auto_login_attempted:
                        try:
                            auto_login = self._try_auto_login(pids)
                        except Exception as login_exc:
                            last_error = str(login_exc)
                            auto_login_failures += 1
                            self.logger.log(
                                "auto_login",
                                "not_ready",
                                error=str(login_exc),
                                attempts=auto_login_failures,
                                max_attempts=AUTO_LOGIN_MAX_FAILURES,
                                pids=pids,
                            )
                            if auto_login_failures >= AUTO_LOGIN_MAX_FAILURES:
                                error = (
                                    "Auto login failed after "
                                    f"{auto_login_failures} attempts: unable to find or click "
                                    f"the configured login element. Last error: {last_error}"
                                )
                                self.logger.log(
                                    "auto_login",
                                    "failed",
                                    error=error,
                                    attempts=auto_login_failures,
                                    pids=pids,
                                )
                                return StepResult(
                                    ok=False,
                                    name="tax_client_app.wait_for_login",
                                    status="auto_login_failed",
                                    evidence={
                                        "attempts": auto_login_failures,
                                        "max_attempts": AUTO_LOGIN_MAX_FAILURES,
                                        "last_error": last_error,
                                        "pids": pids,
                                    },
                                    error=error,
                                    error_type="LOGIN_FAILED",
                                    error_code="auto_login_element_not_found",
                                )
                        else:
                            auto_login_attempted = (
                                auto_login is not None and auto_login.ok
                            )
                            if auto_login_attempted:
                                auto_login_failures = 0

            now = time.time()
            if now - last_log_at >= 10:
                self.logger.log(
                    "wait_login_or_main_window",
                    "waiting",
                    process_name=self.config.process_name,
                    pids=pids,
                    last_error=last_error,
                )
                print("请在客户端内完成登录；检测到主界面后脚本会自动继续。", flush=True)
                last_log_at = now
            time.sleep(1.0)

        return StepResult(
            ok=False,
            name="tax_client_app.wait_for_login",
            status="timeout",
            evidence={"last_error": last_error},
            error=f"Timed out waiting for main window after login: {last_error}",
        )

    def _try_auto_login(self, pids: list[int]) -> StepResult | None:
        """尝试在登录窗口执行一次自动登录，并返回本次尝试结果。"""
        password = self.config.login.declaration_password
        if not password:
            return None

        windows = self.win32.collect_top_windows_for_pids(pids)
        if not windows:
            self.logger.log("auto_login", "no_login_window", pids=pids)
            return None

        login_window = choose_login_window(windows)
        self.win32.set_foreground(login_window["hwnd"])
        result = LoginComponent(
            hwnd=login_window["hwnd"],
            window_rect=login_window["rect"],
            logger=self.logger,
            config=replace(self.config, dry_run=False),
        ).login_with_declaration_password(password)
        self.logger.log(
            "auto_login",
            result.status,
            method=self.config.login.method,
            password_configured=True,
        )
        return result

    def shell(self) -> MainShell:
        """返回主界面门面对象，供工作流继续打开业务页面。"""
        return MainShell(self.context)
