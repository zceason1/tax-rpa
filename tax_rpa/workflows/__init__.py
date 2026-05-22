"""Workflow orchestration modules."""
from tax_rpa.workflows.app_lifecycle_workflow import AppLifecycleWorkflow
from tax_rpa.workflows.combined_tax_workflow import CombinedTaxWorkflow
from tax_rpa.workflows.import_person_info_workflow import ImportPersonInfoWorkflow
from tax_rpa.workflows.import_salary_income_workflow import ImportSalaryIncomeWorkflow
from tax_rpa.workflows.update_special_deduction_workflow import (
    UpdateSpecialDeductionWorkflow,
)

__all__ = [
    "AppLifecycleWorkflow",
    "CombinedTaxWorkflow",
    "ImportPersonInfoWorkflow",
    "ImportSalaryIncomeWorkflow",
    "UpdateSpecialDeductionWorkflow",
]
