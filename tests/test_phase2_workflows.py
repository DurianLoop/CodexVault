import json
import shutil
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

from codexvault.core import export_pack
from codexvault.phase2 import LocalAuthStore, ShareCodeStore
from codexvault.workflow import (
    CodexVaultWorkflow,
    edit_memory_file,
    list_memories,
    list_skills,
)


class Phase2WorkflowTests(unittest.TestCase):
    @contextmanager
    def tempdir(self):
        base = Path.cwd() / ".test-tmp"
        base.mkdir(exist_ok=True)
        path = base / f"case-{uuid.uuid4().hex}"
        path.mkdir()
        try:
            yield path
        finally:
            shutil.rmtree(path, ignore_errors=True)

    def make_codex_tree(self, root: Path) -> Path:
        codex = root / ".codex"
        (codex / "skills" / "valid").mkdir(parents=True)
        (codex / "skills" / "invalid").mkdir(parents=True)
        (codex / "memories").mkdir(parents=True)
        (codex / "skills" / "valid" / "SKILL.md").write_text(
            "---\nname: valid\ndescription: Demo skill\n---\n# Valid\n", encoding="utf-8"
        )
        (codex / "skills" / "invalid" / "notes.md").write_text("missing skill file", encoding="utf-8")
        (codex / "memories" / "MEMORY.md").write_text("original memory", encoding="utf-8")
        return codex

    def test_skill_listing_only_reports_skill_directories_and_validity(self):
        with self.tempdir() as root:
            codex = self.make_codex_tree(root)

            skills = list_skills(codex)

            self.assertEqual({skill.name for skill in skills}, {"valid", "invalid"})
            validity = {skill.name: skill.valid for skill in skills}
            self.assertTrue(validity["valid"])
            self.assertFalse(validity["invalid"])
            preview = next(skill for skill in skills if skill.name == "valid").preview
            self.assertIn("# Valid", preview)

    def test_memory_listing_and_editing_updates_markdown_file(self):
        with self.tempdir() as root:
            codex = self.make_codex_tree(root)

            memories = list_memories(codex)
            self.assertEqual(len(memories), 1)
            self.assertEqual(memories[0].content, "original memory")

            edit_memory_file(codex, "memories/MEMORY.md", "updated memory")

            self.assertEqual((codex / "memories" / "MEMORY.md").read_text(encoding="utf-8"), "updated memory")

    def test_local_auth_registers_login_and_device_without_network(self):
        with self.tempdir() as root:
            store = LocalAuthStore(root / "auth")

            profile = store.register("alice", "correct horse battery staple")
            login = store.login("alice", "correct horse battery staple")
            device = store.register_device(login["sessionToken"], "Windows Dev Box")

            self.assertEqual(profile["username"], "alice")
            self.assertEqual(login["username"], "alice")
            self.assertEqual(device["name"], "Windows Dev Box")
            self.assertEqual(len(store.devices("alice")), 1)

    def test_share_code_round_trip_imports_pack(self):
        with self.tempdir() as root:
            codex = self.make_codex_tree(root)
            pack = root / "demo.codexvault.zip"
            export_pack(codex, pack, author="alice")
            store = ShareCodeStore(root / "share")

            code = store.create_code(pack, owner="alice")
            target = root / "target"
            result = store.import_code(code, target)

            self.assertEqual(len(code), 8)
            self.assertGreaterEqual(result["imported"], 2)
            self.assertTrue((target / "skills" / "valid" / "SKILL.md").exists())
            self.assertTrue((target / "memories" / "MEMORY.md").exists())

    def test_workflow_runs_export_import_backup_and_share_without_gui_clicks(self):
        with self.tempdir() as root:
            codex = self.make_codex_tree(root)
            app_data = root / "data"
            workflow = CodexVaultWorkflow(codex, app_data)

            scan = workflow.scan()
            backup = workflow.create_backup()
            pack = workflow.export_pack()
            code = workflow.create_share_code(pack)
            target = root / "target"
            imported = workflow.import_share_code(code, target)

            self.assertEqual(scan.counts["skills"], 2)
            self.assertTrue((backup / "manifest.json").exists())
            self.assertTrue(pack.exists())
            self.assertGreaterEqual(imported["imported"], 2)
            self.assertTrue((target / "memories" / "MEMORY.md").exists())
            state = json.loads((app_data / "share_codes" / "codes.json").read_text(encoding="utf-8"))
            self.assertIn(code, state)


if __name__ == "__main__":
    unittest.main()
