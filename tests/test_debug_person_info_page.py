import unittest
from pathlib import Path

from tax_rpa.cli.debug_person_info_page import with_debug_options
from tax_rpa.config.person_import import PersonImportConfig


class DebugPersonInfoPageTests(unittest.TestCase):
    def test_with_debug_options_forces_short_timeouts_and_dry_run(self):
        config = PersonImportConfig(
            person_info_file=Path("persons.xlsx"),
            dry_run=False,
            login_timeout_seconds=300,
            window_timeout_seconds=90,
            import_timeout_seconds=120,
            result_timeout_seconds=60,
        )

        debug_config = with_debug_options(config, timeout_seconds=5, force_dry_run=True)

        self.assertTrue(debug_config.dry_run)
        self.assertEqual(debug_config.login_timeout_seconds, 5)
        self.assertEqual(debug_config.window_timeout_seconds, 5)
        self.assertEqual(debug_config.import_timeout_seconds, 5)
        self.assertEqual(debug_config.result_timeout_seconds, 5)

    def test_with_debug_options_does_not_force_dry_run_when_submit_allowed(self):
        config = PersonImportConfig(
            person_info_file=Path("persons.xlsx"),
            dry_run=False,
        )

        debug_config = with_debug_options(config, timeout_seconds=0, force_dry_run=False)

        self.assertFalse(debug_config.dry_run)
        self.assertEqual(debug_config.login_timeout_seconds, 1)


if __name__ == "__main__":
    unittest.main()
