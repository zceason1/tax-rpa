import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ElevatedTaskScriptTests(unittest.TestCase):
    def test_scripts_do_not_embed_local_project_root(self):
        for script in (
            "scripts/register_elevated_task.ps1",
            "scripts/run_elevated_workflow.ps1",
        ):
            with self.subTest(script=script):
                content = (PROJECT_ROOT / script).read_text(encoding="utf-8")

                self.assertNotIn("C:\\rpa-tax-poc", content)

    def test_scripts_derive_project_root_from_script_location(self):
        for script in (
            "scripts/register_elevated_task.ps1",
            "scripts/run_elevated_workflow.ps1",
        ):
            with self.subTest(script=script):
                content = (PROJECT_ROOT / script).read_text(encoding="utf-8")

                self.assertIn("$PSScriptRoot", content)
                self.assertIn("Split-Path -Parent", content)

    def test_register_script_allows_user_override_without_fixed_account(self):
        content = (PROJECT_ROOT / "scripts/register_elevated_task.ps1").read_text(
            encoding="utf-8"
        )

        self.assertIn("$RunAsUser", content)
        self.assertNotIn("$env:USERNAME", content)

    def test_install_script_uses_its_own_project_root_and_artifacts_log(self):
        content = (PROJECT_ROOT / "scripts/install_elevated_task.ps1").read_text(
            encoding="utf-8"
        )

        self.assertIn("$PSScriptRoot", content)
        self.assertIn("Split-Path -Parent", content)
        self.assertIn("artifacts", content)
        self.assertIn("elevated-task-register.log", content)

    def test_install_script_runs_elevated_bootstrap_file_not_inline_command(self):
        content = (PROJECT_ROOT / "scripts/install_elevated_task.ps1").read_text(
            encoding="utf-8"
        )

        self.assertIn("elevated-task-register-bootstrap.ps1", content)
        self.assertIn("Set-Content", content)
        self.assertIn('"-File"', content)
        self.assertNotIn('"-Command"', content)

    def test_install_script_does_not_pass_empty_run_as_user_argument(self):
        content = (PROJECT_ROOT / "scripts/install_elevated_task.ps1").read_text(
            encoding="utf-8"
        )

        self.assertIn('$bootstrapArgs += @("-RunAsUser", $RunAsUser)', content)
        self.assertNotIn(
            '"-RunAsUser",\n    $RunAsUser,\n    "-LogPath"',
            content,
        )

    def test_install_bootstrap_uses_named_splatting_for_register_script(self):
        content = (PROJECT_ROOT / "scripts/install_elevated_task.ps1").read_text(
            encoding="utf-8"
        )

        self.assertIn("$registerArgs = @{", content)
        self.assertIn("& $RegisterScript @registerArgs", content)
        self.assertNotIn('"-TaskName", $TaskName', content)


if __name__ == "__main__":
    unittest.main()
