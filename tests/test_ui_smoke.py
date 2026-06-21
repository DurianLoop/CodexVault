import shutil
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

from codexvault.ui_app import CodexVaultApp


class UiSmokeTests(unittest.TestCase):
    @contextmanager
    def temp_codex(self):
        base = Path.cwd() / ".test-tmp"
        base.mkdir(exist_ok=True)
        root = base / f"ui-{uuid.uuid4().hex}"
        codex = root / ".codex"
        (codex / "skills" / "demo").mkdir(parents=True)
        (codex / "memories").mkdir(parents=True)
        (codex / "skills" / "demo" / "SKILL.md").write_text("---\nname: demo\n---\n# Demo", encoding="utf-8")
        (codex / "memories" / "MEMORY.md").write_text("hello", encoding="utf-8")
        try:
            yield codex
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_ui_can_scan_and_switch_all_views_hidden(self):
        with self.temp_codex() as codex:
            app = CodexVaultApp()
            app.withdraw()
            try:
                app.path_var.set(str(codex))
                app.refresh_all()
                for view in ["overview", "skills", "memory", "sync", "achievements", "account"]:
                    app.show_view(view)
                    app.update_idletasks()
                self.assertEqual(len(app.skills), 1)
                self.assertEqual(len(app.memories), 1)
                self.assertIn("skills", app.metric_labels)
            finally:
                app.destroy()


if __name__ == "__main__":
    unittest.main()
