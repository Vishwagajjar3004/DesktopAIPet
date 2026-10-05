@echo off
REM Build script for Windows: creates dist\Asha\Asha.exe
REM Run from the project root: packaging\build_windows.bat

cd /d "%~dp0\.."

python -m venv .venv_build
call .venv_build\Scripts\activate.bat

pip install -r requirements.txt
pip install pyinstaller

pyinstaller packaging\asha.spec --noconfirm --clean

echo.
echo Build complete. See dist\Asha\Asha.exe
