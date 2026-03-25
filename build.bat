@echo off
echo ============================================
echo   Macro Quick Access - Build
echo ============================================
echo.

echo [1/2] Instalando PyInstaller...
pip install pyinstaller --quiet
if errorlevel 1 (
    echo ERROR: No se pudo instalar PyInstaller. Asegurate de tener pip disponible.
    pause
    exit /b 1
)

echo [2/2] Compilando el ejecutable...
pyinstaller macro_quick_access.spec --clean
if errorlevel 1 (
    echo ERROR: La compilacion fallo. Revisa los mensajes de arriba.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   LISTO
echo ============================================
echo   Ejecutable: dist\MacroQuickAccess\MacroQuickAccess.exe
echo.
echo   Para distribuir: comprime la carpeta dist\MacroQuickAccess\ en un .zip
echo ============================================
pause
