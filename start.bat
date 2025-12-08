@echo off
echo ========================================
echo   AI Document Review System
echo ========================================
echo.

cd /d "%~dp0"

if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Installing dependencies...
pip install -r requirements.txt -q

echo.
echo Checking PDF generation support...
python -c "import reportlab" 2>nul
if errorlevel 1 (
    echo Warning: reportlab not available, PDF download will return Markdown
    echo Run 'quick_install.bat' to install PDF support
)

echo.
echo Starting Flask server...
echo Server will be available at: http://127.0.0.1:5002
echo.
python web_app.py

pause
