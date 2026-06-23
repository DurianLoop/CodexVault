from __future__ import annotations

import time
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from codexvault.ui_app import CodexVaultApp


OUTPUT_DIR = Path("docs/assets/manual-qa")


def capture_window(app: CodexVaultApp, path: Path) -> None:
    try:
        from PIL import ImageGrab
    except ImportError as exc:
        raise SystemExit("Install Pillow to capture screenshots: python -m pip install pillow") from exc
    app.update_idletasks()
    x = app.winfo_rootx()
    y = app.winfo_rooty()
    width = app.winfo_width()
    height = app.winfo_height()
    ImageGrab.grab((x, y, x + width, y + height)).save(path)


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    app = CodexVaultApp()
    try:
        app.update()
        time.sleep(0.3)
        app.show_view("overview")
        app.update()
        capture_window(app, OUTPUT_DIR / "dashboard.png")
        app.show_view("achievements")
        app.update()
        app.render_achievements()
        capture_window(app, OUTPUT_DIR / "achievements.png")
    finally:
        app.request_close()
    print(f"Captured screenshots in {OUTPUT_DIR.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
