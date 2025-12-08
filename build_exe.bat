@echo off
echo ========================================
echo   Building EXE Package
echo ========================================
echo.

cd /d "%~dp0"

REM Activate venv
call venv\Scripts\activate.bat

REM Install PyInstaller
echo Installing PyInstaller...
pip install pyinstaller -q

REM Build EXE
echo.
echo Building executable...
pyinstaller --noconfirm --onedir --console ^
    --name "AI文档审核系统" ^
    --add-data "templates;templates" ^
    --add-data "static;static" ^
    --add-data "src;src" ^
    --add-data ".env.example;." ^
    --hidden-import=flask ^
    --hidden-import=werkzeug ^
    --hidden-import=colorlog ^
    --hidden-import=openai ^
    --hidden-import=python-docx ^
    --hidden-import=PyMuPDF ^
    --hidden-import=reportlab ^
    --hidden-import=PIL ^
    web_app.py

echo.
echo ========================================
echo   Build Complete!
echo ========================================
echo.
echo Output folder: dist\AI文档审核系统\
echo Run: dist\AI文档审核系统\AI文档审核系统.exe
echo.
echo Note: Copy .env file to the dist folder before running
pause
