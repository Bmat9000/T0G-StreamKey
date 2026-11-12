import sys
import queue
import threading
import tkinter as tk
from tkinter import ttk
import tomllib
import webbrowser
from pathlib import Path
from tkinter import messagebox

from streamkey.credentials import Credentials
from streamkey.streamlabs import (
    StreamlabsError, SessionRejected, StreamlabsTikTok, login_from_web,
    load_token_from_pc,
)

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
        self._client = None
        self._stream_id = ""
        self._busy = False
        self._events = queue.Queue()
        self.account_status = tk.StringVar(value="Streamlabs: disconnected")
        self.live_title = tk.StringVar()
        self.live_game = tk.StringVar()
        self.live_mature = tk.BooleanVar(value=False)

        root.title("T0G StreamKey")
        root.configure(background=BACKGROUND)
        root.minsize(720, 680)
        root.geometry("820x790")
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
        root.after(120, self._process_events)

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
        ttk.Label(panel, text="Manual entry or Streamlabs connection", foreground=MUTED
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
        ttk.Separator(panel).grid(row=10, column=0, columnspan=3, sticky="ew", pady=12)
        ttk.Label(panel, text="Get credentials through Streamlabs",
                  font=("Segoe UI", 13, "bold")).grid(row=11, column=0, columnspan=3, sticky="w")
        login_row = ttk.Frame(panel)
        login_row.grid(row=12, column=0, columnspan=3, sticky="w", pady=(8, 4))
        self.web_button = ttk.Button(login_row, text="Load from Web", command=self.connect_web)
        self.web_button.pack(side="left", padx=(0, 8))
        self.pc_button = ttk.Button(login_row, text="Load from PC", command=self.connect_pc)
        self.pc_button.pack(side="left", padx=(0, 8))
        self.refresh_button = ttk.Button(login_row, text="Refresh", command=self.refresh_account)
        self.refresh_button.pack(side="left", padx=(0, 8))
        self.disconnect_button = ttk.Button(login_row, text="Disconnect", command=self.disconnect)
        self.disconnect_button.pack(side="left")
        ttk.Label(panel, textvariable=self.account_status, foreground=MUTED
                  ).grid(row=13, column=0, columnspan=3, sticky="w", pady=(0, 8))
        live_row = ttk.Frame(panel)
        live_row.grid(row=14, column=0, columnspan=3, sticky="ew")
        live_row.columnconfigure(0, weight=2)
        live_row.columnconfigure(1, weight=1)
        ttk.Label(live_row, text="LIVE title").grid(row=0, column=0, sticky="w")
        ttk.Label(live_row, text="Game / category").grid(row=0, column=1, sticky="w", padx=(8, 0))
        ttk.Entry(live_row, textvariable=self.live_title).grid(row=1, column=0, sticky="ew", pady=(4, 8))
        ttk.Entry(live_row, textvariable=self.live_game).grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(4, 8))
        ttk.Checkbutton(panel, text="Mature audience", variable=self.live_mature
                        ).grid(row=15, column=0, sticky="w")
        live_actions = ttk.Frame(panel)
        live_actions.grid(row=16, column=0, columnspan=3, sticky="w", pady=(8, 4))
        self.start_button = ttk.Button(live_actions, text="Start LIVE / Get Key",
                                       style="Primary.TButton", command=self.start_live)
        self.start_button.pack(side="left", padx=(0, 8))
        self.end_button = ttk.Button(live_actions, text="End TikTok LIVE", command=self.end_live)
        self.end_button.pack(side="left")
        ttk.Label(panel, foreground=MUTED, wraplength=650,
                  text="Starting LIVE creates a real TikTok session; it does not start OBS. "
                       "Only select it when you're ready to stream. Never share your key."
                  ).grid(row=17, column=0, columnspan=3, sticky="w", pady=(4, 0))
        self._sync_buttons()
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
            "Your TikTok account must have the appropriate LIVE permission. "
            "Streamlabs Desktop endpoints are not a documented standalone app API, "
            "so web login or LIVE creation can stop working. "
            "The app has no updater, does not store tokens on disk, and does not "
            "require a separate T0G account."
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

    def _sync_buttons(self):
        waiting = self._busy
        connected = self._client is not None
        for button in (self.web_button, self.pc_button):
            button.state(["disabled"] if waiting else ["!disabled"])
        self.refresh_button.state(["disabled"] if waiting or not connected else ["!disabled"])
        self.disconnect_button.state(["disabled"] if waiting or not connected else ["!disabled"])
        self.start_button.state(
            ["disabled"] if waiting or not connected or bool(self._stream_id) else ["!disabled"])
        self.end_button.state(
            ["disabled"] if waiting or not connected or not self._stream_id else ["!disabled"])

    def _task(self, action, work):
        if self._busy:
            return
        self._busy = True
        self._sync_buttons()

        def worker():
            try:
                result = work()
                self._events.put((action, result, ""))
            except (StreamlabsError, ValueError) as error:
                self._events.put((action, None, str(error)))
            except Exception:
                # Do not leak exception bodies that might contain credentials.
                self._events.put((action, None, "An unexpected Streamlabs error occurred."))

        threading.Thread(target=worker, daemon=True).start()

    def _process_events(self):
        try:
            while True:
                action, data, error = self._events.get_nowait()
                self._busy = False
                if error:
                    if action in ("connect", "refresh", "start", "end"):
                        if "rejected the session" in error:
                            if self._client is not None:
                                self._client.disconnect()
                            self._client = None
                            self.account_status.set("Streamlabs: disconnected")
                    self.set_status("Streamlabs request failed", error)
                elif action == "connect":
                    token, account = data
                    if self._client is not None:
                        self._client.disconnect()
                    self._client = StreamlabsTikTok(token)
                    self._show_account(account)
                    self.set_status("Streamlabs connected", "Set a title and choose Start LIVE / Get Key.")
                elif action == "refresh":
                    self._show_account(data)
                    self.set_status("Account refreshed", "TikTok LIVE eligibility checked through Streamlabs.")
                elif action == "start":
                    self._stream_id = data.stream_id
                    self.server.set(data.credentials.server)
                    self.key.set(data.credentials.key)
                    self.apply()
                    self.set_status("TikTok LIVE created",
                                    "RTMP credentials are ready to copy. Start OBS when ready.")
                elif action == "end":
                    self._stream_id = ""
                    self.clear()
                    self.set_status("TikTok LIVE ended", "The stream key was cleared.")
                self._sync_buttons()
        except queue.Empty:
            pass
        if self.root.winfo_exists():
            self.root.after(120, self._process_events)

    def _show_account(self, account):
        label = "Approved for LIVE" if account.can_go_live else "LIVE access not confirmed"
        self.account_status.set(
            f"@{account.username}  |  {label}  |  Status: {account.status}")

    def connect_web(self):
        self.set_status("Streamlabs login", "Complete the sign-in in your web browser.")
        def work():
            token = login_from_web()
            client = StreamlabsTikTok(token)
            try:
                return token, client.get_account()
            finally:
                client.disconnect()
        self._task("connect", work)

    def connect_pc(self):
        self.set_status("Reading Streamlabs Desktop", "Checking the profile on this PC.")
        def work():
            token = load_token_from_pc()
            client = StreamlabsTikTok(token)
            try:
                return token, client.get_account()
            finally:
                client.disconnect()
        self._task("connect", work)

    def refresh_account(self):
        if self._client is not None:
            self._task("refresh", self._client.get_account)

    def start_live(self):
        if self._client is None:
            self.set_status("Not connected", "Load from Web or PC first.")
            return
        if self._stream_id:
            self.set_status("LIVE already created", "End the previous LIVE session first.")
            return
        title = self.live_title.get().strip()
        game = self.live_game.get().strip()
        mature = self.live_mature.get()
        if not title:
            self.set_status("Title required", "Enter the title for your TikTok LIVE.")
            return
        self.set_status("Creating TikTok LIVE", "Requesting an RTMP destination from Streamlabs.")
        def work():
            account = self._client.get_account()
            if not account.can_go_live:
                raise StreamlabsError("Streamlabs reports that this account cannot go LIVE.")
            return self._client.start_live(title, game, mature)
        self._task("start", work)

    def end_live(self):
        if self._client is None or not self._stream_id:
            return
        stream_id = self._stream_id
        self.set_status("Ending TikTok LIVE", "Requesting end confirmation from Streamlabs.")
        self._task("end", lambda: self._client.end_live(stream_id))

    def disconnect(self):
        if self._stream_id:
            self.set_status("LIVE session active",
                            "End TikTok LIVE before disconnecting from Streamlabs.")
            return
        if self._client is not None:
            self._client.disconnect()
            self._client = None
        self.account_status.set("Streamlabs: disconnected")
        self.clear()
        self._sync_buttons()

    def close(self):
        if getattr(self, "_busy", False):
            messagebox.showwarning("Streamlabs request in progress",
                                   "Finish the current Streamlabs request before closing.")
            return
        if getattr(self, "_client", None) is not None:
            self._client.disconnect()
        self.clear()
        self.root.destroy()


def main():
    root = tk.Tk()
    StreamKeyWindow(root)
    root.mainloop()
