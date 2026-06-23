from __future__ import annotations

import time
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from codexvault.ui_app import CodexVaultApp


def assert_bounds(name: str, bounds: tuple[int, int, int, int]) -> None:
    x1, y1, x2, y2 = bounds
    if x2 <= x1 or y2 <= y1:
        raise AssertionError(f"{name} has invalid bounds: {bounds}")


def main() -> int:
    app = CodexVaultApp()
    app.update()
    try:
        for view in ["overview", "skills", "memory", "sync", "achievements", "account"]:
            app.show_view(view)
            app.update()
            time.sleep(0.05)

        app.show_view("achievements")
        app.update_idletasks()
        app.render_achievements()
        if not app.achievement_bounds:
            raise AssertionError("achievement rows were not rendered")
        assert_bounds("first achievement row", app.achievement_bounds[0])
        if app.achievement_button_bounds:
            assert_bounds("first achievement button", next(iter(app.achievement_button_bounds.values())))
        if app.toast_host.place_info():
            raise AssertionError("toast host should be hidden when no toast is active")
        if not hasattr(app, "achievement_scrollbar"):
            raise AssertionError("achievement scrollbar missing")
    finally:
        app.request_close()
    print("UI_BOOT_SMOKE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
