from __future__ import annotations

import base64
import hashlib
import json
import secrets
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .core import import_pack


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class LocalAuthStore:
    """Local-only username/password store for Phase 2 simulation.

    This is intentionally not a cloud auth system. It exists so the MVP can
    exercise login, device state, and share-code ownership without networking.
    """

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.users_path = self.root / "users.json"
        self.sessions_path = self.root / "sessions.json"
        self.devices_path = self.root / "devices.json"

    def register(self, username: str, password: str) -> dict[str, str]:
        username = username.strip()
        if len(username) < 3:
            raise ValueError("Username must be at least 3 characters")
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters")
        users = read_json(self.users_path, {})
        if username in users:
            raise ValueError("Username already exists")
        salt = secrets.token_hex(16)
        users[username] = {
            "username": username,
            "salt": salt,
            "passwordHash": self._hash(password, salt),
            "createdAt": now_iso(),
        }
        write_json(self.users_path, users)
        return {"username": username, "createdAt": users[username]["createdAt"]}

    def login(self, username: str, password: str) -> dict[str, str]:
        users = read_json(self.users_path, {})
        user = users.get(username)
        if not user or self._hash(password, user["salt"]) != user["passwordHash"]:
            raise ValueError("Invalid username or password")
        token = secrets.token_urlsafe(24)
        sessions = read_json(self.sessions_path, {})
        sessions[token] = {"username": username, "createdAt": now_iso()}
        write_json(self.sessions_path, sessions)
        return {"username": username, "sessionToken": token}

    def register_device(self, session_token: str, name: str) -> dict[str, str]:
        username = self.username_for_session(session_token)
        devices = read_json(self.devices_path, {})
        device = {
            "id": secrets.token_hex(8),
            "username": username,
            "name": name.strip() or "Windows Device",
            "platform": "windows",
            "lastSeenAt": now_iso(),
        }
        devices.setdefault(username, []).append(device)
        write_json(self.devices_path, devices)
        return device

    def devices(self, username: str) -> list[dict[str, str]]:
        return read_json(self.devices_path, {}).get(username, [])

    def username_for_session(self, session_token: str) -> str:
        sessions = read_json(self.sessions_path, {})
        session = sessions.get(session_token)
        if not session:
            raise ValueError("Invalid session")
        return session["username"]

    @staticmethod
    def _hash(password: str, salt: str) -> str:
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
        return base64.b64encode(digest).decode("ascii")


class ShareCodeStore:
    """Local share-code registry.

    A code points to a copied pack under app data. This mimics Phase 2 share-code
    behavior without cloud storage or permissions.
    """

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.packs_dir = self.root / "packs"
        self.codes_path = self.root / "codes.json"

    def create_code(self, pack_path: str | Path, *, owner: str = "local", ttl_days: int = 30) -> str:
        pack = Path(pack_path).resolve()
        if not pack.exists():
            raise FileNotFoundError(f"Pack not found: {pack}")
        codes = read_json(self.codes_path, {})
        code = self._new_code(codes)
        self.packs_dir.mkdir(parents=True, exist_ok=True)
        stored_pack = self.packs_dir / f"{code}.codexvault.zip"
        shutil.copy2(pack, stored_pack)
        codes[code] = {
            "code": code,
            "owner": owner,
            "packPath": str(stored_pack),
            "createdAt": now_iso(),
            "ttlDays": ttl_days,
        }
        write_json(self.codes_path, codes)
        return code

    def resolve(self, code: str) -> dict[str, Any]:
        codes = read_json(self.codes_path, {})
        if code not in codes:
            raise ValueError("Share code not found")
        return codes[code]

    def import_code(self, code: str, target_root: str | Path) -> dict[str, Any]:
        record = self.resolve(code)
        result = import_pack(record["packPath"], target_root)
        result["code"] = code
        return result

    def all_codes(self) -> dict[str, Any]:
        return read_json(self.codes_path, {})

    @staticmethod
    def _new_code(existing: dict[str, Any]) -> str:
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        while True:
            code = "".join(secrets.choice(alphabet) for _ in range(8))
            if code not in existing:
                return code
