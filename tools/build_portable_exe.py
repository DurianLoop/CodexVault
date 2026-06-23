from __future__ import annotations

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"
PORTABLE_DIR = DIST_DIR / "CodexVault-portable"
ZIP_PATH = DIST_DIR / "CodexVault-portable.zip"
ACHIEVEMENT_ASSET_DIR = ROOT / "codexvault" / "assets" / "achievements"


def pyinstaller_data_arg(source: Path, target: str) -> str:
    separator = ";" if sys.platform.startswith("win") else ":"
    return f"{source}{separator}{target}"


def require_pyinstaller() -> None:
    try:
        import PyInstaller  # noqa: F401
    except ImportError as exc:
        raise SystemExit(
            "PyInstaller is required for the portable beta build.\n"
            "Install it with: python -m pip install pyinstaller"
        ) from exc


def validate_assets() -> None:
    missing = [
        ACHIEVEMENT_ASSET_DIR / f"ach_{index:02d}_{variant}.png"
        for index in range(25)
        for variant in ["card", "detail"]
        if not (ACHIEVEMENT_ASSET_DIR / f"ach_{index:02d}_{variant}.png").exists()
    ]
    if missing:
        names = "\n".join(f"- {path}" for path in missing[:10])
        raise SystemExit(f"Missing achievement PNG assets ({len(missing)}):\n{names}")


def run_pyinstaller(name: str, entrypoint: Path, *, windowed: bool) -> None:
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name",
        name,
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(BUILD_DIR),
        "--specpath",
        str(BUILD_DIR),
        "--add-data",
        pyinstaller_data_arg(ROOT / "codexvault" / "assets", "codexvault/assets"),
    ]
    if windowed:
        command.append("--windowed")
    command.append(str(entrypoint))
    subprocess.run(command, cwd=ROOT, check=True)


def copy_tree(source: Path, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
    shutil.copytree(source, target, ignore=ignore)


def write_backend_launcher() -> None:
    (PORTABLE_DIR / "run_backend.bat").write_text(
        '@echo off\r\n'
        "setlocal\r\n"
        'cd /d "%~dp0"\r\n'
        'CodexVaultBackend.exe\r\n'
        "endlocal\r\n",
        encoding="utf-8",
    )


def assemble_portable_folder() -> None:
    if PORTABLE_DIR.exists():
        shutil.rmtree(PORTABLE_DIR)
    PORTABLE_DIR.mkdir(parents=True)

    shutil.copy2(DIST_DIR / "CodexVault.exe", PORTABLE_DIR / "CodexVault.exe")
    shutil.copy2(DIST_DIR / "CodexVaultBackend.exe", PORTABLE_DIR / "CodexVaultBackend.exe")
    write_backend_launcher()
    shutil.copy2(ROOT / "README.md", PORTABLE_DIR / "README.md")
    copy_tree(ROOT / "docs", PORTABLE_DIR / "docs")
    license_path = ROOT / "LICENSE"
    if license_path.exists():
        shutil.copy2(license_path, PORTABLE_DIR / "LICENSE")


def zip_portable_folder() -> None:
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(PORTABLE_DIR.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(PORTABLE_DIR.parent))


def main() -> int:
    require_pyinstaller()
    validate_assets()
    DIST_DIR.mkdir(exist_ok=True)
    run_pyinstaller("CodexVault", ROOT / "codexvault" / "desktop_entry.py", windowed=True)
    run_pyinstaller("CodexVaultBackend", ROOT / "codexvault" / "backend_entry.py", windowed=False)
    assemble_portable_folder()
    zip_portable_folder()
    print(f"Built portable folder: {PORTABLE_DIR}")
    print(f"Built portable zip:    {ZIP_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
