# Visual QA Checklist

Run the boot smoke helper:

```powershell
python tools\ui_boot_smoke.py
```

Optional screenshot capture:

```powershell
python -m pip install pillow
python tools\capture_ui_screenshots.py
```

Check:

- dashboard cards stay within the main content bounds
- titlebar close button is visible and clickable
- close works in normal and maximized states
- achievements scroll from first to last row
- achievement rows do not overlap at minimum window size
- activation buttons stay inside row bounds
- toast host is hidden when no toast is active
- import preview modal text is readable
- rollback confirmation names the backup and target root
