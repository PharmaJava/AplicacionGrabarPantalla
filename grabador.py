import subprocess
import os
import signal
import threading
import tkinter as tk
from tkinter import messagebox
import time

class ScreenRecorder:
    def __init__(self, output_file="output.mp4"):
        self.output_file = output_file
        self.process = None

    def start_recording(self):
        if self.process:
            print("Recording is already in progress.")
            return

        print("Starting recording...")
        command = [
            "ffmpeg",
            "-y",
            "-f", "gdigrab",
            "-framerate", "30",
            "-probesize", "50M",
            "-analyzeduration", "100M",
            "-i", "desktop",
            "-f", "dshow",
            "-i", "audio=Varios micrófonos (Realtek(R) Audio)",
            "-vcodec", "libx264",
            "-acodec", "aac",
            "-strict", "experimental",
            "-pix_fmt", "yuv420p",
            self.output_file
        ]

        self.process = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
        )
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
        self.timer_thread = None

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
