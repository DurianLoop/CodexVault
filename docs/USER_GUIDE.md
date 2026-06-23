# Codex Vault User Guide

Codex Vault is a local-first Windows desktop tool for inspecting, backing up, exporting, importing, and testing a `.codex` folder.

## Start

Source checkout:

```powershell
python -m codexvault.ui_app
```

Portable beta:

```powershell
.\CodexVault.exe
```

Runtime data is stored in `%LOCALAPPDATA%\CodexVault`.

## Scan A Vault

1. Open the app.
2. Browse to `C:\Users\<you>\.codex`.
3. Select Scan.
4. Review Dashboard, Skills, Memory, Sync / Packs, and Achievements.

No cloud upload happens during scan.

## Export A Pack

Open Sync / Packs and choose Export. Codex Vault excludes common secrets, runtime logs, cache folders, sessions, SQLite files, and generated backup/export data.

## Import A Pack

Imports show a preview before writing:

- added files
- replaced files
- skipped files
- unknown-folder warnings
- markdown diffs for changed `.md` files

Cancel leaves the target unchanged. Confirming creates a backup first, imports the selected actions, shows a summary, and writes recent import history locally.

## Rollback

Open Sync / Packs, select a backup, and choose Rollback Selected. The confirmation names the backup timestamp and target root before restoring files.

## Achievements

The achievement wall shows one achievement per row with description, requirement, progress, state, and activation. Locked achievements cannot be activated. Activation and unlock history are stored locally.

## Backend Lab

The backend is optional and local-first. Start it only when testing sync-ready APIs:

```powershell
.\run_backend.bat
```

The desktop app can be used without logging in.
