import subprocess
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import numpy as np
import time

FFMPEG_PATH = "ffmpeg"  # Change to absolute path if needed (e.g., "ffmpeg.exe")

class SmoothMirror(tk.Toplevel):
    def __init__(self, serial, width=1080, height=1920, scale=0.5):
        super().__init__()
        self.serial = serial
        self.title(f"HopeMirror – {serial}")
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.resizable(False, False)

        self.dev_w, self.dev_h = width, height
        self.scale = scale
        self.win_w, self.win_h = int(width * scale), int(height * scale)

        self.canvas = tk.Canvas(self, width=self.win_w, height=self.win_h, bg="black")
        self.canvas.pack()
        self.img_id = self.canvas.create_image(0, 0, anchor="nw", image=None)
        self.photo = None

        self.stop_event = threading.Event()
        self.adb_proc = None
        self.ffmpeg_proc = None

        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<ButtonPress-1>", self.drag_start)
        self.canvas.bind("<ButtonRelease-1>", self.drag_end)

        threading.Thread(target=self.stream_loop, daemon=True).start()

    def stream_loop(self):
        frame_size = self.dev_w * self.dev_h * 3
        try:
            adb_cmd = ["adb", "-s", self.serial, "exec-out", "screenrecord", "--output-format=h264", "-"]
            ffmpeg_cmd = [
                FFMPEG_PATH,
                "-f", "h264", "-i", "pipe:0",
                "-f", "rawvideo", "-pix_fmt", "rgb24",
                "-video_size", f"{self.dev_w}x{self.dev_h}",
                "pipe:1"
            ]

            self.adb_proc = subprocess.Popen(adb_cmd, stdout=subprocess.PIPE)
            self.ffmpeg_proc = subprocess.Popen(ffmpeg_cmd, stdin=self.adb_proc.stdout,
                                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                                bufsize=10**8)

            while not self.stop_event.is_set():
                raw = self.ffmpeg_proc.stdout.read(frame_size)
                if not raw or len(raw) < frame_size:
                    time.sleep(0.01)
                    continue
                try:
                    frame = np.frombuffer(raw, dtype=np.uint8).reshape((self.dev_h, self.dev_w, 3))
                    img = Image.fromarray(frame)
                    if self.scale != 1.0:
                        img = img.resize((self.win_w, self.win_h), Image.BILINEAR)
                    self.photo = ImageTk.PhotoImage(img)
                    self.after(0, lambda: self.canvas.itemconfig(self.img_id, image=self.photo))
                except Exception:
                    continue

        except FileNotFoundError:
            messagebox.showerror("FFmpeg Error", f"FFmpeg not found: {FFMPEG_PATH}")
        except Exception as e:
            messagebox.showerror("Stream Error", str(e))

    def map_coords(self, x, y):
        return int(x / self.scale), int(y / self.scale)

    def on_click(self, ev):
        x, y = self.map_coords(ev.x, ev.y)
        subprocess.Popen(["adb", "-s", self.serial, "shell", "input", "tap", str(x), str(y)])

    def drag_start(self, ev):
        self._x0, self._y0 = ev.x, ev.y

    def drag_end(self, ev):
        x1, y1 = self.map_coords(self._x0, self._y0)
        x2, y2 = self.map_coords(ev.x, ev.y)
        subprocess.Popen([
            "adb", "-s", self.serial, "shell", "input", "swipe",
            str(x1), str(y1), str(x2), str(y2), "200"
        ])

    def on_close(self):
        self.stop_event.set()
        if self.adb_proc:
            self.adb_proc.kill()
        if self.ffmpeg_proc:
            self.ffmpeg_proc.kill()
        self.destroy()


class DeviceSelector(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("HopeMirror Launcher")
        self.geometry("320x420")
        self.resizable(False, False)

        tk.Label(self, text="Connected Devices", font=("Helvetica", 13)).pack(pady=10)
        self.device_list = tk.Listbox(self, selectmode="extended", height=12)
        self.device_list.pack(fill="both", expand=True, padx=15)

        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=15)
        ttk.Button(btn_frame, text="🔄 Refresh", command=self.refresh).pack(side="left", padx=8)
        ttk.Button(btn_frame, text="▶️ Stream", command=self.stream_selected).pack(side="left", padx=8)

        self.refresh()

    def refresh(self):
        self.device_list.delete(0, tk.END)
        try:
            out = subprocess.check_output(["adb", "devices"], universal_newlines=True)
            for line in out.splitlines()[1:]:
                if line.strip() and "device" in line:
                    serial = line.split()[0]
                    self.device_list.insert(tk.END, serial)
        except Exception as e:
            messagebox.showerror("ADB Error", f"Could not list devices:\n{e}")

    def stream_selected(self):
        selection = self.device_list.curselection()
        if not selection:
            messagebox.showinfo("No Selection", "Please select at least one device.")
            return

        for i in selection:
            serial = self.device_list.get(i)
            try:
                w, h = self.get_device_resolution(serial)
                SmoothMirror(serial, width=w, height=h, scale=0.5)
            except Exception as e:
                messagebox.showerror("Device Error", str(e))

    def get_device_resolution(self, serial):
        out = subprocess.check_output(["adb", "-s", serial, "shell", "wm", "size"], universal_newlines=True)
        for part in out.split():
            if "x" in part:
                w, h = part.split("x")
                return int(w), int(h)
        return 1080, 1920  # fallback

if __name__ == "__main__":
    DeviceSelector().mainloop()
