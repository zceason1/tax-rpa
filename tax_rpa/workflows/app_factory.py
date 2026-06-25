from typing import Any

from tax_rpa.config.person_import import PersonImportConfig


def create_tax_client_app(config: PersonImportConfig, logger: Any) -> Any:
    """Create the real tax client app only when a workflow needs it."""
    from tax_rpa.app.tax_client_app import TaxClientApp

    return TaxClientApp(config, logger)
