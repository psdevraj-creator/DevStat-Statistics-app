@echo off
cd /d "%~dp0"
powershell -WindowStyle Hidden -NoProfile -Command "Start-Process -WindowStyle Hidden -FilePath 'py' -ArgumentList '-3.14','launcher_gui.py'"
exit
