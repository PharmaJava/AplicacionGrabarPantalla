@echo off
REM ====================================================================
REM  Genera el ejecutable "GrabadorPantallaPRO.exe" (portable, con FFmpeg
REM  incrustado dentro). Solo tienes que hacer doble clic en este archivo.
REM ====================================================================

echo.
echo === Grabador de Pantalla PRO - generador de .exe ===
echo.

REM 1) Asegura que PyInstaller esta instalado.
py -m pip install --upgrade pyinstaller
if errorlevel 1 (
    echo.
    echo ERROR: no se pudo instalar PyInstaller.
    pause
    exit /b 1
)

REM 2) Compila usando el spec (incrusta ffmpeg.exe).
py -m PyInstaller --noconfirm --clean grabador_pro.spec
if errorlevel 1 (
    echo.
    echo ERROR: la compilacion fallo.
    pause
    exit /b 1
)

echo.
echo === LISTO ===
echo El ejecutable esta en:  dist\GrabadorPantallaPRO.exe
echo Puedes copiarlo a cualquier ordenador Windows y ejecutarlo.
echo.
pause
