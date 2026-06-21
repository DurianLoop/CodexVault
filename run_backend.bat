@echo off
setlocal
cd /d "%~dp0"
python -m codexvault.backend
endlocal
