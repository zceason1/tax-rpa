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


def has_business_side_effect(result: WorkflowResult) -> bool:
    if result.side_effect_started or result.side_effect_committed:
        return True
    return any(
        step.side_effect_started or step.side_effect_committed
        for step in result.steps
    )


def can_retry_after_failure(result: WorkflowResult) -> bool:
    if not is_recoverable_environment_failure(result):
        return False
    if has_business_side_effect(result):
        return False
    return bool(result.retry_allowed)
