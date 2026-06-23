# Windows Packaging

Codex Vault v0.3 uses PyInstaller as the first private-beta packaging path.

The portable build is local-first: it bundles the desktop app, achievement PNG assets, docs, README, and a local backend executable. Runtime data is written to the user's local app data directory instead of the executable folder.

## Prerequisites

- Windows 10 or newer
- Python 3.11 or newer for the build machine
- PyInstaller on the build machine

Install PyInstaller:

```powershell
python -m pip install pyinstaller
```

## Build

From the repository root:

```powershell
python tools\build_portable_exe.py
```

Or double-click/run:

```powershell
.\build_portable_exe.bat
```

The script creates:

```text
dist/
  CodexVault.exe
  CodexVaultBackend.exe
  CodexVault-portable/
    CodexVault.exe
    CodexVaultBackend.exe
    run_backend.bat
    README.md
    docs/
    LICENSE
  CodexVault-portable.zip
```

`LICENSE` is copied only when the repository contains one.

## Runtime Data

The packaged app stores runtime data under:

```text
%LOCALAPPDATA%\CodexVault
```

This includes:

- backups
- exports
- achievement state
- local auth and share-code metadata
- backend SQLite data

For test runs, override the data directory:

```powershell
$env:CODEXVAULT_DATA_DIR="C:\Temp\CodexVaultData"
.\dist\CodexVault-portable\CodexVault.exe
```

## Startup Diagnostics

At startup, the app reports diagnostics in the in-app status log for:

- missing achievement PNG assets
- an unusable or unwritable runtime data directory
- backend port conflicts on `127.0.0.1:8765`

The backend port warning means another Codex Vault backend or local service is already listening on the default beta port. The desktop app still opens, but backend smoke tests should resolve the conflict first.

## Smoke Test

Before packaging:

```powershell
python -B -m unittest discover -s tests -v
```

From the packaged folder:

```powershell
.\CodexVault.exe
.\run_backend.bat
```

Manual desktop smoke path:

1. Open `CodexVault.exe`.
2. Browse to `C:\Users\<user>\.codex`.
3. Scan.
4. Open Skills.
5. Open Memory.
6. Open Sync / Packs.
7. Export a pack.
8. Preview and import a pack.
9. Open Achievements.
10. Confirm achievement icons render.
11. Confirm the app closes cleanly from the top-right button.

## Notes

- The build intentionally avoids administrator privileges.
- The packaged app does not upload `.codex` content automatically.
- Keep README screenshots as PNG files under `docs/assets/`.
- Antivirus tools may flag fresh unsigned executables; provide the source-run fallback for testers when needed.
