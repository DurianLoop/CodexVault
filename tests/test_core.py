import json
import shutil
import tempfile
import unittest
import uuid
import zipfile
from contextlib import contextmanager
from pathlib import Path

from codexvault.achievements import AchievementEngine, default_achievements
from codexvault.core import (
    create_backup,
    export_pack,
    import_pack,
    preview_import_pack,
    restore_backup,
    scan_codex,
)


class CodexVaultCoreTests(unittest.TestCase):
    @contextmanager
    def tempdir(self):
        base = Path.cwd() / ".test-tmp"
        base.mkdir(exist_ok=True)
        path = base / f"case-{uuid.uuid4().hex}"
        path.mkdir()
        try:
            yield str(path)
        finally:
            shutil.rmtree(path, ignore_errors=True)

    def make_codex_tree(self, root: Path) -> Path:
        codex = root / ".codex"
        (codex / "memories").mkdir(parents=True)
        (codex / "skills" / "pdf").mkdir(parents=True)
        (codex / "prompts").mkdir(parents=True)
        (codex / "rules").mkdir(parents=True)
        (codex / "plugins").mkdir(parents=True)
        (codex / "sessions").mkdir(parents=True)
        (codex / "memories" / "MEMORY.md").write_text("Decision log", encoding="utf-8")
        (codex / "skills" / "pdf" / "SKILL.md").write_text("---\nname: pdf\n---", encoding="utf-8")
        (codex / "prompts" / "global.md").write_text("Be concise", encoding="utf-8")
        (codex / "rules" / "general.md").write_text("Prefer tests", encoding="utf-8")
        (codex / "plugins" / "plugin.json").write_text('{"name":"demo"}', encoding="utf-8")
        (codex / "config.toml").write_text("[model]\nname='demo'\n", encoding="utf-8")
        (codex / "auth.json").write_text('{"api_key":"sk-secret"}', encoding="utf-8")
        (codex / "sessions" / "trace.log").write_text("large volatile log", encoding="utf-8")
        return codex

    def test_scan_codex_classifies_assets_and_sensitive_files(self):
        with self.tempdir() as tmp:
            codex = self.make_codex_tree(Path(tmp))

            scan = scan_codex(codex)

            self.assertEqual(scan.root, codex)
            self.assertEqual(scan.counts["memories"], 1)
            self.assertEqual(scan.counts["skills"], 1)
            self.assertEqual(scan.counts["prompts"], 1)
            self.assertEqual(scan.counts["rules"], 1)
            self.assertEqual(scan.counts["plugins"], 1)
            self.assertGreaterEqual(scan.total_files, 7)
            self.assertIn("auth.json", [item.relative_path for item in scan.sensitive_items])
            self.assertIn("sessions/trace.log", [item.relative_path for item in scan.volatile_items])

    def test_export_pack_writes_manifest_and_excludes_risky_files_by_default(self):
        with self.tempdir() as tmp:
            root = Path(tmp)
            codex = self.make_codex_tree(root)
            output_zip = root / "vault.codexvault.zip"

            manifest = export_pack(codex, output_zip, author="tester")

            self.assertTrue(output_zip.exists())
            self.assertEqual(manifest["schemaVersion"], "1.0.0")
            with zipfile.ZipFile(output_zip) as pack:
                names = set(pack.namelist())
                self.assertIn("manifest.json", names)
                self.assertIn("memories/MEMORY.md", names)
                self.assertIn("skills/pdf/SKILL.md", names)
                self.assertNotIn("auth.json", names)
                self.assertNotIn("sessions/trace.log", names)
                saved_manifest = json.loads(pack.read("manifest.json").decode("utf-8"))
            exported_types = {item["type"] for item in saved_manifest["items"]}
            self.assertIn("memory", exported_types)
            self.assertIn("skill", exported_types)

    def test_backup_and_import_restore_managed_assets_without_credentials(self):
        with self.tempdir() as tmp:
            root = Path(tmp)
            codex = self.make_codex_tree(root)
            backup_dir = root / "backups"

            backup_path = create_backup(codex, backup_dir, reason="unit-test")

            self.assertTrue((backup_path / "manifest.json").exists())
            self.assertTrue((backup_path / "memories" / "MEMORY.md").exists())
            self.assertFalse((backup_path / "auth.json").exists())

            pack_path = root / "vault.codexvault.zip"
            export_pack(codex, pack_path, author="tester")
            target = root / "target-codex"
            result = import_pack(pack_path, target)

            self.assertTrue((target / "memories" / "MEMORY.md").exists())
            self.assertTrue((target / "skills" / "pdf" / "SKILL.md").exists())
            self.assertFalse((target / "auth.json").exists())
            self.assertGreaterEqual(result["imported"], 4)

    def test_import_preview_reports_add_replace_skip_before_writing(self):
        with self.tempdir() as tmp:
            root = Path(tmp)
            codex = self.make_codex_tree(root)
            pack_path = root / "vault.codexvault.zip"
            export_pack(codex, pack_path, author="tester")

            target = root / "target-codex"
            (target / "memories").mkdir(parents=True)
            (target / "memories" / "MEMORY.md").write_text("old content", encoding="utf-8")

            preview = preview_import_pack(pack_path, target)

            self.assertIn("memories/MEMORY.md", preview["replaced"])
            self.assertIn("skills/pdf/SKILL.md", preview["added"])
            self.assertEqual(preview["skipped"], [])
            self.assertIn("markdownDiff", next(item for item in preview["files"] if item["path"] == "memories/MEMORY.md"))
            self.assertFalse((target / "skills" / "pdf" / "SKILL.md").exists())

    def test_import_actions_support_skip_replace_rename_and_history(self):
        with self.tempdir() as tmp:
            root = Path(tmp)
            codex = self.make_codex_tree(root)
            pack_path = root / "vault.codexvault.zip"
            export_pack(codex, pack_path, author="tester")
            target = root / "target-codex"
            (target / "memories").mkdir(parents=True)
            (target / "memories" / "MEMORY.md").write_text("old content", encoding="utf-8")
            history = root / "history.json"

            result = import_pack(
                pack_path,
                target,
                actions={
                    "memories/MEMORY.md": "skip",
                    "skills/pdf/SKILL.md": {"action": "rename", "target": "skills/pdf/SKILL.imported.md"},
                },
                history_path=history,
                backup_path=root / "backups" / "backup-1",
            )

            self.assertEqual((target / "memories" / "MEMORY.md").read_text(encoding="utf-8"), "old content")
            self.assertTrue((target / "skills" / "pdf" / "SKILL.imported.md").exists())
            self.assertGreaterEqual(result["skipped"], 1)
            self.assertEqual(result["renamed"], 1)
            saved = json.loads(history.read_text(encoding="utf-8"))
            self.assertEqual(saved[-1]["result"]["renamed"], 1)

    def test_import_preview_warns_unknown_folders_and_blocks_path_traversal(self):
        with self.tempdir() as tmp:
            root = Path(tmp)
            pack_path = root / "custom.codexvault.zip"
            manifest = {
                "name": "Custom",
                "author": "tester",
                "schemaVersion": "1.0.0",
                "items": [
                    {"relative_path": "mystery/file.md", "type": "other", "size": 5, "sha256": "x", "modified_at": ""},
                    {"relative_path": "../escape.md", "type": "other", "size": 6, "sha256": "x", "modified_at": ""},
                ],
            }
            with zipfile.ZipFile(pack_path, "w") as pack:
                pack.writestr("manifest.json", json.dumps(manifest))
                pack.writestr("mystery/file.md", "hello")
                pack.writestr("../escape.md", "escape")

            preview = preview_import_pack(pack_path, root / "target")

            self.assertIn("mystery/file.md", preview["added"])
            self.assertEqual(preview["warnings"][0]["kind"], "unknown-folder")
            self.assertEqual(preview["skipped"][0]["reason"], "unsafe path")

            result = import_pack(pack_path, root / "target")
            self.assertTrue((root / "target" / "mystery" / "file.md").exists())
            self.assertFalse((root / "escape.md").exists())
            self.assertEqual(result["skipped"], 1)

    def test_restore_backup_recovers_files_from_backup_point(self):
        with self.tempdir() as tmp:
            root = Path(tmp)
            codex = self.make_codex_tree(root)
            backup_path = create_backup(codex, root / "backups", reason="rollback-test")
            (codex / "memories" / "MEMORY.md").write_text("broken", encoding="utf-8")

            result = restore_backup(backup_path, codex)

            self.assertGreaterEqual(result["restored"], 4)
            self.assertEqual((codex / "memories" / "MEMORY.md").read_text(encoding="utf-8"), "Decision log")
            self.assertFalse((codex / "auth.json").read_text(encoding="utf-8") == "Decision log")

    def test_achievement_engine_unlocks_scan_and_asset_milestones(self):
        engine = AchievementEngine(default_achievements())
        unlocked = engine.evaluate(
            {
                "event": "scan.completed",
                "counts": {
                    "memories": 10,
                    "skills": 5,
                    "prompts": 3,
                    "project_presets": 3,
                    "backups": 1,
                },
                "health_issues_fixed": 5,
                "sensitive_blocks": 1,
            }
        )

        ids = {item["id"] for item in unlocked}
        self.assertIn("hello_world", ids)
        self.assertIn("memory_curator", ids)
        self.assertIn("skill_collector", ids)
        self.assertIn("project_presetter", ids)
        self.assertIn("safety_gatekeeper", ids)


if __name__ == "__main__":
    unittest.main()
