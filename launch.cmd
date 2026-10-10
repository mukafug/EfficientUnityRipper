@echo off
cd /d "%~dp0"
if not exist ".local\venv\Scripts\pythonw.exe" (
  echo Run setup.ps1 first.
  pause
  exit /b 1
)
start "EfficientUnityRipper" ".local\venv\Scripts\pythonw.exe" -m eur.gui %*
