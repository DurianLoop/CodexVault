@echo off
setlocal
cd /d "%~dp0"
python tools\build_portable_exe.py
endlocal
