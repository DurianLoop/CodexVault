import unittest

from codexvault.achievements import AchievementEngine, default_achievements


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


if __name__ == "__main__":
    unittest.main()
