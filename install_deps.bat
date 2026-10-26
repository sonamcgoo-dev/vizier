@echo off
REM Install Vizier from this source checkout with every optional feature.
setlocal
where python >nul 2>nul
if errorlevel 1 (
    echo Python 3.10+ was not found on PATH.
    echo Install it from https://www.python.org/downloads/ and try again.
    pause
    exit /b 1
)

python -m pip install --upgrade pip
python -m pip install -e ".[full,dev]"
if errorlevel 1 (
    echo.
    echo Dependency installation failed. See the messages above.
    pause
    exit /b 1
)

echo.
echo Vizier dependencies are installed. Launch it with:  python -m vizier
pause
