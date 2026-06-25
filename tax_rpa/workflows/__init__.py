"""Workflow orchestration modules."""

_EXPORTS = {
    "AppLifecycleWorkflow": "tax_rpa.workflows.app_lifecycle_workflow",
    "BusinessWorkflow": "tax_rpa.workflows.base",
    "CombinedTaxWorkflow": "tax_rpa.workflows.combined_tax_workflow",
    "ImportPersonInfoWorkflow": "tax_rpa.workflows.import_person_info_workflow",
    "ImportSalaryIncomeWorkflow": "tax_rpa.workflows.import_salary_income_workflow",
    "UpdateSpecialDeductionWorkflow": "tax_rpa.workflows.update_special_deduction_workflow",
    "WorkflowContext": "tax_rpa.workflows.context",
}

__all__ = [
    "AppLifecycleWorkflow",
    "BusinessWorkflow",
    "CombinedTaxWorkflow",
    "ImportPersonInfoWorkflow",
    "ImportSalaryIncomeWorkflow",
    "UpdateSpecialDeductionWorkflow",
    "WorkflowContext",
]


def __getattr__(name):
    """Load workflow exports lazily so non-Windows tests can import support modules."""
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from importlib import import_module

    module = import_module(_EXPORTS[name])
    value = getattr(module, name)
    globals()[name] = value
    return value
