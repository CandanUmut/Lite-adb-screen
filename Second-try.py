import os
import subprocess
import threading
import tkinter as tk
from PIL import Image, ImageTk
import cv2
import time

class DeviceStreamer(tk.Tk):
    def __init__(self, scale=0.5):
        super().__init__()
        self.title("Vysor-Lite – Windows Stream")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.scale = scale
        self.temp_file = "screen_temp.mp4"
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
        threading.Thread(target=self.adb_record_to_file, daemon=True).start()
        threading.Thread(target=self.read_from_file_and_display, daemon=True).start()

    def get_device_size(self):
        output = subprocess.check_output(["adb", "shell", "wm", "size"], universal_newlines=True)
        for token in output.split():
            if "x" in token:
                w, h = token.split("x")
                return int(w), int(h)
        raise RuntimeError("Unable to get screen size")

    def adb_record_to_file(self):
        # Continuously overwrite the mp4 file every 2 seconds
        while not self.stop_event.is_set():
            with open(self.temp_file, "wb") as f:
                proc = subprocess.Popen(
                    ["adb", "exec-out", "screenrecord", "--time-limit", "2", "--output-format=h264", "-"],
                    stdout=subprocess.PIPE
                )
                while True:
                    chunk = proc.stdout.read(1024)
                    if not chunk or self.stop_event.is_set():
                        break
                    f.write(chunk)
                proc.terminate()
            time.sleep(0.2)

    def read_from_file_and_display(self):
        while not self.stop_event.is_set():
            if not os.path.exists(self.temp_file):
                time.sleep(0.1)
                continue
            cap = cv2.VideoCapture(self.temp_file)
            while cap.isOpened() and not self.stop_event.is_set():
                ret, frame = cap.read()
                if not ret:
                    break
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(frame)
                img = img.resize((self.win_w, self.win_h))
                self.photo = ImageTk.PhotoImage(img)
                self.after(0, lambda: self.canvas.itemconfig(self.img_id, image=self.photo))
                time.sleep(1/15)  # ~15 FPS
            cap.release()
            time.sleep(0.2)

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
            os.remove(self.temp_file)
        except:
            pass



def stream_loop(self):
    while not self.stop_event.is_set():
        try:
            img_data = subprocess.check_output(
                ["adb", "-s", self.serial, "exec-out", "screencap", "-p"],
                stderr=subprocess.DEVNULL
            )
            img = Image.open(io.BytesIO(img_data))

            # ✅ Update device and window sizes if screen rotated
            new_w, new_h = img.size
            if (new_w, new_h) != (self.dev_w, self.dev_h):
                self.dev_w, self.dev_h = new_w, new_h
                self.win_w = int(new_w * self.scale)
                self.win_h = int(new_h * self.scale)
                self.canvas.config(width=self.win_w, height=self.win_h)

            # ✅ Resize and show image
            img = img.resize((self.win_w, self.win_h), Image.BILINEAR)
            self.photo = ImageTk.PhotoImage(img)
            self.after(0, lambda: self.canvas.itemconfig(self.img_id, image=self.photo))

        except Exception as e:
            print(f"[{self.serial}] Screenshot error:", e)

        time.sleep(0.08)  # ~12 FPS

if __name__ == "__main__":
    DeviceStreamer(scale=0.6).mainloop()
