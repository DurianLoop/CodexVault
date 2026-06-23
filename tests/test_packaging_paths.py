import os
import tempfile
import unittest
from pathlib import Path

from codexvault import paths


class PackagingPathTests(unittest.TestCase):
    def test_runtime_directories_are_user_writable(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = os.environ.get("CODEXVAULT_DATA_DIR")
            os.environ["CODEXVAULT_DATA_DIR"] = tmp
            try:
                self.assertTrue(paths._is_writable_directory(Path(tmp)))
            finally:
                if original is None:
                    os.environ.pop("CODEXVAULT_DATA_DIR", None)
                else:
                    os.environ["CODEXVAULT_DATA_DIR"] = original

    def test_achievement_asset_set_has_packaged_png_variants(self):
        missing = [
            paths.ACHIEVEMENT_ICON_DIR / f"ach_{index:02d}_{variant}.png"
            for index in range(25)
            for variant in ["card", "detail"]
            if not (paths.ACHIEVEMENT_ICON_DIR / f"ach_{index:02d}_{variant}.png").exists()
        ]
        self.assertEqual(missing, [])

    def test_startup_diagnostics_returns_list(self):
        diagnostics = paths.startup_diagnostics()
        self.assertIsInstance(diagnostics, list)


if __name__ == "__main__":
    unittest.main()
