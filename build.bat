@echo off
rem Builds dist\OpenReMouse.exe (single file, no console window, with icon).
rem The icon comes from assets\icon.ico; regenerate it with:  python tools\make_icon.py  (needs Pillow)
cd /d "%~dp0"
python -m pip install --quiet -r requirements.txt pyinstaller || exit /b 1
python -m PyInstaller --noconfirm --clean --onefile --windowed --name OpenReMouse ^
  --icon assets\icon.ico --add-data "assets\icon.ico;assets" ^
  --hidden-import pynput.keyboard._win32 --hidden-import pynput.mouse._win32 run.py || exit /b 1
echo.
echo Done: %~dp0dist\OpenReMouse.exe
