import subprocess
import os
import signal
import threading
import tkinter as tk
import time
from tkinter import simpledialog, messagebox


class ScreenRecorder:
    def __init__(self, output_file="output.mp4"):
        self.output_file = output_file
        self.process = None
        self.audio_device = self.get_audio_device()

    def get_audio_device(self):
        """Detect available audio devices using ffmpeg and let the user select one."""
        try:
            # Ejecuta ffmpeg para listar dispositivos de audio
            result = subprocess.run(
                ["ffmpeg", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
                text=True
            )
            devices = result.stderr.splitlines()
            audio_devices = [line for line in devices if "audio=" in line]

            if not audio_devices:
                messagebox.showerror("Error", "No se detectaron dispositivos de audio.")
                return None

            # Extraer nombres de dispositivos de audio
            device_names = [line.split("audio=")[1].strip().strip('"') for line in audio_devices]

            if len(device_names) == 1:
                return device_names[0]  # Si solo hay un dispositivo, lo selecciona automáticamente

            # Preguntar al usuario qué dispositivo usar
            selected_device = simpledialog.askstring(
                "Seleccionar dispositivo de audio",
                f"Dispositivos disponibles:\n" + "\n".join(device_names) + "\n\nEscribe el nombre del dispositivo:"
            )

            if selected_device not in device_names:
                messagebox.showerror("Error", "Dispositivo de audio no válido.")
                return None

            return selected_device

        except Exception as e:
            print(f"Error detectando dispositivos de audio: {e}")
            return None

    def start_recording(self):
        if self.process:
            print("Recording is already in progress.")
            return

        if not self.audio_device:
            messagebox.showerror("Error", "No se configuró un dispositivo de audio.")
            return

        print("Starting recording...")

        # Comando genérico para ffmpeg
        command = [
            "ffmpeg",
            "-y",  # Sobrescribe el archivo de salida
            "-f", "gdigrab",  # Captura de pantalla en Windows
            "-framerate", "30",
            "-i", "desktop",  # Captura toda la pantalla
            "-f", "dshow",  # Captura de audio con DirectShow
            f"-i", f"audio={self.audio_device}",
            "-vcodec", "libx264",
            "-acodec", "aac",
            "-strict", "experimental",
            "-pix_fmt", "yuv420p",
            self.output_file,
        ]

        print("FFmpeg command:", " ".join(command))  # Para depuración

        # Ejecutar el proceso ffmpeg
        self.process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )

        # Registrar salida de ffmpeg
        def log_ffmpeg_output(process):
            for line in iter(process.stderr.readline, b""):
                print("[FFmpeg]", line.decode("utf-8").strip())

        threading.Thread(target=log_ffmpeg_output, args=(self.process,), daemon=True).start()

        print("Recording started...")

    def stop_recording(self):
        if not self.process:
            print("No recording is in progress.")
            return

        print("Stopping recording...")
        self.process.send_signal(signal.CTRL_BREAK_EVENT)
        self.process = None
        print("Recording stopped.")


class RecorderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Screen Recorder")
        self.recorder = ScreenRecorder(output_file="output.mp4")

        self.is_recording = False
        self.start_time = None

        # Botones
        self.start_button = tk.Button(root, text="Start Recording", command=self.start_recording, width=20, bg="green", fg="white")
        self.start_button.grid(row=0, column=0, padx=10, pady=10)

        self.stop_button = tk.Button(root, text="Stop Recording", command=self.stop_recording, width=20, bg="red", fg="white", state="disabled")
        self.stop_button.grid(row=1, column=0, padx=10, pady=10)

        # Contador
        self.timer_label = tk.Label(root, text="Recording Time: 0 seconds", font=("Arial", 12))
        self.timer_label.grid(row=2, column=0, padx=10, pady=10)

    def start_recording(self):
        if not self.is_recording:
            self.is_recording = True
            self.start_time = time.time()
            self.recorder.start_recording()
            self.start_button.config(state="disabled")
            self.stop_button.config(state="normal")
            self.update_timer()

    def stop_recording(self):
        if self.is_recording:
            self.is_recording = False
            self.recorder.stop_recording()
            self.start_button.config(state="normal")
            self.stop_button.config(state="disabled")
            self.timer_label.config(text="Recording Time: 0 seconds")

    def update_timer(self):
        if self.is_recording:
            elapsed_time = int(time.time() - self.start_time)
            self.timer_label.config(text=f"Recording Time: {elapsed_time} seconds")
            self.root.after(1000, self.update_timer)


# Crear la ventana principal
if __name__ == "__main__":
    root = tk.Tk()
    app = RecorderApp(root)
    root.mainloop()
