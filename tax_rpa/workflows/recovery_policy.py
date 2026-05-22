from tax_rpa.runtime.result import WorkflowResult


RECOVERABLE_STATUSES = {
    "timeout",
    "missing_app_path",
    "main_window_missing",
    "main_window_lost",
    "process_not_found",
}

RECOVERABLE_ERROR_MARKERS = (
    "Timed out waiting for page",
    "Timed out waiting for main window",
    "Main window is not available",
    "Client process is not running",
    "process is not running",
)


def is_recoverable_environment_failure(result: WorkflowResult) -> bool:
    if result.ok:
        return False
    if result.status in RECOVERABLE_STATUSES:
        return True
    error = result.error or ""
    return any(marker in error for marker in RECOVERABLE_ERROR_MARKERS)
