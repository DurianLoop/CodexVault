import shutil
import time
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
                self.assertIn("Scan complete", app.status_var.get())
                for view in ["overview", "skills", "memory", "sync", "achievements", "account"]:
                    app.show_view(view)
                    app.update_idletasks()
                self.assertTrue(callable(app.state))
                app._restore_chrome_after_minimize()
                self.assertIn("Viewing Account", app.status_var.get())
                self.assertEqual(len(app.skills), 1)
                self.assertEqual(len(app.memories), 1)
                self.assertIn("skills", app.metric_labels)
            finally:
                app.destroy()

    def test_achievement_rows_show_description_without_detail_click(self):
        app = CodexVaultApp()
        app.withdraw()
        try:
            app.show_view("achievements")
            app.update_idletasks()
            app.render_achievements()
            self.assertEqual(app.achievement_index_at_point(24, 86), 0)
            self.assertIn("完成第一次 .codex 扫描", app.achievement_canvas.itemcget(app.achievement_description_items[0], "text"))
            self.assertFalse(app.detail_overlay.place_info())
            self.assertIsNone(app.achievement_index_at_point(4, 4))
        finally:
            app.destroy()

    def test_achievement_activation_button_records_state_and_animation(self):
        app = CodexVaultApp()
        app.withdraw()
        try:
            app.engine.unlocked_ids = {"hello_world"}
            app.activated_achievement_ids.clear()
            app.persist_state = lambda: None
            app.show_view("achievements")
            app.update_idletasks()
            app.render_achievements()
            x1, y1, x2, y2 = app.achievement_activate_bounds[0]
            self.assertEqual(app.achievement_activation_index_at_point((x1 + x2) // 2, (y1 + y2) // 2), 0)
            app.on_achievement_canvas_click(type("Click", (), {"x": (x1 + x2) // 2, "y": (y1 + y2) // 2})())
            app.update_idletasks()
            self.assertIn("hello_world", app.activated_achievement_ids)
            self.assertEqual(app.activation_animation_target, 0)
            self.assertGreater(len(app.activation_animation_items), 0)
        finally:
            app.destroy()

    def test_unachieved_achievement_cannot_be_activated(self):
        app = CodexVaultApp()
        app.withdraw()
        try:
            app.engine.unlocked_ids = set()
            app.activated_achievement_ids.clear()
            app.persist_state = lambda: None
            app.show_view("achievements")
            app.update_idletasks()
            app.render_achievements()
            self.assertIn(1, app.achievement_button_bounds)
            self.assertNotIn(1, app.achievement_activate_bounds)
            x1, y1, x2, y2 = app.achievement_button_bounds[1]
            app.on_achievement_canvas_click(type("Click", (), {"x": (x1 + x2) // 2, "y": (y1 + y2) // 2})())
            app.update_idletasks()
            self.assertNotIn("prompt_engineer", app.activated_achievement_ids)
            self.assertIsNone(app.activation_animation_target)
        finally:
            app.destroy()

    def test_achievement_rows_adapt_to_wide_canvas(self):
        app = CodexVaultApp()
        app.withdraw()
        try:
            app.geometry("1800x1000")
            app.engine.unlocked_ids = {"hello_world"}
            app.show_view("achievements")
            app.achievement_canvas.configure(width=1500)
            app.update_idletasks()
            app.render_achievements()
            row_x1, _row_y1, row_x2, _row_y2 = app.achievement_bounds[0]
            btn_x1, _btn_y1, btn_x2, _btn_y2 = app.achievement_button_bounds[0]
            progress_x1, _progress_y1, progress_x2, _progress_y2 = app.achievement_progress_bounds[0]
            self.assertGreater(row_x2 - row_x1, 1200)
            self.assertLess(row_x2 - btn_x2, 60)
            self.assertGreater(btn_x2 - btn_x1, 120)
            self.assertGreater(progress_x2 - progress_x1, 800)
        finally:
            app.destroy()

    def test_achievement_filter_controls_by_status_and_rarity(self):
        app = CodexVaultApp()
        app.withdraw()
        try:
            app.engine.unlocked_ids = {"hello_world"}
            app.set_achievement_filter("已达成")
            self.assertEqual([item.id for item in app.filtered_achievements()], ["hello_world"])
            app.set_achievement_filter("未达成")
            self.assertNotIn("hello_world", [item.id for item in app.filtered_achievements()])
            app.set_achievement_filter("稀有")
            self.assertTrue(all(item.rarity == "稀有" for item in app.filtered_achievements()))
        finally:
            app.destroy()

    def test_achievement_icons_load_from_asset_set(self):
        app = CodexVaultApp()
        app.withdraw()
        try:
            self.assertEqual(len(app.achievement_icon_images), 25)
            app.show_view("achievements")
            app.update_idletasks()
            app.render_achievements()
            self.assertEqual(len(app.achievement_icon_items), 25)
        finally:
            app.destroy()

    def test_close_window_command_destroys_root(self):
        app = CodexVaultApp()
        app.withdraw()
        app.request_close()
        self.assertTrue(app._close_requested)

    def test_bottom_status_log_records_feedback(self):
        app = CodexVaultApp()
        app.withdraw()
        try:
            app.notify("Queued background export", "info", "Task queued")
            app.update_idletasks()
            text = app.status_log.get("1.0", "end")
            self.assertIn("Queued background export", text)
        finally:
            app.destroy()

    def test_notify_uses_in_app_toast_feedback(self):
        app = CodexVaultApp()
        app.withdraw()
        try:
            app.notify("Saved locally", "success")
            app.update_idletasks()
            self.assertGreaterEqual(len(app.toast_messages), 1)
            self.assertIn("Saved locally", app.toast_messages[-1]["message"])
        finally:
            app.destroy()

    def test_toast_host_stays_hidden_when_empty(self):
        app = CodexVaultApp()
        app.withdraw()
        try:
            self.assertFalse(app.toast_host.place_info())
            app.notify("Brief notice", "info", timeout_ms=20)
            app.update_idletasks()
            self.assertTrue(app.toast_host.place_info())
            deadline = time.time() + 1
            while app.toast_host.place_info() and time.time() < deadline:
                app.update()
                time.sleep(0.01)
            self.assertFalse(app.toast_host.place_info())
        finally:
            app.destroy()

    def test_achievements_canvas_supports_scrolling_to_bottom(self):
        app = CodexVaultApp()
        app.withdraw()
        try:
            app.show_view("achievements")
            app.update_idletasks()
            app.render_achievements()
            self.assertTrue(hasattr(app, "achievement_scrollbar"))
            self.assertEqual(app.achievement_scrollbar.cget("style"), "Vault.Vertical.TScrollbar")
            self.assertNotEqual(app.achievement_canvas.cget("yscrollcommand"), "")
            scrollregion = [int(float(value)) for value in app.achievement_canvas.cget("scrollregion").split()]
            self.assertGreaterEqual(scrollregion[3], max(y2 for *_xy, y2 in app.achievement_bounds.values()))
            app.achievement_canvas.yview_moveto(1.0)
            self.assertGreater(app.achievement_canvas.yview()[0], 0)
        finally:
            app.destroy()

    def test_background_scan_updates_ui_without_blocking_call(self):
        with self.temp_codex() as codex:
            app = CodexVaultApp()
            app.withdraw()
            try:
                app.path_var.set(str(codex))
                app.refresh_in_background()
                self.assertTrue(app._scan_in_progress)
                deadline = time.time() + 3
                while app._scan_in_progress and time.time() < deadline:
                    app.update()
                    time.sleep(0.01)
                app.update_idletasks()
                self.assertFalse(app._scan_in_progress)
                self.assertEqual(len(app.skills), 1)
                self.assertIn("Scan complete", app.status_var.get())
            finally:
                app.destroy()

    def test_background_task_reports_to_status_bar(self):
        app = CodexVaultApp()
        app.withdraw()
        try:
            app.run_background_task(
                "Mock export",
                lambda: "done",
                lambda result: app.notify(f"Task result {result}", "success", "Mock complete"),
            )
            self.assertTrue(app._task_in_progress)
            deadline = time.time() + 3
            while app._task_in_progress and time.time() < deadline:
                app.update()
                time.sleep(0.01)
            app.update_idletasks()
            self.assertFalse(app._task_in_progress)
            self.assertIn("Task result done", app.status_log.get("1.0", "end"))
        finally:
            app.destroy()


if __name__ == "__main__":
    unittest.main()
