import unittest
import tempfile
from pathlib import Path

from codexvault.achievements import AchievementEngine, default_achievements, load_state, save_state


class AchievementUiModelTests(unittest.TestCase):
    def test_all_achievements_have_condition_metadata_for_details(self):
        achievements = default_achievements()
        self.assertEqual(len(achievements), 25)
        for achievement in achievements:
            self.assertTrue(achievement.metric)
            self.assertGreaterEqual(achievement.threshold, 1)
            self.assertTrue(achievement.description)

    def test_progress_metrics_support_threshold_based_bar(self):
        achievement = next(item for item in default_achievements() if item.id == "skill_collector")
        metrics = AchievementEngine.metrics_from_event({"counts": {"skills": 3}})
        progress = min(metrics[achievement.metric] / achievement.threshold, 1)
        self.assertEqual(progress, 0.6)

    def test_v02_state_can_store_progress_and_notification_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "achievement_state.json"
            save_state(
                path,
                {
                    "unlocked": ["hello_world"],
                    "metrics": {"imports": 1},
                    "progress": {"migration_master": {"value": 1, "threshold": 1}},
                    "notifications": [{"id": "hello_world", "name": "Hello World"}],
                },
            )

            state = load_state(path)

            self.assertEqual(state["progress"]["migration_master"]["value"], 1)
            self.assertEqual(state["notifications"][0]["name"], "Hello World")

    def test_state_loader_accepts_utf8_bom_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "achievement_state.json"
            path.write_text('{"unlocked": ["hello_world"], "metrics": {}}', encoding="utf-8-sig")

            state = load_state(path)

            self.assertEqual(state["unlocked"], ["hello_world"])


if __name__ == "__main__":
    unittest.main()
