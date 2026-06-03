from dataclasses import replace

from tax_rpa.config.person_import import PersonImportConfig


def with_execution_mode(config: PersonImportConfig, submit: bool) -> PersonImportConfig:
    """根据是否允许提交派生运行配置，控制 dry-run 与真实提交边界。"""
    return replace(config, dry_run=not submit)
