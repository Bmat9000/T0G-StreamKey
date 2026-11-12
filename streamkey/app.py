import sys
import tkinter as tk
from tkinter import ttk
import tomllib
import webbrowser
from pathlib import Path

from streamkey.credentials import Credentials

STREAMLABS_GUIDE = (
    "https://support.streamlabs.com/hc/en-us/articles/"
    "49480028480667-How-to-Find-Your-TikTok-Stream-Key"
)
BACKGROUND = "#0e131d"
PANEL = "#171f2d"
TEXT = "#edf2fa"
MUTED = "#b1bfd3"
ACCENT = "#80ebcf"


class StreamKeyWindow:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.credentials = None
        self.clipboard_value = None
        self.revealed = False
        self.server = tk.StringVar()
        self.key = tk.StringVar()
        self.status = tk.StringVar(value="Waiting for credentials")
        self.detail = tk.StringVar(value="Paste the server URL and key issued to your TikTok account.")
        self.version = self.read_version()

        root.title("T0G StreamKey")
        root.configure(background=BACKGROUND)
        root.minsize(660, 480)
        root.geometry("740x540")
        root.protocol("WM_DELETE_WINDOW", self.close)
        icon = Path(__file__).with_name("streamkey.ico")
        if sys.platform == "win32" and icon.is_file():
            root.iconbitmap(default=str(icon))

        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure(".", font=("Segoe UI", 10), foreground=TEXT, background=PANEL)
        style.configure("TButton", padding=(12, 8), borderwidth=0, background="#26354a")
        style.map("TButton", background=[("active", "#354864")],
                  foreground=[("disabled", "#8d9ab0")])
        style.configure("Primary.TButton", background=ACCENT, foreground=BACKGROUND)
        style.map("Primary.TButton", background=[("active", "#adf5e2")])
        style.configure("TEntry", padding=8, fieldbackground=BACKGROUND,
                        insertcolor=TEXT, foreground=TEXT)
        style.configure("TNotebook", background=BACKGROUND, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(14, 7), background="#26354a")
        style.map("TNotebook.Tab", background=[("selected", PANEL)])

        header = tk.Frame(root, bg=BACKGROUND)
        header.pack(fill="x", padx=28, pady=(22, 18))
        logo = tk.Canvas(header, width=42, height=42, bg=BACKGROUND, highlightthickness=0)
        logo.pack(side="left", padx=(0, 12))
        logo.create_rectangle(1, 1, 41, 41, fill="#173a39", outline="")
        logo.create_oval(9, 10, 23, 24, outline=ACCENT, width=3)
        logo.create_line(21, 22, 32, 33, 35, 30, fill=ACCENT, width=3)
        logo.create_line(28, 29, 31, 26, fill=ACCENT, width=3)
        tk.Label(header, text="T0G StreamKey", bg=BACKGROUND, fg=TEXT,
                 font=("Segoe UI", 23, "bold")).pack(side="left")
        tk.Label(header, text=f"v{self.version}", bg=BACKGROUND, fg=MUTED,
                 font=("Segoe UI", 10)).pack(side="right")

        tabs = ttk.Notebook(root)
        tabs.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        main = ttk.Frame(tabs, padding=20)
        settings = ttk.Frame(tabs, padding=20)
        tabs.add(main, text="Credentials")
        tabs.add(settings, text="Settings")
        self.build_credentials(main)
        self.build_settings(settings)
        self.server.trace_add("write", self.on_edit)
        self.key.trace_add("write", self.on_edit)

    @staticmethod
    def read_version():
        root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
        with (root / "pyproject.toml").open("rb") as project:
            return tomllib.load(project)["project"]["version"]

    def build_credentials(self, panel):
        panel.columnconfigure(0, weight=1)
        ttk.Label(panel, text="TikTok RTMP credentials", font=("Segoe UI", 15, "bold")
                  ).grid(row=0, column=0, sticky="w")
        ttk.Button(panel, text="Open Streamlabs guide", command=self.open_guide
                   ).grid(row=0, column=1, columnspan=2, sticky="e")
        ttk.Label(panel, text="Streamlabs connection unavailable", foreground=MUTED
                  ).grid(row=1, column=0, sticky="w", pady=(4, 12))

        ttk.Label(panel, text="RTMP server URL").grid(row=2, column=0, sticky="w")
        self.server_entry = ttk.Entry(panel, textvariable=self.server)
        self.server_entry.grid(row=3, column=0, sticky="ew", pady=(4, 12))
        self.copy_server = ttk.Button(panel, text="Copy URL", state="disabled",
                                      command=lambda: self.copy("server"))
        self.copy_server.grid(row=3, column=1, sticky="ew", padx=(8, 0), pady=(4, 12))

        ttk.Label(panel, text="Stream key").grid(row=4, column=0, sticky="w")
        self.key_entry = ttk.Entry(panel, textvariable=self.key, show="•")
        self.key_entry.grid(row=5, column=0, sticky="ew", pady=(4, 12))
        self.copy_key = ttk.Button(panel, text="Copy key", state="disabled",
                                   command=lambda: self.copy("key"))
        self.copy_key.grid(row=5, column=1, sticky="ew", padx=(8, 0), pady=(4, 12))
        self.visibility = ttk.Button(panel, text="Show key", command=self.toggle_key)
        self.visibility.grid(row=5, column=2, padx=(8, 0), pady=(4, 12))

        actions = ttk.Frame(panel)
        actions.grid(row=6, column=0, columnspan=3, sticky="w")
        ttk.Button(actions, text="Use credentials", style="Primary.TButton",
                   command=self.apply).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Clear credentials", command=self.clear).pack(side="left")
        ttk.Separator(panel).grid(row=7, column=0, columnspan=3, sticky="ew", pady=16)
        ttk.Label(panel, textvariable=self.status, foreground=ACCENT,
                  font=("Segoe UI", 11, "bold")).grid(row=8, column=0, columnspan=3, sticky="w")
        ttk.Label(panel, textvariable=self.detail, foreground=MUTED, wraplength=540
                  ).grid(row=9, column=0, columnspan=3, sticky="w", pady=(4, 0))
        self.server_entry.focus_set()

    def build_settings(self, panel):
        ttk.Label(panel, text=f"T0G StreamKey v{self.version}",
                  font=("Segoe UI", 15, "bold")).pack(anchor="w")
        ttk.Label(panel, text="Credentials stay in memory until cleared or closed.",
                  foreground=MUTED).pack(anchor="w", pady=(8, 16))
        self.settings_status = tk.StringVar()
        ttk.Button(panel, text="Clear saved session", command=self.clear_session
                   ).pack(anchor="w", pady=(0, 8))
        ttk.Button(panel, text="Clear local application data", command=self.clear_data
                   ).pack(anchor="w")
        ttk.Label(panel, textvariable=self.settings_status, foreground=ACCENT,
                  wraplength=540).pack(anchor="w", pady=(8, 16))
        ttk.Label(panel, text="Troubleshooting", font=("Segoe UI", 11, "bold")
                  ).pack(anchor="w")
        ttk.Label(panel, text=(
            "TikTok must grant your account RTMP access. If your key expires, "
            "get a fresh URL and key from TikTok, paste both here, and choose Use credentials."
        ), foreground=MUTED, wraplength=540).pack(anchor="w", pady=(6, 0))

    def set_status(self, title, detail):
        self.status.set(title)
        self.detail.set(detail)

    def on_edit(self, *_):
        self.credentials = None
        self.copy_server.state(["disabled"])
        self.copy_key.state(["disabled"])
        self.set_status("Waiting for credentials", "Choose Use credentials to validate the current fields.")

    def open_guide(self):
        try:
            if webbrowser.open(STREAMLABS_GUIDE):
                return
        except (webbrowser.Error, OSError):
            pass
        self.set_status("Browser unavailable", "Open Streamlabs Support in your browser and search for TikTok stream key.")

    def apply(self):
        try:
            self.credentials = Credentials.parse(self.server.get(), self.key.get())
        except ValueError as error:
            self.set_status("Credentials unavailable", str(error))
            return
        self.copy_server.state(["!disabled"])
        self.copy_key.state(["!disabled"])
        self.set_status("Ready to copy", "Format checked locally. TikTok verifies the credentials when you stream.")

    def copy(self, field):
        if self.credentials is None:
            return
        value = getattr(self.credentials, field)
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(value)
        except tk.TclError:
            self.set_status("Clipboard unavailable", "Try copying again after closing other clipboard tools.")
            return
        self.clipboard_value = value
        self.set_status("Copied", "RTMP URL copied." if field == "server" else "Stream key copied.")

    def toggle_key(self):
        self.revealed = not self.revealed
        self.key_entry.configure(show="" if self.revealed else "•")
        self.visibility.configure(text="Hide key" if self.revealed else "Show key")

    def clear(self):
        if self.clipboard_value is not None:
            try:
                if self.root.clipboard_get() == self.clipboard_value:
                    self.root.clipboard_clear()
            except tk.TclError:
                pass
        self.clipboard_value = None
        self.credentials = None
        self.server.set("")
        self.key.set("")
        if self.revealed:
            self.toggle_key()
        self.set_status("Credentials cleared", "Paste new credentials when ready.")

    def clear_session(self):
        self.clear()
        self.settings_status.set("Local credentials cleared. Manage browser sign-in through Streamlabs.")

    def clear_data(self):
        self.clear()
        self.settings_status.set("Local credentials cleared. This edition stores no application data on disk.")

    def close(self):
        self.clear()
        self.root.destroy()


def main():
    root = tk.Tk()
    StreamKeyWindow(root)
    root.mainloop()
