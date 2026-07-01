# Grabador de Pantalla PRO

Aplicación de escritorio para **Windows** que graba la pantalla con audio
usando FFmpeg. Pensada para funcionar en **cualquier ordenador o portátil**
sin instalar nada.

## Descargar

👉 [**Descargar el instalador (última versión)**](https://github.com/PharmaJava/AplicacionGrabarPantalla/releases/latest)

Descarga `GrabadorPantallaPRO_Setup.exe`, ejecútalo y sigue el asistente.
Windows puede avisar de "Editor desconocido" (el instalador no está firmado
digitalmente); pulsa "Más información" → "Ejecutar de todas formas".

## Características

- **Icono propio** en el ejecutable y en la ventana.
- **Menús** (Archivo · Grabación · Configuración · Ayuda).
- **Selección de pantalla**: si tienes varios monitores, eliges cuál grabar
  (o el escritorio completo).
- **Región personalizada**: pulsa "Región…" (o `Ctrl+G`) y arrastra un
  rectángulo sobre la pantalla para grabar solo esa zona.
- **Selección de micrófono / audio** por desplegable (o grabar sin audio).
- **Calidad de vídeo** seleccionable: Alta / Media / Baja (equilibrio entre
  nitidez y tamaño de archivo).
- Ajuste de **FPS** (15/24/30/60) y de la **carpeta de salida**.
- **Temporizador** de grabación y barra de estado.
- Atajos: `Ctrl+R` iniciar, `Ctrl+S` detener, `Ctrl+G` región,
  `F5` re-escanear dispositivos.
- **FFmpeg incrustado** en el `.exe`: no hay que instalar nada en el equipo
  de destino.

## Probar sin compilar

```bat
py grabador_pro.py
```

(FFmpeg debe estar junto al script, en `./bin/ffmpeg.exe`, o en el PATH.)

## Generar el ejecutable `.exe`

Haz **doble clic** en `build.bat`, o desde una terminal:

```bat
py -m pip install --upgrade pyinstaller
py -m PyInstaller --noconfirm --clean grabador_pro.spec
```

El ejecutable se genera en:

```
dist\GrabadorPantallaPRO.exe
```

Ese único archivo ya lleva FFmpeg dentro. Cópialo a cualquier PC con Windows
y funciona con doble clic.

> El `.exe` ocupa bastante (~70 MB) porque incluye FFmpeg completo. Es el
> precio de que sea 100 % portable. Si prefieres un `.exe` pequeño, edita
> `grabador_pro.spec` y deja `binaries = []`; entonces deberás copiar
> `ffmpeg.exe` junto al ejecutable (o tenerlo en el PATH).

## Generar el instalador (Setup.exe)

Para distribuir la app como un instalador normal de Windows (con asistente,
accesos directos en el Menú Inicio/Escritorio y desinstalador), en vez de
repartir el `.exe` suelto:

1. Instala [Inno Setup 6](https://jrsoftware.org/isdl.php) (gratuito).
2. Genera primero el ejecutable con `build.bat` (paso anterior).
3. Haz **doble clic** en `build_installer.bat`, o desde una terminal:

   ```bat
   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
   ```

El instalador se genera en:

```
installer_output\GrabadorPantallaPRO_Setup.exe
```

Ese archivo es el que se reparte: al ejecutarlo en cualquier PC con Windows,
instala la app en Archivos de Programa, crea el acceso directo en el Menú
Inicio (y opcionalmente en el Escritorio) y registra un desinstalador en
"Aplicaciones y características". No requiere tener Python, FFmpeg ni nada
más instalado en el equipo de destino.

## Cómo localiza FFmpeg la aplicación

Busca `ffmpeg.exe` en este orden:

1. Incrustado dentro del `.exe` (PyInstaller).
2. Junto al ejecutable, o en una subcarpeta `bin\`.
3. En el `PATH` del sistema.

## Notas

- Requiere **Windows** (usa `gdigrab` y `dshow` de FFmpeg).
- La ruta de FFmpeg que se incrusta está en `grabador_pro.spec`
  (`FFMPEG_SRC`, por defecto `C:\webm\bin\ffmpeg.exe`). Cámbiala si tu
  FFmpeg está en otro sitio.
- Las grabaciones se guardan por defecto en tu carpeta **Vídeos** con el
  nombre `Grabacion_AAAAMMDD_HHMMSS.mp4`.
