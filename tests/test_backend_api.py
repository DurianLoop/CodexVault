import base64
import json
import shutil
import tempfile
import time
import unittest
import urllib.request
import uuid
from contextlib import contextmanager
from pathlib import Path

from codexvault.backend import BackendServer
from codexvault.core import export_pack


class BackendApiTests(unittest.TestCase):
    @contextmanager
    def tempdir(self):
        base = Path.cwd() / "backend-test-tmp"
        base.mkdir(exist_ok=True)
        path = base / f"backend-{uuid.uuid4().hex}"
        path.mkdir()
        try:
            yield path
        finally:
            shutil.rmtree(path, ignore_errors=True)

    def post_json(self, base_url: str, path: str, payload: dict, token: str | None = None) -> dict:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{base_url}{path}",
            data=body,
            headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))

    def get_json(self, base_url: str, path: str, token: str | None = None) -> dict:
        req = urllib.request.Request(
            f"{base_url}{path}",
            headers={"Authorization": f"Bearer {token}"} if token else {},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))

    def make_pack(self, root: Path) -> Path:
        codex = root / ".codex"
        (codex / "skills" / "demo").mkdir(parents=True)
        (codex / "memories").mkdir(parents=True)
        (codex / "skills" / "demo" / "SKILL.md").write_text("---\nname: demo\n---", encoding="utf-8")
        (codex / "memories" / "MEMORY.md").write_text("memory", encoding="utf-8")
        pack = root / "pack.zip"
        export_pack(codex, pack, author="api")
        return pack

    def test_backend_register_login_device_upload_share_download(self):
        with self.tempdir() as root:
            server = BackendServer(root / "server", host="127.0.0.1", port=0, memory_db=True)
            server.start_in_thread()
            try:
                base = server.base_url
                register = self.post_json(base, "/api/register", {"username": "alice", "password": "correct horse"})
                self.assertEqual(register["username"], "alice")
                login = self.post_json(base, "/api/login", {"username": "alice", "password": "correct horse"})
                token = login["token"]
                device = self.post_json(base, "/api/devices", {"name": "Laptop"}, token)
                self.assertEqual(device["name"], "Laptop")

                pack = self.make_pack(root)
                encoded = base64.b64encode(pack.read_bytes()).decode("ascii")
                uploaded = self.post_json(base, "/api/packs", {"name": "Demo Pack", "contentBase64": encoded}, token)
                code = uploaded["shareCode"]
                self.assertEqual(len(code), 8)

                public = self.get_json(base, f"/api/share-codes/{code}")
                self.assertEqual(public["name"], "Demo Pack")
                downloaded = self.get_json(base, f"/api/packs/{code}/download", token)
                self.assertEqual(base64.b64decode(downloaded["contentBase64"]), pack.read_bytes())
            finally:
                server.stop()


if __name__ == "__main__":
    unittest.main()
