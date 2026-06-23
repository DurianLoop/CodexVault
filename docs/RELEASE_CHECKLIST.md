# Release Checklist

## Source Validation

```powershell
python -B -m unittest discover -s tests -v
python tools\build_portable_exe.py
```

## Packaged Smoke Test

From `dist\CodexVault-portable`:

```powershell
.\CodexVault.exe
.\run_backend.bat
```

Manual app path:

1. Open app.
2. Browse to `C:\Users\<user>\.codex`.
3. Scan.
4. Open Skills.
5. Open Memory.
6. Open Sync / Packs.
7. Export a pack.
8. Preview and import a pack.
9. Confirm markdown diff appears for changed `.md` files.
10. Confirm import summary appears.
11. Roll back from the pre-import backup.
12. Open Achievements.
13. Apply All, Achieved, Unachieved, Activated, Not activated, and rarity filters.
14. Confirm locked achievements cannot activate.
15. Confirm close works in normal and maximized states.

## Documentation

- README screenshots are PNG files.
- User guide matches the actual app.
- Security model documents local-only behavior and exclusions.
- API reference matches backend routes.
- Packaging docs name runtime data location.

## Release Artifacts

- `dist\CodexVault-portable.zip`
- Test output
- Manual smoke notes
- Version/tag notes
