# -*- mode: python ; coding: utf-8 -*-
#
# Spec de PyInstaller para "Grabador de Pantalla PRO".
#
# Empaqueta ffmpeg.exe DENTRO del ejecutable para que la aplicación funcione
# en cualquier ordenador Windows sin necesidad de instalar FFmpeg.
#
# Compilar con:   pyinstaller grabador_pro.spec
#
import os

# Ruta a ffmpeg.exe que se incrustará en el .exe.
# Cambia esta ruta si tu ffmpeg está en otro sitio.
FFMPEG_SRC = r"C:\webm\bin\ffmpeg.exe"

binaries = []
if os.path.isfile(FFMPEG_SRC):
    # El destino "." coloca ffmpeg.exe en la raíz del paquete, donde lo busca
    # get_ffmpeg_path() a través de sys._MEIPASS.
    binaries.append((FFMPEG_SRC, "."))
else:
    print("AVISO: no se encontró", FFMPEG_SRC,
          "-> el .exe NO llevará FFmpeg incrustado.")

# Incluye el icono para poder mostrarlo también en la ventana de la app.
datas = []
if os.path.isfile("icon.ico"):
    datas.append(("icon.ico", "."))
ICON = "icon.ico" if os.path.isfile("icon.ico") else None


a = Analysis(
    ['grabador_pro.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='GrabadorPantallaPRO',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,            # aplicación de ventana, sin consola
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON,
)
