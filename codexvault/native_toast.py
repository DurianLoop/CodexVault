from __future__ import annotations

import subprocess


def show_native_toast(title: str, message: str, *, dry_run: bool = False) -> bool:
    """Try to show a Windows toast through PowerShell.

    If BurntToast is not installed, callers should fall back to the Tk overlay.
    The function returns False instead of raising so UI flows stay smooth.
    """

    safe_title = title.replace("'", "''")
    safe_message = message.replace("'", "''")
    script = (
        "if (Get-Command New-BurntToastNotification -ErrorAction SilentlyContinue) { "
        f"New-BurntToastNotification -Text @('{safe_title}', '{safe_message}'); "
        "exit 0 } else { exit 2 }"
    )
    if dry_run:
        return True
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return False
    return result.returncode == 0
