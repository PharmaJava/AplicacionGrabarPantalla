# -*- coding: utf-8 -*-
"""
Grabador de Pantalla PRO
------------------------
Aplicación de escritorio (Windows) para grabar la pantalla con audio usando
FFmpeg. Incluye:

  * Barra de menús (Archivo / Grabación / Configuración / Ayuda).
  * Selección de la pantalla a grabar cuando hay varios monitores.
  * Selección del dispositivo de audio (o grabar sin audio).
  * Ajuste de FPS y carpeta de salida.
  * Localización automática de FFmpeg: empaquetado dentro del .exe,
    junto al ejecutable, o en el PATH del sistema. Así funciona en
    cualquier ordenador aunque no tenga FFmpeg instalado.

Requisitos en tiempo de ejecución: solo la librería estándar de Python
(tkinter + ctypes). No hace falta instalar nada más.
"""

import os
import re
import sys
import time
import signal
import shutil
import threading
import subprocess
from datetime import datetime

import ctypes
from ctypes import wintypes

import tkinter as tk
from tkinter import ttk, filedialog, messagebox


APP_NAME = "Grabador de Pantalla PRO"

# Evita que se abran ventanas de consola al lanzar FFmpeg (build --windowed).
CREATE_NO_WINDOW = 0x08000000


# --------------------------------------------------------------------------- #
#  Utilidades de sistema
# --------------------------------------------------------------------------- #
def get_ffmpeg_path():
    """Devuelve la ruta a ffmpeg.exe buscando en varios sitios.

    Orden de búsqueda:
      1. Recurso empaquetado por PyInstaller (sys._MEIPASS).
      2. Junto al ejecutable / script (o en su subcarpeta ./bin).
      3. En el PATH del sistema.
    """
    candidates = []

    # 1) Empaquetado con PyInstaller (--onefile extrae aquí).
    if hasattr(sys, "_MEIPASS"):
        candidates.append(os.path.join(sys._MEIPASS, "ffmpeg.exe"))

    # 2) Junto al ejecutable/script.
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(base, "ffmpeg.exe"))
    candidates.append(os.path.join(base, "bin", "ffmpeg.exe"))

    for path in candidates:
        if path and os.path.isfile(path):
            return path

    # 3) En el PATH.
    found = shutil.which("ffmpeg")
    if found:
        return found

    return None


def resource_path(name):
    """Localiza un recurso empaquetado (icono) tanto en .py como en .exe."""
    if hasattr(sys, "_MEIPASS"):
        path = os.path.join(sys._MEIPASS, name)
        if os.path.isfile(path):
            return path
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base, name)
    return path if os.path.isfile(path) else None


def _hide_console_window(pid, timeout=1.0):
    """Oculta la ventana de consola de un proceso hijo (por su PID).

    FFmpeg necesita su propia consola para poder recibir CTRL_BREAK_EVENT
    (ver comentario en ScreenRecorder.start), pero no queremos que se vea.
    Se busca la ventana recién creada por PID y se oculta con ShowWindow;
    la consola sigue existiendo (y recibiendo señales), solo que invisible.
    """
    try:
        user32 = ctypes.windll.user32
        WNDENUMPROC = ctypes.WINFUNCTYPE(
            ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        found = {"hwnd": None}

        def _callback(hwnd, _lparam):
            found_pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(found_pid))
            if found_pid.value == pid:
                found["hwnd"] = hwnd
                return False  # detiene la enumeración
            return True

        deadline = time.time() + timeout
        while time.time() < deadline and not found["hwnd"]:
            user32.EnumWindows(WNDENUMPROC(_callback), 0)
            if not found["hwnd"]:
                time.sleep(0.02)

        if found["hwnd"]:
            SW_HIDE = 0
            user32.ShowWindow(found["hwnd"], SW_HIDE)
    except Exception as exc:  # noqa: BLE001
        print("No se pudo ocultar la consola de FFmpeg:", exc)


def get_monitors():
    """Enumera los monitores conectados usando la API de Windows (ctypes).

    Devuelve una lista de diccionarios con: left, top, width, height y
    primary. Las coordenadas están en el sistema del escritorio virtual, que
    es justo lo que necesita gdigrab con -offset_x/-offset_y/-video_size.
    """
    monitors = []
    try:
        user32 = ctypes.windll.user32

        MonitorEnumProc = ctypes.WINFUNCTYPE(
            ctypes.c_int,
            ctypes.c_ulong,                     # hMonitor
            ctypes.c_ulong,                     # hdcMonitor
            ctypes.POINTER(wintypes.RECT),      # lprcMonitor
            ctypes.c_double,                    # dwData
        )

        def _callback(hMonitor, hdcMonitor, lprcMonitor, dwData):
            r = lprcMonitor.contents
            monitors.append({
                "left": r.left,
                "top": r.top,
                "width": r.right - r.left,
                "height": r.bottom - r.top,
                "primary": (r.left == 0 and r.top == 0),
            })
            return 1  # continuar la enumeración

        user32.EnumDisplayMonitors(0, 0, MonitorEnumProc(_callback), 0)
    except Exception as exc:  # noqa: BLE001
        print("No se pudieron enumerar los monitores:", exc)

    # Orden estable: de izquierda a derecha / de arriba abajo.
    monitors.sort(key=lambda m: (m["top"], m["left"]))
    return monitors


def list_audio_devices(ffmpeg_path):
    """Lista los dispositivos de audio (DirectShow) disponibles con FFmpeg.

    Devuelve una lista de dicts {"name": nombre_visible, "alt": nombre_alt}.
    El "nombre alternativo" (p.ej. "@device_cm_{GUID}\\wave_{GUID}") es un
    identificador ASCII estable que FFmpeg también acepta con "-i audio=...".
    Se usa ese en vez del nombre visible porque, en Windows, los nombres con
    tildes/ñ pueden sufrir un problema de codificación al pasarlos de vuelta
    como argumento y FFmpeg entonces no encuentra el dispositivo.
    """
    devices = []
    if not ffmpeg_path:
        return devices

    try:
        result = subprocess.run(
            [ffmpeg_path, "-hide_banner", "-list_devices", "true",
             "-f", "dshow", "-i", "dummy"],
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            creationflags=CREATE_NO_WINDOW,
        )
        lines = (result.stderr or "").splitlines()

        mode = None  # "audio" o "video" según la sección en la que estemos
        for i, line in enumerate(lines):
            low = line.lower()
            if "directshow audio devices" in low:
                mode = "audio"
                continue
            if "directshow video devices" in low:
                mode = "video"
                continue
            if "alternative name" in low:
                continue

            match = re.search(r'"([^"]+)"', line)
            if not match:
                continue
            name = match.group(1)

            # FFmpeg nuevo marca "(audio)"; el antiguo usa la cabecera de sección.
            if "(audio)" in low or (mode == "audio" and "(video)" not in low):
                alt = None
                if i + 1 < len(lines) and "alternative name" in lines[i + 1].lower():
                    alt_match = re.search(r'"([^"]+)"', lines[i + 1])
                    if alt_match:
                        alt = alt_match.group(1)
                devices.append({"name": name, "alt": alt})
    except Exception as exc:  # noqa: BLE001
        print("No se pudieron listar los dispositivos de audio:", exc)

    # Elimina duplicados (por nombre) conservando el orden.
    seen = set()
    unique = []
    for dev in devices:
        if dev["name"] not in seen:
            seen.add(dev["name"])
            unique.append(dev)
    return unique


# --------------------------------------------------------------------------- #
#  Motor de grabación
# --------------------------------------------------------------------------- #
class ScreenRecorder:
    """Envuelve el proceso de FFmpeg para grabar la pantalla."""

    def __init__(self, ffmpeg_path):
        self.ffmpeg = ffmpeg_path
        self.process = None
        self.output_file = None

    @property
    def is_running(self):
        return self.process is not None

    def start(self, output_file, monitor=None, audio_device=None, fps=30,
              crf="23", preset="veryfast"):
        """Inicia la grabación.

        monitor: dict con left/top/width/height o None para todo el escritorio.
                 También sirve para una región personalizada.
        audio_device: nombre del dispositivo o None para grabar sin audio.
        crf/preset: parámetros de calidad de vídeo de libx264.
        """
        if self.process:
            raise RuntimeError("Ya hay una grabación en curso.")
        if not self.ffmpeg:
            raise RuntimeError("No se encontró FFmpeg.")

        self.output_file = output_file

        cmd = [self.ffmpeg, "-hide_banner", "-y",
               "-f", "gdigrab", "-framerate", str(fps)]

        if monitor is not None:
            cmd += [
                "-offset_x", str(monitor["left"]),
                "-offset_y", str(monitor["top"]),
                "-video_size", f'{monitor["width"]}x{monitor["height"]}',
            ]
        cmd += ["-i", "desktop"]

        if audio_device:
            cmd += ["-f", "dshow", "-i", f"audio={audio_device}"]

        cmd += ["-c:v", "libx264", "-preset", preset, "-crf", str(crf),
                "-pix_fmt", "yuv420p"]
        if audio_device:
            cmd += ["-c:a", "aac"]
        cmd += [output_file]

        print("Comando FFmpeg:", " ".join(cmd))

        self.process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            # OJO: aquí NO se usa CREATE_NO_WINDOW. Sin una consola real
            # adjunta, Windows no tiene forma de entregarle CTRL_BREAK_EVENT
            # a FFmpeg (la señal se pierde silenciosamente), así que al
            # detener la grabación se agota el timeout y se acaba matando el
            # proceso en seco, dejando el MP4 sin el "moov atom" (corrupto).
            # Por eso se crea con su propia consola (CREATE_NEW_PROCESS_GROUP)
            # y se oculta la ventana justo después con _hide_console_window().
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        _hide_console_window(self.process.pid)

        threading.Thread(
            target=self._drain_output, args=(self.process,), daemon=True
        ).start()

    def _drain_output(self, proc):
        """Vuelca la salida de FFmpeg a la consola (útil para depurar)."""
        try:
            for line in iter(proc.stderr.readline, b""):
                print("[FFmpeg]", line.decode("utf-8", "ignore").rstrip())
        except Exception:  # noqa: BLE001
            pass

    def stop(self):
        """Detiene la grabación de forma limpia para no corromper el MP4.

        Devuelve la ruta del archivo grabado (o None).
        """
        if not self.process:
            return None

        proc = self.process
        self.process = None

        # CTRL_BREAK_EVENT hace que FFmpeg finalice y cierre el MP4
        # correctamente (escribe el trailer). En Windows, escribir "q" por
        # stdin NO sirve aquí: FFmpeg lee el teclado con _kbhit()/_getch(),
        # que solo funcionan sobre una consola real, no sobre un pipe.
        try:
            proc.send_signal(signal.CTRL_BREAK_EVENT)
        except Exception as exc:  # noqa: BLE001
            print("No se pudo enviar CTRL_BREAK_EVENT:", exc)

        try:
            proc.wait(timeout=10)
        except Exception:  # noqa: BLE001
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:  # noqa: BLE001
                pass

        return self.output_file


# --------------------------------------------------------------------------- #
#  Interfaz gráfica
# --------------------------------------------------------------------------- #
class RecorderApp:
    ALL_SCREENS_LABEL = "Todas las pantallas (escritorio completo)"
    NO_AUDIO_LABEL = "Sin audio (solo vídeo)"
    REGION_PREFIX = "Región"

    # Perfiles de calidad de vídeo (crf: menor = mejor calidad y más tamaño).
    QUALITY_OPTIONS = {
        "Alta (mejor calidad)":   {"crf": "18", "preset": "veryfast"},
        "Media (equilibrada)":    {"crf": "23", "preset": "veryfast"},
        "Baja (archivo pequeño)": {"crf": "30", "preset": "ultrafast"},
    }

    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        self.root.minsize(520, 360)
        self.root.resizable(False, False)

        # Icono de la ventana (barra de título, Alt+Tab y barra de tareas).
        icon = resource_path("icon.ico")
        if icon:
            try:
                self.root.iconbitmap(icon)
            except Exception:  # noqa: BLE001
                pass
            self.root.after(0, lambda: self._apply_taskbar_icon(icon))

        self.ffmpeg_path = get_ffmpeg_path()
        self.recorder = ScreenRecorder(self.ffmpeg_path)

        self.is_recording = False
        self.start_time = None

        # Carpeta de salida por defecto: la carpeta "Vídeos" del usuario.
        videos = os.path.join(os.path.expanduser("~"), "Videos")
        self.output_dir = videos if os.path.isdir(videos) else os.path.expanduser("~")
        self.last_output = None

        # Datos que se rellenan al escanear.
        self.monitors = []
        self.audio_devices = []
        self.custom_region = None  # dict left/top/width/height o None

        # Variables de la interfaz.
        self.screen_var = tk.StringVar()
        self.audio_var = tk.StringVar()
        self.fps_var = tk.StringVar(value="30")
        self.quality_var = tk.StringVar(value="Media (equilibrada)")
        self.folder_var = tk.StringVar(value=self.output_dir)
        self.timer_var = tk.StringVar(value="Tiempo de grabación: 00:00:00")
        self.status_var = tk.StringVar(value="Listo.")

        self._build_menu()
        self._build_widgets()

        self.refresh_devices()

        if not self.ffmpeg_path:
            self._no_ffmpeg_warning()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ---------------------------- construcción UI --------------------------- #
    def _build_menu(self):
        menubar = tk.Menu(self.root)

        # Archivo
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Carpeta de salida…",
                              command=self.choose_output_folder)
        file_menu.add_command(label="Abrir carpeta de grabaciones",
                              command=self.open_output_folder)
        file_menu.add_separator()
        file_menu.add_command(label="Salir", command=self.on_close)
        menubar.add_cascade(label="Archivo", menu=file_menu)

        # Grabación
        rec_menu = tk.Menu(menubar, tearoff=0)
        rec_menu.add_command(label="Iniciar grabación",
                            command=self.start_recording, accelerator="Ctrl+R")
        rec_menu.add_command(label="Detener grabación",
                            command=self.stop_recording, accelerator="Ctrl+S")
        menubar.add_cascade(label="Grabación", menu=rec_menu)

        # Configuración
        cfg_menu = tk.Menu(menubar, tearoff=0)
        cfg_menu.add_command(label="Seleccionar región…",
                            command=self.select_region, accelerator="Ctrl+G")
        cfg_menu.add_command(label="Actualizar pantallas y audio",
                            command=self.refresh_devices, accelerator="F5")
        menubar.add_cascade(label="Configuración", menu=cfg_menu)

        # Ayuda
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Acerca de…", command=self.show_about)
        menubar.add_cascade(label="Ayuda", menu=help_menu)

        self.root.config(menu=menubar)

        # Atajos de teclado.
        self.root.bind("<Control-r>", lambda e: self.start_recording())
        self.root.bind("<Control-R>", lambda e: self.start_recording())
        self.root.bind("<Control-s>", lambda e: self.stop_recording())
        self.root.bind("<Control-S>", lambda e: self.stop_recording())
        self.root.bind("<F5>", lambda e: self.refresh_devices())
        self.root.bind("<Control-g>", lambda e: self.select_region())
        self.root.bind("<Control-G>", lambda e: self.select_region())

    def _build_widgets(self):
        pad = {"padx": 10, "pady": 6}
        frame = ttk.Frame(self.root, padding=14)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(1, weight=1)

        # Pantalla
        ttk.Label(frame, text="Pantalla a grabar:").grid(
            row=0, column=0, sticky="w", **pad)
        self.screen_combo = ttk.Combobox(
            frame, textvariable=self.screen_var, state="readonly", width=34)
        self.screen_combo.grid(row=0, column=1, sticky="ew", **pad)
        self.region_button = ttk.Button(
            frame, text="Región…", command=self.select_region)
        self.region_button.grid(row=0, column=2, sticky="e", **pad)

        # Audio
        ttk.Label(frame, text="Dispositivo de audio:").grid(
            row=1, column=0, sticky="w", **pad)
        self.audio_combo = ttk.Combobox(
            frame, textvariable=self.audio_var, state="readonly", width=34)
        self.audio_combo.grid(row=1, column=1, columnspan=2, sticky="ew", **pad)

        # FPS
        ttk.Label(frame, text="Fotogramas por segundo (FPS):").grid(
            row=2, column=0, sticky="w", **pad)
        self.fps_combo = ttk.Combobox(
            frame, textvariable=self.fps_var, state="readonly", width=8,
            values=["15", "24", "30", "60"])
        self.fps_combo.grid(row=2, column=1, sticky="w", **pad)

        # Calidad de vídeo
        ttk.Label(frame, text="Calidad de vídeo:").grid(
            row=3, column=0, sticky="w", **pad)
        self.quality_combo = ttk.Combobox(
            frame, textvariable=self.quality_var, state="readonly", width=34,
            values=list(self.QUALITY_OPTIONS.keys()))
        self.quality_combo.grid(row=3, column=1, columnspan=2, sticky="ew", **pad)

        # Carpeta de salida
        ttk.Label(frame, text="Carpeta de salida:").grid(
            row=4, column=0, sticky="w", **pad)
        folder_entry = ttk.Entry(frame, textvariable=self.folder_var,
                                 state="readonly")
        folder_entry.grid(row=4, column=1, sticky="ew", **pad)
        ttk.Button(frame, text="Cambiar…",
                  command=self.choose_output_folder).grid(
            row=4, column=2, sticky="e", **pad)

        # Separador
        ttk.Separator(frame, orient="horizontal").grid(
            row=5, column=0, columnspan=3, sticky="ew", pady=8)

        # Botones grabar / detener
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=6, column=0, columnspan=3, pady=4)

        self.start_button = tk.Button(
            btn_frame, text="● Iniciar grabación", command=self.start_recording,
            width=22, bg="#1e8e3e", fg="white", font=("Segoe UI", 10, "bold"),
            activebackground="#166b2e", relief="flat", cursor="hand2")
        self.start_button.grid(row=0, column=0, padx=8)

        self.stop_button = tk.Button(
            btn_frame, text="■ Detener grabación", command=self.stop_recording,
            width=22, bg="#c5221f", fg="white", font=("Segoe UI", 10, "bold"),
            activebackground="#8f1613", relief="flat", cursor="hand2",
            state="disabled")
        self.stop_button.grid(row=0, column=1, padx=8)

        # Temporizador
        self.timer_label = ttk.Label(
            frame, textvariable=self.timer_var, font=("Segoe UI", 13, "bold"))
        self.timer_label.grid(row=7, column=0, columnspan=3, pady=(10, 2))

        # Barra de estado
        status = ttk.Label(self.root, textvariable=self.status_var,
                          relief="sunken", anchor="w", padding=(8, 3))
        status.grid(row=1, column=0, sticky="ew")

        self.root.columnconfigure(0, weight=1)

    # ------------------------------ acciones -------------------------------- #
    def refresh_devices(self):
        """Vuelve a escanear monitores y dispositivos de audio."""
        # Monitores (y opción de región si ya existe una)
        self.monitors = get_monitors()
        self._rebuild_screen_values()

        # Audio
        self.audio_devices = list_audio_devices(self.ffmpeg_path)
        audio_labels = [d["name"] for d in self.audio_devices] + [self.NO_AUDIO_LABEL]
        self.audio_combo["values"] = audio_labels
        if self.audio_var.get() not in audio_labels:
            self.audio_var.set(audio_labels[0])

        n_scr = len(self.monitors)
        n_aud = len(self.audio_devices)
        self.status_var.set(
            f"Detectado(s): {n_scr} pantalla(s), {n_aud} dispositivo(s) de audio.")

    def _rebuild_screen_values(self, select_region=False):
        """Reconstruye las opciones del desplegable de pantallas."""
        labels = [self.ALL_SCREENS_LABEL]
        for i, m in enumerate(self.monitors, start=1):
            tag = " (principal)" if m["primary"] else ""
            labels.append(f"Pantalla {i}: {m['width']}x{m['height']}{tag}")
        if self.custom_region:
            r = self.custom_region
            labels.append(
                f"{self.REGION_PREFIX}: {r['width']}x{r['height']} "
                f"en ({r['left']},{r['top']})")

        self.screen_combo["values"] = labels
        if select_region and self.custom_region:
            self.screen_var.set(labels[-1])
        elif self.screen_var.get() not in labels:
            # Por defecto, la pantalla principal si existe; si no, todas.
            self.screen_var.set(labels[1] if len(labels) > 1 else labels[0])
        return labels

    def select_region(self):
        """Muestra una capa a pantalla completa para dibujar una región."""
        if self.is_recording:
            return
        if not self.monitors:
            self.monitors = get_monitors()
        if not self.monitors:
            return

        # Límites del escritorio virtual (puede empezar en coordenadas negativas).
        vx = min(m["left"] for m in self.monitors)
        vy = min(m["top"] for m in self.monitors)
        vw = max(m["left"] + m["width"] for m in self.monitors) - vx
        vh = max(m["top"] + m["height"] for m in self.monitors) - vy

        overlay = tk.Toplevel(self.root)
        overlay.overrideredirect(True)
        overlay.geometry(f"{vw}x{vh}+{vx}+{vy}")
        overlay.attributes("-alpha", 0.30)
        overlay.attributes("-topmost", True)
        overlay.configure(bg="black", cursor="crosshair")

        canvas = tk.Canvas(overlay, bg="black", highlightthickness=0,
                          cursor="crosshair")
        canvas.pack(fill="both", expand=True)
        canvas.create_text(
            vw // 2, 34,
            text="Arrastra para seleccionar la región a grabar  ·  ESC para cancelar",
            fill="white", font=("Segoe UI", 15, "bold"))

        state = {"x0": 0, "y0": 0, "rect": None, "result": None}

        def on_press(event):
            state["x0"], state["y0"] = event.x, event.y
            if state["rect"]:
                canvas.delete(state["rect"])
            state["rect"] = canvas.create_rectangle(
                event.x, event.y, event.x, event.y, outline="red", width=3)

        def on_drag(event):
            if state["rect"]:
                canvas.coords(state["rect"], state["x0"], state["y0"],
                            event.x, event.y)

        def on_release(event):
            state["result"] = (state["x0"], state["y0"], event.x, event.y)
            overlay.destroy()

        canvas.bind("<ButtonPress-1>", on_press)
        canvas.bind("<B1-Motion>", on_drag)
        canvas.bind("<ButtonRelease-1>", on_release)
        overlay.bind("<Escape>", lambda e: overlay.destroy())
        overlay.focus_force()
        overlay.grab_set()
        self.root.wait_window(overlay)

        if not state["result"]:
            return
        x0, y0, x1, y1 = state["result"]
        width = abs(x1 - x0)
        height = abs(y1 - y0)
        if width < 16 or height < 16:
            self.status_var.set("Región demasiado pequeña; no se ha cambiado.")
            return

        # Las dimensiones deben ser pares para libx264 (yuv420p).
        width -= width % 2
        height -= height % 2
        left = vx + min(x0, x1)
        top = vy + min(y0, y1)

        self.custom_region = {"left": left, "top": top,
                              "width": width, "height": height,
                              "primary": False}
        self._rebuild_screen_values(select_region=True)
        self.status_var.set(
            f"Región seleccionada: {width}x{height} en ({left},{top}).")

    def _selected_monitor(self):
        """Devuelve el monitor/región elegido o None (todas las pantallas)."""
        label = self.screen_var.get()
        if label == self.ALL_SCREENS_LABEL:
            return None
        if label.startswith(self.REGION_PREFIX):
            return self.custom_region
        match = re.match(r"Pantalla (\d+):", label)
        if match:
            idx = int(match.group(1)) - 1
            if 0 <= idx < len(self.monitors):
                return self.monitors[idx]
        return None

    def _selected_quality(self):
        """Devuelve el perfil de calidad (crf/preset) elegido."""
        return self.QUALITY_OPTIONS.get(
            self.quality_var.get(), self.QUALITY_OPTIONS["Media (equilibrada)"])

    def _selected_audio(self):
        """Devuelve el identificador de audio a pasar a FFmpeg (o None).

        Se usa el "nombre alternativo" (ASCII, tipo @device_cm_{GUID}\\wave_
        {GUID}) en vez del nombre visible, para evitar que los acentos/ñ del
        nombre real del dispositivo se corrompan al pasarlos como argumento.
        """
        label = self.audio_var.get()
        if label == self.NO_AUDIO_LABEL or not label:
            return None
        for dev in self.audio_devices:
            if dev["name"] == label:
                return dev["alt"] or dev["name"]
        return label

    def choose_output_folder(self):
        folder = filedialog.askdirectory(
            title="Elige la carpeta donde guardar las grabaciones",
            initialdir=self.output_dir)
        if folder:
            self.output_dir = folder
            self.folder_var.set(folder)
            self.status_var.set(f"Carpeta de salida: {folder}")

    def open_output_folder(self):
        try:
            os.startfile(self.output_dir)  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror(APP_NAME, f"No se pudo abrir la carpeta:\n{exc}")

    def start_recording(self):
        if self.is_recording:
            return
        if not self.ffmpeg_path:
            self._no_ffmpeg_warning()
            return

        monitor = self._selected_monitor()
        audio = self._selected_audio()
        quality = self._selected_quality()
        try:
            fps = int(self.fps_var.get())
        except ValueError:
            fps = 30

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(self.output_dir, f"Grabacion_{timestamp}.mp4")

        try:
            self.recorder.start(output_file, monitor=monitor,
                                audio_device=audio, fps=fps,
                                crf=quality["crf"], preset=quality["preset"])
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror(APP_NAME, f"No se pudo iniciar la grabación:\n{exc}")
            return

        self.is_recording = True
        self.start_time = time.time()
        self.last_output = output_file
        self._set_controls_state("disabled")
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")

        what = "todas las pantallas" if monitor is None else self.screen_var.get()
        self.status_var.set(f"Grabando {what} → {os.path.basename(output_file)}")
        self._update_timer()

    def stop_recording(self):
        if not self.is_recording:
            return
        self.is_recording = False
        self.status_var.set("Finalizando y guardando el archivo…")
        self.start_button.config(state="disabled")
        self.stop_button.config(state="disabled")

        # La finalización puede tardar unos segundos: hazlo en segundo plano.
        threading.Thread(target=self._stop_worker, daemon=True).start()

    def _stop_worker(self):
        path = self.recorder.stop()
        self.root.after(0, lambda: self._on_stopped(path))

    def _on_stopped(self, path):
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")
        self._set_controls_state("readonly")
        self.timer_var.set("Tiempo de grabación: 00:00:00")
        if path and os.path.isfile(path):
            self.status_var.set(f"Guardado: {path}")
        else:
            self.status_var.set("Grabación detenida.")

    def _set_controls_state(self, state):
        """Bloquea o desbloquea los selectores durante la grabación."""
        combo_state = "disabled" if state == "disabled" else "readonly"
        btn_state = "disabled" if state == "disabled" else "normal"
        self.screen_combo.config(state=combo_state)
        self.audio_combo.config(state=combo_state)
        self.fps_combo.config(state=combo_state)
        self.quality_combo.config(state=combo_state)
        self.region_button.config(state=btn_state)

    def _update_timer(self):
        if self.is_recording:
            elapsed = int(time.time() - self.start_time)
            h, rem = divmod(elapsed, 3600)
            m, s = divmod(rem, 60)
            self.timer_var.set(
                f"Tiempo de grabación: {h:02d}:{m:02d}:{s:02d}")
            self.root.after(1000, self._update_timer)

    def _apply_taskbar_icon(self, icon_path):
        """Fuerza el icono grande de la ventana (WM_SETICON) en Windows.

        tkinter's `iconbitmap()` solo aplica de forma fiable el icono
        pequeño (barra de título). El icono que usa la barra de tareas se
        toma del icono "grande" de la ventana, que hay que fijar a mano con
        la API de Windows para que no aparezca la pluma por defecto de Tk.
        """
        try:
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            if not hwnd:
                hwnd = self.root.winfo_id()

            h_large = ctypes.c_void_p()
            h_small = ctypes.c_void_p()
            ctypes.windll.shell32.ExtractIconExW(
                icon_path, 0,
                ctypes.byref(h_large), ctypes.byref(h_small), 1)

            WM_SETICON = 0x0080
            ICON_SMALL, ICON_BIG = 0, 1
            if h_large.value:
                ctypes.windll.user32.SendMessageW(
                    hwnd, WM_SETICON, ICON_BIG, h_large.value)
            if h_small.value:
                ctypes.windll.user32.SendMessageW(
                    hwnd, WM_SETICON, ICON_SMALL, h_small.value)
        except Exception as exc:  # noqa: BLE001
            print("No se pudo fijar el icono de la barra de tareas:", exc)

    # ------------------------------ diálogos -------------------------------- #
    def _no_ffmpeg_warning(self):
        self.status_var.set("FFmpeg no encontrado. La grabación está desactivada.")
        self.start_button.config(state="disabled")
        messagebox.showwarning(
            APP_NAME,
            "No se encontró FFmpeg.\n\n"
            "Coloca 'ffmpeg.exe' junto a este programa (o en una subcarpeta "
            "'bin'), o instálalo y añádelo al PATH del sistema.\n\n"
            "Si usas la versión .exe empaquetada, FFmpeg ya va incluido; "
            "vuelve a generar el ejecutable siguiendo el README.")

    def show_about(self):
        ffmpeg_info = self.ffmpeg_path or "no encontrado"
        messagebox.showinfo(
            f"Acerca de {APP_NAME}",
            f"{APP_NAME}\n\n"
            "Grabador de pantalla con audio para Windows.\n"
            "Permite elegir la pantalla (multi-monitor) y el micrófono.\n\n"
            f"FFmpeg: {ffmpeg_info}\n\n"
            "Basado en FFmpeg (gdigrab + dshow) y Python/tkinter.")

    def on_close(self):
        if self.is_recording:
            if not messagebox.askyesno(
                    APP_NAME,
                    "Hay una grabación en curso. ¿Deseas detenerla y salir?"):
                return
            self.is_recording = False
            self.recorder.stop()
        self.root.destroy()


def main():
    root = tk.Tk()
    try:
        # Tema visual algo más moderno si está disponible.
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")
    except Exception:  # noqa: BLE001
        pass
    RecorderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
