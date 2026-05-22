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

Or run it directly through Windows:

```powershell
schtasks /Run /TN TaxRpaElevatedWorkflow
```

## Reinstall After Moving The Folder

If the project folder is moved, reinstall the task from the new folder:

```powershell
.\scripts\install_elevated_task.ps1 -Submit -Reset
```

The existing task is replaced with the new path.
