from __future__ import annotations

import base64
import hashlib
import json
import secrets
import sqlite3
import threading
from contextlib import closing
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class BackendDb:
    def __init__(self, root: str | Path, *, memory: bool = False):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.pack_dir = self.root / "packs"
        self.pack_dir.mkdir(parents=True, exist_ok=True)
        self.memory = memory
        self.path = "file:codex_vault_backend?mode=memory&cache=shared" if memory else str(self.root / "codex_vault.sqlite")
        self.anchor = sqlite3.connect(self.path, uri=self.memory) if self.memory else None
        if self.anchor:
            self.anchor.row_factory = sqlite3.Row
        self.init()

    def connect(self):
        conn = sqlite3.connect(self.path, uri=self.memory)
        conn.row_factory = sqlite3.Row
        return conn

    def init(self) -> None:
        with closing(self.connect()) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    salt TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS devices (
                    id TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    name TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS packs (
                    id TEXT PRIMARY KEY,
                    owner TEXT NOT NULL,
                    name TEXT NOT NULL,
                    path TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS share_codes (
                    code TEXT PRIMARY KEY,
                    pack_id TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    visibility TEXT NOT NULL
                );
                """
            )
            conn.commit()

    def register(self, username: str, password: str) -> dict[str, str]:
        if len(username) < 3 or len(password) < 8:
            raise ValueError("username>=3 and password>=8 required")
        salt = secrets.token_hex(16)
        password_hash = self.hash_password(password, salt)
        with closing(self.connect()) as conn:
            conn.execute(
                "INSERT INTO users(username, salt, password_hash, created_at) VALUES(?, ?, ?, ?)",
                (username, salt, password_hash, now_iso()),
            )
            conn.commit()
        return {"username": username}

    def login(self, username: str, password: str) -> dict[str, str]:
        with closing(self.connect()) as conn:
            row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
            if not row or self.hash_password(password, row["salt"]) != row["password_hash"]:
                raise ValueError("invalid credentials")
            token = secrets.token_urlsafe(24)
            conn.execute("INSERT INTO sessions(token, username, created_at) VALUES(?, ?, ?)", (token, username, now_iso()))
            conn.commit()
        return {"username": username, "token": token}

    def username_for_token(self, token: str) -> str:
        with closing(self.connect()) as conn:
            row = conn.execute("SELECT username FROM sessions WHERE token=?", (token,)).fetchone()
        if not row:
            raise PermissionError("invalid token")
        return row["username"]

    def add_device(self, token: str, name: str) -> dict[str, str]:
        username = self.username_for_token(token)
        device = {
            "id": secrets.token_hex(8),
            "username": username,
            "name": name or "Windows Device",
            "platform": "windows",
            "lastSeenAt": now_iso(),
        }
        with closing(self.connect()) as conn:
            conn.execute(
                "INSERT INTO devices(id, username, name, platform, last_seen_at) VALUES(?, ?, ?, ?, ?)",
                (device["id"], username, device["name"], device["platform"], device["lastSeenAt"]),
            )
            conn.commit()
        return device

    def add_pack(self, token: str, name: str, content: bytes) -> dict[str, str]:
        username = self.username_for_token(token)
        pack_id = secrets.token_hex(10)
        pack_path = self.pack_dir / f"{pack_id}.codexvault.zip"
        pack_path.write_bytes(content)
        code = self.new_code()
        with closing(self.connect()) as conn:
            conn.execute(
                "INSERT INTO packs(id, owner, name, path, created_at) VALUES(?, ?, ?, ?, ?)",
                (pack_id, username, name or "Codex Vault Pack", str(pack_path), now_iso()),
            )
            conn.execute(
                "INSERT INTO share_codes(code, pack_id, owner, created_at, visibility) VALUES(?, ?, ?, ?, ?)",
                (code, pack_id, username, now_iso(), "public"),
            )
            conn.commit()
        return {"packId": pack_id, "shareCode": code}

    def share_info(self, code: str) -> dict[str, str]:
        with closing(self.connect()) as conn:
            row = conn.execute(
                "SELECT s.code, s.owner, s.created_at, p.name FROM share_codes s JOIN packs p ON p.id=s.pack_id WHERE s.code=?",
                (code,),
            ).fetchone()
        if not row:
            raise KeyError("share code not found")
        return {"code": row["code"], "owner": row["owner"], "createdAt": row["created_at"], "name": row["name"]}

    def download_pack(self, token: str, code: str) -> dict[str, str]:
        self.username_for_token(token)
        with closing(self.connect()) as conn:
            row = conn.execute(
                "SELECT p.name, p.path FROM share_codes s JOIN packs p ON p.id=s.pack_id WHERE s.code=?",
                (code,),
            ).fetchone()
        if not row:
            raise KeyError("share code not found")
        content = Path(row["path"]).read_bytes()
        return {"name": row["name"], "contentBase64": base64.b64encode(content).decode("ascii")}

    def new_code(self) -> str:
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        with closing(self.connect()) as conn:
            while True:
                code = "".join(secrets.choice(alphabet) for _ in range(8))
                if not conn.execute("SELECT 1 FROM share_codes WHERE code=?", (code,)).fetchone():
                    return code

    def close(self) -> None:
        if self.anchor:
            self.anchor.close()
            self.anchor = None

    @staticmethod
    def hash_password(password: str, salt: str) -> str:
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
        return base64.b64encode(digest).decode("ascii")


class BackendServer:
    def __init__(self, root: str | Path, host: str = "127.0.0.1", port: int = 8765, *, memory_db: bool = False):
        self.root = Path(root)
        self.db = BackendDb(self.root, memory=memory_db)
        self.host = host
        self.port = port
        self.httpd: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None

    @property
    def base_url(self) -> str:
        if not self.httpd:
            return f"http://{self.host}:{self.port}"
        host, port = self.httpd.server_address
        return f"http://{host}:{port}"

    def make_handler(self):
        db = self.db

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, _format, *args):  # noqa: N802
                return

            def do_GET(self):  # noqa: N802
                try:
                    parsed = urlparse(self.path)
                    if parsed.path.startswith("/api/share-codes/"):
                        code = parsed.path.rsplit("/", 1)[-1]
                        self.send_json(db.share_info(code))
                        return
                    if parsed.path.startswith("/api/packs/") and parsed.path.endswith("/download"):
                        code = parsed.path.split("/")[-2]
                        self.send_json(db.download_pack(self.bearer_token(), code))
                        return
                    if parsed.path == "/api/health":
                        self.send_json({"ok": True, "time": now_iso()})
                        return
                    self.send_error_json(404, "not found")
                except Exception as exc:
                    self.send_error_json(400, str(exc))

            def do_POST(self):  # noqa: N802
                try:
                    payload = self.read_json()
                    if self.path == "/api/register":
                        self.send_json(db.register(payload.get("username", ""), payload.get("password", "")))
                        return
                    if self.path == "/api/login":
                        self.send_json(db.login(payload.get("username", ""), payload.get("password", "")))
                        return
                    if self.path == "/api/devices":
                        self.send_json(db.add_device(self.bearer_token(), payload.get("name", "")))
                        return
                    if self.path == "/api/packs":
                        content = base64.b64decode(payload.get("contentBase64", ""))
                        self.send_json(db.add_pack(self.bearer_token(), payload.get("name", ""), content))
                        return
                    self.send_error_json(404, "not found")
                except Exception as exc:
                    self.send_error_json(400, str(exc))

            def read_json(self) -> dict[str, Any]:
                length = int(self.headers.get("Content-Length", "0"))
                if length == 0:
                    return {}
                return json.loads(self.rfile.read(length).decode("utf-8"))

            def bearer_token(self) -> str:
                header = self.headers.get("Authorization", "")
                if not header.startswith("Bearer "):
                    raise PermissionError("missing bearer token")
                return header.split(" ", 1)[1]

            def send_json(self, payload: dict[str, Any]) -> None:
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def send_error_json(self, code: int, message: str) -> None:
                body = json.dumps({"error": message}, ensure_ascii=False).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        return Handler

    def start_in_thread(self) -> None:
        self.httpd = ThreadingHTTPServer((self.host, self.port), self.make_handler())
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def serve_forever(self) -> None:
        self.httpd = ThreadingHTTPServer((self.host, self.port), self.make_handler())
        self.httpd.serve_forever()

    def stop(self) -> None:
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
        if self.thread:
            self.thread.join(timeout=5)
        self.db.close()


def main() -> int:
    root = Path(__file__).resolve().parents[1] / "data" / "backend"
    server = BackendServer(root, host="127.0.0.1", port=8765)
    print(f"Codex Vault backend listening on http://127.0.0.1:8765")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
