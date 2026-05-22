from dataclasses import replace

from tax_rpa.config.person_import import PersonImportConfig


def with_execution_mode(config: PersonImportConfig, submit: bool) -> PersonImportConfig:
    return replace(config, dry_run=not submit)
