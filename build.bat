@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python314\python.exe"
if not exist "%PYTHON_EXE%" (
  echo Python 3.14 was not found at "%PYTHON_EXE%".
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  "%PYTHON_EXE%" -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip -q
pip install -r requirements.txt pyinstaller -q
if errorlevel 1 (
  echo Dependency installation failed.
  exit /b 1
)

echo Building standalone executable...
pyinstaller --noconfirm --clean MarkerGitHubBridge.spec
if errorlevel 1 (
  echo Build failed.
  exit /b 1
)

if exist "dist\MarkerGitHubBridge.exe" (
  copy /Y .env.example dist\.env.example >nul
  echo.
  echo Build complete: dist\MarkerGitHubBridge.exe
  echo Copy .env.example to .env in dist and configure the credentials before running it.
) else (
  echo Build failed: executable was not created.
  exit /b 1
)
