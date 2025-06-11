import os
import subprocess
import threading
import tkinter as tk
from PIL import Image, ImageTk
import cv2
import numpy as np

class DeviceStreamer(tk.Tk):
    def __init__(self, scale=0.5):
        super().__init__()
        self.title("Vysor-Lite Stream")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.scale = scale
        self.pipe_name = "screen_pipe.h264"

        if os.path.exists(self.pipe_name):
            os.remove(self.pipe_name)
        os.mkfifo(self.pipe_name) if os.name != 'nt' else open(self.pipe_name, 'wb').close()  # fake it on Windows

        self.dev_w, self.dev_h = self.get_device_size()
        self.win_w, self.win_h = int(self.dev_w * scale), int(self.dev_h * scale)

        self.canvas = tk.Canvas(self, width=self.win_w, height=self.win_h)
        self.canvas.pack()
        self.img_id = self.canvas.create_image(0, 0, anchor="nw", image=None)
        self.photo = None

        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<ButtonPress-1>", self.drag_start)
        self.canvas.bind("<ButtonRelease-1>", self.drag_end)

        self.stop_event = threading.Event()
        threading.Thread(target=self.adb_stream_to_pipe, daemon=True).start()
        threading.Thread(target=self.read_from_pipe_and_display, daemon=True).start()

    def get_device_size(self):
        output = subprocess.check_output(["adb", "shell", "wm", "size"], universal_newlines=True)
        for token in output.split():
            if "x" in token:
                w, h = token.split("x")
                return int(w), int(h)
        raise RuntimeError("Unable to get screen size")

    def adb_stream_to_pipe(self):
        with open(self.pipe_name, "wb") as pipe:
            proc = subprocess.Popen(["adb", "exec-out", "screenrecord", "--output-format=h264", "-"],
                                    stdout=subprocess.PIPE)
            while not self.stop_event.is_set():
                chunk = proc.stdout.read(4096)
                if not chunk:
                    break
                pipe.write(chunk)
            proc.terminate()

    def read_from_pipe_and_display(self):
        cap = cv2.VideoCapture(self.pipe_name, cv2.CAP_FFMPEG)
        while not self.stop_event.is_set():
            ret, frame = cap.read()
            if not ret:
                continue
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame)
            if self.scale != 1.0:
                img = img.resize((self.win_w, self.win_h))
            self.photo = ImageTk.PhotoImage(img)
            self.after(0, lambda: self.canvas.itemconfig(self.img_id, image=self.photo))
        cap.release()

    def map_coords(self, x, y):
        return int(x / self.scale), int(y / self.scale)

    def on_click(self, ev):
        x, y = self.map_coords(ev.x, ev.y)
        subprocess.Popen(["adb", "shell", "input", "tap", str(x), str(y)])

    def drag_start(self, ev):
        self._x0, self._y0 = ev.x, ev.y

    def drag_end(self, ev):
        x1, y1 = self.map_coords(self._x0, self._y0)
        x2, y2 = self.map_coords(ev.x, ev.y)
        subprocess.Popen([
            "adb", "shell", "input", "swipe",
            str(x1), str(y1), str(x2), str(y2), "200"
        ])

    def on_close(self):
        self.stop_event.set()
        self.destroy()
        try:
            os.remove(self.pipe_name)
        except:
            pass

if __name__ == "__main__":
    DeviceStreamer(scale=0.5).mainloop()
