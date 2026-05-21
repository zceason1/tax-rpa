from collections.abc import Callable
from typing import Any

from tax_rpa.config.person_import import PersonImportConfig
from tax_rpa.app.tax_client_app import TaxClientApp
from tax_rpa.pages.person_info.steps.import_person_file import ImportPersonFileStep
from tax_rpa.pages.person_info.steps.open_page import OpenPersonInfoPageStep
from tax_rpa.pages.person_info.steps.wait_import_result import WaitImportResultStep
from tax_rpa.runtime.result import StepResult, WorkflowResult


class ImportPersonInfoWorkflow:
    def __init__(
        self,
        config: PersonImportConfig,
        logger: Any,
        app_factory: Callable[[PersonImportConfig, Any], Any] | None = None,
    ) -> None:
        self.config = config
        self.logger = logger
        self.app_factory = app_factory or (lambda config, logger: TaxClientApp(config, logger))

    def run(self) -> WorkflowResult:
        steps: list[StepResult] = []
        app = self.app_factory(self.config, self.logger)

        start = app.start_if_needed()
        steps.append(start)
        if not start.ok:
            return WorkflowResult(
                ok=False,
                name="import_person_info_workflow",
                status=start.status,
                steps=steps,
                error=start.error,
            )

        login = app.wait_for_login()
        steps.append(login)
        if not login.ok:
            return WorkflowResult(
                ok=False,
                name="import_person_info_workflow",
                status=login.status,
                steps=steps,
                error=login.error,
            )

        page = OpenPersonInfoPageStep(app.shell()).run()
        import_file = ImportPersonFileStep(page).run(self.config.person_info_file)
        steps.append(import_file)
        if not import_file.ok:
            return WorkflowResult(
                ok=False,
                name="import_person_info_workflow",
                status=import_file.status,
                steps=steps,
                evidence={"import_file": import_file.evidence},
                error=import_file.error,
            )

        import_result = WaitImportResultStep(page).run()
        steps.append(import_result)

        return WorkflowResult(
            ok=import_result.ok,
            name="import_person_info_workflow",
            status=import_result.status,
            steps=steps,
            evidence={
                "import_file": import_file.evidence,
                "import_result": import_result.evidence,
            },
            error=import_result.error,
        )
