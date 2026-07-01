@echo off
REM ====================================================================
REM  Genera el instalador "GrabadorPantallaPRO_Setup.exe".
REM  Requiere haber generado antes dist\GrabadorPantallaPRO.exe con
REM  build.bat, y tener instalado Inno Setup 6 (https://jrsoftware.org).
REM ====================================================================

set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"

echo.
echo === Grabador de Pantalla PRO - generador de instalador ===
echo.

if not exist "dist\GrabadorPantallaPRO.exe" (
    echo ERROR: no existe dist\GrabadorPantallaPRO.exe
    echo Ejecuta primero build.bat para generar el ejecutable.
    pause
    exit /b 1
)

if not exist %ISCC% (
    echo ERROR: no se encontro Inno Setup 6 en:
    echo   %ISCC%
    echo Descargalo de https://jrsoftware.org/isdl.php e instalalo.
    pause
    exit /b 1
)

%ISCC% installer.iss
if errorlevel 1 (
    echo.
    echo ERROR: la generacion del instalador fallo.
    pause
    exit /b 1
)

echo.
echo === LISTO ===
echo El instalador esta en:  installer_output\GrabadorPantallaPRO_Setup.exe
echo Puedes distribuir ese unico archivo: instala la app en cualquier PC.
echo.
pause
