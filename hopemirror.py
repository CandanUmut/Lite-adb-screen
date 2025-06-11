import subprocess
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import io
import time

class ScreenshotMirror(tk.Toplevel):
    def __init__(self, serial, scale=0.5):
        super().__init__()
        self.serial = serial
        self.scale = scale
        self.stop_event = threading.Event()
        self.title(f"HopeMirror – {serial}")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.dev_w, self.dev_h = self.get_device_size()
        self.win_w = int(self.dev_w * scale)
        self.win_h = int(self.dev_h * scale)

        self.canvas = tk.Canvas(self, width=self.win_w, height=self.win_h)
        self.canvas.pack()
        self.img_id = self.canvas.create_image(0, 0, anchor="nw", image=None)
        self.photo = None

        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<ButtonPress-1>", self.drag_start)
        self.canvas.bind("<ButtonRelease-1>", self.drag_end)

        threading.Thread(target=self.stream_loop, daemon=True).start()

    def get_device_size(self):
        try:
            out = subprocess.check_output(["adb", "-s", self.serial, "shell", "wm", "size"], universal_newlines=True)
            for token in out.split():
                if "x" in token:
                    w, h = token.split("x")
                    return int(w), int(h)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to get screen size: {e}")
        return 1080, 1920

    def stream_loop(self):
        while not self.stop_event.is_set():
            try:
                img_data = subprocess.check_output(["adb", "-s", self.serial, "exec-out", "screencap", "-p"])
                img = Image.open(io.BytesIO(img_data))
                if self.scale != 1.0:
                    img = img.resize((self.win_w, self.win_h))
                self.photo = ImageTk.PhotoImage(img)
                self.after(0, lambda: self.canvas.itemconfig(self.img_id, image=self.photo))
            except Exception as e:
                print(f"[{self.serial}] Screenshot error:", e)
            time.sleep(0.08)  # ~12 FPS
        print(f"[{self.serial}] Stream stopped.")

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
        self.destroy()


class DeviceSelector(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("HopeMirror Launcher (Screenshot Mode)")
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
            ScreenshotMirror(serial, scale=0.7)


if __name__ == "__main__":
    DeviceSelector().mainloop()
