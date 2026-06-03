# Windows Elevated Task Migration

This project can be copied to another Windows user profile and registered there without editing hard-coded paths.

## Prerequisites

- The copied project directory contains `.venv`.
- `config/person_import.json` exists on the target computer.
- The target user can confirm one UAC prompt during task installation.
- The tax client shortcut or executable path in `config/person_import.json` is valid on that computer.

## Install On A Target Computer

Open PowerShell in the copied project directory and run:

```powershell
.\scripts\install_elevated_task.ps1 -Submit -Reset
```

The script derives the project root from its own location. It registers the scheduled task for the current Windows user and writes the registration log to:

```text
artifacts\elevated-task-register.log
```

Use `-TaskName` when the same computer needs multiple project copies:

```powershell
.\scripts\install_elevated_task.ps1 -TaskName TaxRpaElevatedWorkflow_UserA -Submit -Reset
```

Use `-RunAsUser` only when registering for a different interactive user:

```powershell
.\scripts\install_elevated_task.ps1 -RunAsUser "DOMAIN\username" -Submit -Reset
```

## Run The Workflow

After installation, run:

```powershell
.\scripts\start_elevated_task.ps1
```

External triggers that do not want to know PowerShell details can call:

```cmd
scripts\start_elevated_task.cmd
```

Or run it directly through Windows Task Scheduler:

```powershell
schtasks /Run /TN "\TaxRpaElevatedWorkflow"
```

Do not call `python -m tax_rpa.cli.run_tax_workflow` directly from the trigger. Direct Python CLI startup can enter the self-elevation path and show a UAC prompt. The scheduled task path runs `scripts/run_elevated_workflow.ps1`, which passes `--no-self-elevate` because the task is already registered to run at the highest privilege level.

## Allow A Separate Trigger User

By default, register and run the task as the same interactive Windows user that owns the tax desktop session.

If another local/domain user must trigger the task on the same machine, register the task once with an explicit run grant:

```powershell
.\scripts\install_elevated_task.ps1 -GrantRunToUser "DOMAIN\trigger-user" -Reset
```

This grants read/execute access to the scheduled task file for that specific account. It does not grant broad administrator rights, and it does not remove the requirement that the RPA desktop user must be logged in for OCR/mouse automation to work reliably.

## Reinstall After Moving The Folder

If the project folder is moved, reinstall the task from the new folder:

```powershell
.\scripts\install_elevated_task.ps1 -Submit -Reset
```

The existing task is replaced with the new path.
