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

        # 🟩 Toolbar Frame
        toolbar = tk.Frame(self)
        toolbar.pack(side="top", fill="x", padx=5, pady=3)

        ttk.Button(toolbar, text="🔊 Vol +", command=self.volume_up).pack(side="left")
        ttk.Button(toolbar, text="🔉 Vol -", command=self.volume_down).pack(side="left")
        ttk.Button(toolbar, text="🏠 Home", command=self.send_home).pack(side="left")
        ttk.Button(toolbar, text="🔙 Back", command=self.send_back).pack(side="left")
        ttk.Button(toolbar, text="📸 Screenshot", command=self.take_screenshot).pack(side="left")
        ttk.Button(toolbar, text="⌨ Send Text", command=self.prompt_send_text).pack(side="left")

        # 🟩 Canvas
        self.canvas = tk.Canvas(self, width=self.win_w, height=self.win_h)
        self.canvas.pack()
        self.img_id = self.canvas.create_image(0, 0, anchor="nw", image=None)
        self.photo = None

        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<ButtonPress-1>", self.drag_start)
        self.canvas.bind("<ButtonRelease-1>", self.drag_end)

        threading.Thread(target=self.stream_loop, daemon=True).start()

    def get_device_size(self):
        out = subprocess.check_output(["adb", "-s", self.serial, "shell", "wm", "size"], universal_newlines=True)
        for token in out.split():
            if "x" in token:
                w, h = token.split("x")
                return int(w), int(h)
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
            time.sleep(0.08)

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

    # 🟩 Button Command Helpers
    def volume_up(self):
        subprocess.Popen(["adb", "-s", self.serial, "shell", "input", "keyevent", "24"])

    def volume_down(self):
        subprocess.Popen(["adb", "-s", self.serial, "shell", "input", "keyevent", "25"])

    def send_back(self):
        subprocess.Popen(["adb", "-s", self.serial, "shell", "input", "keyevent", "4"])

    def send_home(self):
        subprocess.Popen(["adb", "-s", self.serial, "shell", "input", "keyevent", "3"])

    def take_screenshot(self):
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{self.serial}_{timestamp}.png"
        try:
            img_data = subprocess.check_output(["adb", "-s", self.serial, "exec-out", "screencap", "-p"])
            with open(filename, "wb") as f:
                f.write(img_data)
            messagebox.showinfo("Screenshot Saved", f"Saved to {filename}")
        except Exception as e:
            messagebox.showerror("Screenshot Error", str(e))

    def prompt_send_text(self):
        top = tk.Toplevel(self)
        top.title("Send Text to Device")
        top.geometry("300x100")
        tk.Label(top, text="Enter text:").pack(pady=5)
        entry = tk.Entry(top)
        entry.pack(pady=5)

        def send():
            text = entry.get().replace(" ", "%s")  # ADB escapes spaces
            subprocess.Popen(["adb", "-s",
