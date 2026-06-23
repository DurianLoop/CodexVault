from __future__ import annotations

import os
import socket
import sys
import tempfile
from pathlib import Path


APP_DIR_NAME = "CodexVault"
BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 8765


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resource_root() -> Path:
    bundled_root = getattr(sys, "_MEIPASS", None)
    if bundled_root:
        return Path(bundled_root)
    return project_root()


def resource_path(*parts: str) -> Path:
    return resource_root().joinpath(*parts)


def user_data_dir() -> Path:
    override = os.environ.get("CODEXVAULT_DATA_DIR")
    if override:
        return Path(override).expanduser()
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if base:
        return Path(base) / APP_DIR_NAME
    return Path.home() / f".{APP_DIR_NAME.lower()}"


DATA_DIR = user_data_dir()
BACKUP_DIR = DATA_DIR / "backups"
EXPORT_DIR = DATA_DIR / "exports"
STATE_FILE = DATA_DIR / "achievement_state.json"
IMPORT_HISTORY_FILE = DATA_DIR / "import_history.json"
BACKEND_DATA_DIR = DATA_DIR / "backend"
ACHIEVEMENT_ICON_DIR = resource_path("codexvault", "assets", "achievements")


def ensure_runtime_dirs() -> None:
    for path in [DATA_DIR, BACKUP_DIR, EXPORT_DIR, BACKEND_DATA_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def _is_writable_directory(path: Path) -> bool:
    path.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.NamedTemporaryFile(prefix=".codexvault-", dir=path, delete=True):
            return True
    except OSError:
        return False


def _port_is_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex((host, port)) == 0


def startup_diagnostics() -> list[str]:
    issues: list[str] = []
    try:
        if not _is_writable_directory(DATA_DIR):
            issues.append(f"Data directory is not writable: {DATA_DIR}")
    except OSError as exc:
        issues.append(f"Data directory is not usable: {DATA_DIR} ({exc})")

    missing_icons = [
        ACHIEVEMENT_ICON_DIR / f"ach_{index:02d}_{variant}.png"
        for index in range(25)
        for variant in ["card", "detail"]
        if not (ACHIEVEMENT_ICON_DIR / f"ach_{index:02d}_{variant}.png").exists()
    ]
    if missing_icons:
        issues.append(f"Missing achievement PNG assets: {len(missing_icons)} expected files were not found.")

    if _port_is_in_use(BACKEND_HOST, BACKEND_PORT):
        issues.append(f"Backend port already in use: {BACKEND_HOST}:{BACKEND_PORT}")
    return issues
