import json
import unittest
from pathlib import Path

from tax_rpa.config.person_import import (
    PersonImportConfigError,
    assert_safe_action,
    load_import_config,
    validate_excel_path,
)


class PersonImportConfigTests(unittest.TestCase):
    def test_load_config_resolves_relative_person_file_from_config_directory(self):
        with self.subTest("relative path resolution"):
            import tempfile

            with tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                data_dir = root / "data"
                data_dir.mkdir()
                excel_file = data_dir / "persons.xlsx"
                excel_file.write_bytes(b"placeholder")

                config_path = root / "person_import.json"
                config_path.write_text(
                    json.dumps(
                        {
                            "person_info_file": "data/persons.xlsx",
                            "dry_run": True,
                            "window_timeout_seconds": 15,
                        }
                    ),
                    encoding="utf-8",
                )

                config = load_import_config(config_path)

                self.assertEqual(config.person_info_file, excel_file.resolve())
                self.assertIs(config.dry_run, True)
                self.assertEqual(config.window_timeout_seconds, 15)
                self.assertEqual(config.import_timeout_seconds, 120)

    def test_load_config_resolves_optional_app_path_and_login_timeout(self):
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            excel_file = root / "persons.xlsx"
            excel_file.write_bytes(b"placeholder")
            app_file = root / "EPPortalITS.exe"
            app_file.write_bytes(b"placeholder")

            config_path = root / "person_import.json"
            config_path.write_text(
                json.dumps(
                    {
                        "person_info_file": "persons.xlsx",
                        "app_path": "EPPortalITS.exe",
                        "process_name": "EPPortalITS.exe",
                        "launch_timeout_seconds": 20,
                        "login_timeout_seconds": 30,
                    }
                ),
                encoding="utf-8",
            )

            config = load_import_config(config_path)

            self.assertEqual(config.app_path, app_file.resolve())
            self.assertEqual(config.process_name, "EPPortalITS.exe")
            self.assertEqual(config.launch_timeout_seconds, 20)
            self.assertEqual(config.login_timeout_seconds, 30)

    def test_load_config_reads_declaration_password_login_config(self):
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            excel_file = root / "persons.xlsx"
            excel_file.write_bytes(b"placeholder")
            config_path = root / "person_import.json"
            config_path.write_text(
                json.dumps(
                    {
                        "person_info_file": "persons.xlsx",
                        "login": {
                            "method": "申报密码登录",
                            "declaration_password": "secret-password",
                        },
                    }
                ),
                encoding="utf-8",
            )

            config = load_import_config(config_path)

            self.assertEqual(config.login.method, "申报密码登录")
            self.assertEqual(config.login.declaration_password, "secret-password")

    def test_empty_declaration_password_disables_auto_login(self):
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            excel_file = root / "persons.xlsx"
            excel_file.write_bytes(b"placeholder")
            config_path = root / "person_import.json"
            config_path.write_text(
                json.dumps(
                    {
                        "person_info_file": "persons.xlsx",
                        "login": {
                            "declaration_password": "",
                        },
                    }
                ),
                encoding="utf-8",
            )

            config = load_import_config(config_path)

            self.assertEqual(config.login.method, "申报密码登录")
            self.assertIsNone(config.login.declaration_password)

    def test_login_config_must_be_an_object(self):
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            excel_file = root / "persons.xlsx"
            excel_file.write_bytes(b"placeholder")
            config_path = root / "person_import.json"
            config_path.write_text(
                json.dumps(
                    {
                        "person_info_file": "persons.xlsx",
                        "login": "secret-password",
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(PersonImportConfigError, "login must be a JSON object"):
                load_import_config(config_path)

    def test_load_config_resolves_named_import_files_from_config_directory(self):
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "data"
            data_dir.mkdir()
            person_file = data_dir / "persons.xlsx"
            salary_file = data_dir / "salary.xlsx"
            person_file.write_bytes(b"placeholder")
            salary_file.write_bytes(b"placeholder")

            config_path = root / "person_import.json"
            config_path.write_text(
                json.dumps(
                    {
                        "person_info_file": "data/persons.xlsx",
                        "imports": {
                            "person_info": {"file": "data/persons.xlsx"},
                            "salary_income": {"file": "data/salary.xlsx"},
                        },
                    }
                ),
                encoding="utf-8",
            )

            config = load_import_config(config_path)

            self.assertEqual(config.import_file("person_info"), person_file.resolve())
            self.assertEqual(config.import_file("salary_income"), salary_file.resolve())
            self.assertEqual(config.imports["salary_income"].file, salary_file.resolve())

    def test_import_file_rejects_unknown_import_location(self):
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            person_file = root / "persons.xlsx"
            person_file.write_bytes(b"placeholder")
            config_path = root / "person_import.json"
            config_path.write_text(
                json.dumps({"person_info_file": "persons.xlsx"}),
                encoding="utf-8",
            )

            config = load_import_config(config_path)

            with self.assertRaisesRegex(PersonImportConfigError, "Unknown import location"):
                config.import_file("salary_income")

    def test_load_config_does_not_validate_unused_named_import_file(self):
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            person_file = root / "persons.xlsx"
            person_file.write_bytes(b"placeholder")
            config_path = root / "person_import.json"
            config_path.write_text(
                json.dumps(
                    {
                        "person_info_file": "persons.xlsx",
                        "imports": {
                            "salary_income": {"file": "missing_salary.xlsx"},
                        },
                    }
                ),
                encoding="utf-8",
            )

            config = load_import_config(config_path)

            self.assertEqual(config.import_file("person_info"), person_file.resolve())
            with self.assertRaises(FileNotFoundError):
                config.import_file("salary_income")

    def test_assert_safe_action_allows_comprehensive_income_navigation(self):
        assert_safe_action("综合所得申报")

    def test_assert_safe_action_allows_declaration_password_login(self):
        assert_safe_action("申报密码登录")

    def test_validate_excel_path_rejects_missing_file(self):
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(FileNotFoundError):
                validate_excel_path(Path(temp_dir) / "missing.xlsx")

    def test_validate_excel_path_rejects_non_excel_file(self):
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            text_file = Path(temp_dir) / "persons.txt"
            text_file.write_text("not excel", encoding="utf-8")

            with self.assertRaisesRegex(PersonImportConfigError, "Excel"):
                validate_excel_path(text_file)

    def test_assert_safe_action_blocks_report_submit_actions(self):
        with self.assertRaisesRegex(PersonImportConfigError, "forbidden"):
            assert_safe_action("报送")

        with self.assertRaisesRegex(PersonImportConfigError, "forbidden"):
            assert_safe_action("发送申报")

    def test_assert_safe_action_allows_import_actions(self):
        assert_safe_action("人员信息采集")
        assert_safe_action("导入")
        assert_safe_action("标准模板导入")


if __name__ == "__main__":
    unittest.main()
