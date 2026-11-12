"""T0G StreamKey: generate TikTok RTMP credentials with Streamlabs.

Nothing is typed into the RTMP URL or key fields: both are read-only. Save
persists ONLY the Streamlabs authentication token in Windows Credential Manager.
"""
import queue
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
import tomllib
import webbrowser

from streamkey.streamlabs import (
    StreamlabsError, SessionRejected, StreamlabsTikTok, TikTokCategory, login_from_web,
)
from streamkey.token_store import WindowsTokenStore, TokenStoreError

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
    def __init__(self, root: tk.Tk, token_store=None):
        self.root = root
        self.token_store = token_store if token_store is not None else WindowsTokenStore()
        self.credentials = None
        self.clipboard_value = None
        self._client = None
        self._stream_id = ""
        self._busy = False
        self._events = queue.Queue()
        self.status = tk.StringVar(value="Checking for a saved Streamlabs session...")
        self.detail = tk.StringVar(value="Save remembers your Streamlabs token, not your stream key.")
        self.account_status = tk.StringVar(value="Streamlabs: disconnected")
        self.server_display = tk.StringVar(value="Not generated")
        self.key_display = tk.StringVar(value="Not generated")
        self.live_title = tk.StringVar()
        self.live_game = tk.StringVar()
        self.live_audience = tk.StringVar(value="Everyone")
        self.category_hint = tk.StringVar(
            value="Search for a game, then select one of the results."
        )
        self._selected_category = None
        self._category_candidates = []
        self._category_generation = 0
        self._category_after = None
        self._setting_category = False

        root.title("T0G StreamKey")
        root.configure(background=BACKGROUND)
        root.minsize(690, 620)
        root.geometry("780x700")
        root.protocol("WM_DELETE_WINDOW", self.close)
        icon_path = Path(__file__).with_name("streamkey.ico")
        if sys.platform == "win32" and icon_path.is_file():
            root.iconbitmap(default=str(icon_path))

        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure(".", font=("Segoe UI", 10), foreground=TEXT, background=PANEL)
        style.configure("TButton", padding=(12, 8), background="#26354a", foreground=TEXT)
        style.map("TButton", background=[("active", "#354864")])
        style.configure("Primary.TButton", background=ACCENT, foreground=BACKGROUND)
        style.map("Primary.TButton", background=[("active", "#adf5e2")])
        style.configure("TEntry", padding=8, fieldbackground=BACKGROUND, foreground=TEXT)
        style.configure("TCombobox", padding=6, fieldbackground=BACKGROUND)
        style.configure("TNotebook", background=BACKGROUND, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(14, 7), background="#26354a")
        style.map("TNotebook.Tab", background=[("selected", PANEL)])

        header = tk.Frame(root, bg=BACKGROUND)
        header.pack(fill="x", padx=24, pady=(20, 12))
        tk.Label(header, text="T0G StreamKey", bg=BACKGROUND, fg=TEXT,
                 font=("Segoe UI", 23, "bold")).pack(side="left")
        tk.Label(header, text=f"v{self.read_version()}", bg=BACKGROUND, fg=MUTED
                 ).pack(side="right")

        tabs = ttk.Notebook(root)
        tabs.pack(fill="both", expand=True, padx=24, pady=(0, 18))
        main = ttk.Frame(tabs, padding=20)
        settings = ttk.Frame(tabs, padding=20)
        help_tab = ttk.Frame(tabs, padding=20)
        tabs.add(main, text="StreamKey")
        tabs.add(settings, text="Settings")
        tabs.add(help_tab, text="Need Help?")
        self.tabs = tabs
        self.help_tab = help_tab
        self.last_content_tab = str(main)
        self.build_main(main)
        self.build_settings(settings)
        tabs.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        self.live_game.trace_add("write", self._category_changed)
        self._sync_buttons()
        root.after(120, self._process_events)
        self.restore_saved()

    @staticmethod
    def read_version():
        root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
        with (root / "pyproject.toml").open("rb") as project:
            return tomllib.load(project)["project"]["version"]

    def build_main(self, panel):
        panel.columnconfigure(0, weight=1)
        ttk.Label(panel, text="TikTok RTMP credentials",
                  font=("Segoe UI", 15, "bold")).grid(
                      row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(panel, textvariable=self.account_status, foreground=MUTED
                  ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 14))

        top = ttk.Frame(panel)
        top.grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 14))
        self.web_button = ttk.Button(top, text="Load from Web", command=self.connect_web)
        self.web_button.pack(side="left", padx=(0, 8))
        self.save_button = ttk.Button(top, text="Save", command=self.save_token)
        self.save_button.pack(side="left", padx=(0, 8))
        live = ttk.Frame(panel)
        live.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 16))
        live.columnconfigure(0, weight=1)
        live.columnconfigure(1, weight=1)

        ttk.Label(live, text="LIVE title", foreground=MUTED).grid(
            row=0, column=0, columnspan=2, sticky="w")
        self.title_entry = ttk.Entry(live, textvariable=self.live_title)
        self.title_entry.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(5, 12))

        ttk.Label(live, text="Game / category", foreground=MUTED).grid(
            row=2, column=0, sticky="w")
        ttk.Label(live, text="Audience", foreground=MUTED).grid(
            row=2, column=1, sticky="w", padx=(12, 0))
        self.category_entry = ttk.Entry(live, textvariable=self.live_game)
        self.category_entry.grid(row=3, column=0, sticky="ew", pady=(5, 3))
        self.category_entry.bind("<Down>", self._focus_categories)
        self.category_entry.bind("<Return>", self._choose_first_category)
        self.category_entry.bind("<Escape>", lambda _event: self._hide_categories())
        self.audience_dropdown = ttk.Combobox(
            live, textvariable=self.live_audience,
            values=("Everyone", "18+"), state="readonly", width=16
        )
        self.audience_dropdown.grid(
            row=3, column=1, sticky="ew", padx=(12, 0), pady=(5, 3))

        self.category_list = tk.Listbox(
            live, height=5, exportselection=False,
            bg=BACKGROUND, fg=TEXT, selectbackground="#354864",
            selectforeground=TEXT, borderwidth=1, relief="solid"
        )
        self.category_list.grid(row=4, column=0, sticky="ew", pady=(1, 2))
        self.category_list.grid_remove()
        self.category_list.bind("<ButtonRelease-1>", self._choose_category)
        self.category_list.bind("<Return>", self._choose_category)
        self.category_list.bind("<Escape>", self._focus_game)
        ttk.Label(live, textvariable=self.category_hint, foreground=MUTED,
                  wraplength=460).grid(
                      row=5, column=0, columnspan=2, sticky="w", pady=(4, 0))

        ttk.Label(panel, text="RTMP URL", foreground=MUTED).grid(
            row=4, column=0, sticky="w")
        url_row = ttk.Frame(panel)
        url_row.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(5, 14))
        url_row.columnconfigure(0, weight=1)
        ttk.Label(url_row, textvariable=self.server_display, anchor="w",
                  background=BACKGROUND, padding=10).grid(row=0, column=0, sticky="ew")
        self.copy_server = ttk.Button(url_row, text="Copy URL",
                                      command=lambda: self.copy("server"))
        self.copy_server.grid(row=0, column=1, padx=(8, 0))

        ttk.Label(panel, text="Stream Key", foreground=MUTED).grid(
            row=6, column=0, sticky="w")
        key_row = ttk.Frame(panel)
        key_row.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(5, 16))
        key_row.columnconfigure(0, weight=1)
        ttk.Label(key_row, textvariable=self.key_display, anchor="w",
                  background=BACKGROUND, padding=10).grid(row=0, column=0, sticky="ew")
        self.copy_key = ttk.Button(key_row, text="Copy Key",
                                   command=lambda: self.copy("key"))
        self.copy_key.grid(row=0, column=1, padx=(8, 0))

        actions = ttk.Frame(panel)
        actions.grid(row=8, column=0, columnspan=2, sticky="w")
        self.start_button = ttk.Button(actions, text="Start",
                                        style="Primary.TButton", command=self.start_live)
        self.start_button.pack(side="left", padx=(0, 8))
        self.stop_button = ttk.Button(actions, text="Stop", command=self.stop_live)
        self.stop_button.pack(side="left")
        ttk.Separator(panel).grid(row=9, column=0, columnspan=2,
                                  sticky="ew", pady=16)
        ttk.Label(panel, textvariable=self.status, foreground=ACCENT,
                  font=("Segoe UI", 11, "bold")).grid(
                      row=10, column=0, columnspan=2, sticky="w")
        ttk.Label(panel, textvariable=self.detail, foreground=MUTED,
                  wraplength=590).grid(row=11, column=0, columnspan=2,
                                        sticky="w", pady=(6, 0))

    def build_settings(self, panel):
        ttk.Label(panel, text="Saved Streamlabs session",
                  font=("Segoe UI", 14, "bold")).pack(anchor="w")
        ttk.Label(panel, text=(
            "Save stores only your Streamlabs authentication token in Windows "
            "Credential Manager. This Windows user can restore it automatically "
            "when you reopen StreamKey. RTMP URLs and stream keys are never saved."
        ), foreground=MUTED, wraplength=575).pack(anchor="w", pady=(8, 14))
        self.forget_button = ttk.Button(panel, text="Forget saved Streamlabs token",
                                        command=self.forget_saved)
        self.forget_button.pack(anchor="w")
        ttk.Label(panel, text=(
            "A rejected or expired token is removed automatically. "
            "If generating credentials fails for another reason, use Load from Web "
            "to reauthenticate. Start creates a TikTok LIVE session; Stop ends it "
            "through Streamlabs. Closing StreamKey does not end a LIVE session."
        ), foreground=MUTED, wraplength=575).pack(anchor="w", pady=(16, 0))

    def set_status(self, title, detail):
        self.status.set(title)
        self.detail.set(detail)

    def _sync_buttons(self):
        waiting = self._busy
        connected = self._client is not None
        live = bool(self._stream_id)
        self.web_button.state(["disabled"] if waiting or live else ["!disabled"])
        self.save_button.state(["disabled"] if waiting or not connected else ["!disabled"])
        self.start_button.state(["disabled"] if waiting or not connected or live else ["!disabled"])
        self.stop_button.state(["disabled"] if waiting or not connected or not live else ["!disabled"])
        has_credentials = self.credentials is not None
        for copy_button in (self.copy_server, self.copy_key):
            copy_button.state(["!disabled"] if has_credentials else ["disabled"])
        self.forget_button.state(["disabled"] if waiting or live else ["!disabled"])
        for field in (self.title_entry, self.category_entry):
            field.state(["disabled"] if waiting or live else ["!disabled"])
        self.audience_dropdown.state(["disabled"] if waiting or live else ["readonly"])

    def _hide_categories(self):
        self.category_list.grid_remove()

    def _focus_game(self, _event=None):
        self._hide_categories()
        self.category_entry.focus_set()
        return "break"

    def _focus_categories(self, _event=None):
        if self.category_list.winfo_ismapped() and self._category_candidates:
            self.category_list.focus_set()
            self.category_list.selection_clear(0, tk.END)
            self.category_list.selection_set(0)
            self.category_list.activate(0)
        return "break"

    def _choose_first_category(self, _event=None):
        if self.category_list.winfo_ismapped() and self._category_candidates:
            self.category_list.selection_clear(0, tk.END)
            self.category_list.selection_set(0)
            self._choose_category()
        return "break"

    def _choose_category(self, _event=None):
        selection = self.category_list.curselection()
        if not selection:
            return "break"
        idx = selection[0]
        if not 0 <= idx < len(self._category_candidates):
            return "break"
        selected = self._category_candidates[idx]
        self._setting_category = True
        try:
            self.live_game.set(selected.name)
        finally:
            self._setting_category = False
        self._selected_category = selected
        self._hide_categories()
        self.category_hint.set("Selected: " + selected.name)
        self.category_entry.focus_set()
        return "break"

    def _category_changed(self, *_args):
        if self._setting_category:
            return
        self._selected_category = None
        self._category_candidates = []
        self._category_generation += 1
        generation = self._category_generation
        self._hide_categories()
        if self._category_after is not None:
            self.root.after_cancel(self._category_after)
            self._category_after = None
        query = self.live_game.get().strip()
        if not self._client:
            self.category_hint.set("Connect Streamlabs to search for TikTok games.")
        elif len(query) < 2:
            self.category_hint.set("Type at least 2 letters to search for a game.")
        else:
            self.category_hint.set("Searching for matching games...")
            client = self._client
            self._category_after = self.root.after(
                300, lambda: self._request_categories(query, generation, client))

    def _request_categories(self, query, generation, client):
        self._category_after = None

        def work():
            try:
                result = client.search_categories(query)
                self._events.put(("categories", (generation, query, client, result), None))
            except SessionRejected:
                self._events.put(("categories", (generation, query, client, []), "expired"))
            except StreamlabsError:
                self._events.put(("categories", (generation, query, client, []), "error"))
            except Exception:
                self._events.put(("categories", (generation, query, client, []), "error"))

        threading.Thread(target=work, daemon=True).start()

    def _receive_categories(self, result, error):
        generation, query, client, choices = result
        if (generation != self._category_generation or client is not self._client
                or query != self.live_game.get().strip()):
            return
        if error == "expired":
            self._invalidate_token()
            self._sync_buttons()
            return
        if error:
            self.category_hint.set("Game search failed. Check Streamlabs and try typing again.")
            return
        self._category_candidates = choices
        self.category_list.delete(0, tk.END)
        for candidate in choices:
            self.category_list.insert(tk.END, candidate.name)
        if choices:
            self.category_list.configure(height=min(6, len(choices)))
            self.category_list.grid()
            self.category_hint.set("Select a game from the suggestions, or choose Other.")
        else:
            self.category_hint.set("No matching games. Try a different search.")

    def _task(self, action, work):
        if self._busy:
            return
        self._busy = True
        self._sync_buttons()

        def worker():
            try:
                self._events.put((action, work(), None))
            except SessionRejected:
                self._events.put((action, None, "expired"))
            except (StreamlabsError, TokenStoreError) as exc:
                self._events.put((action, None, str(exc)))
            except Exception:
                # Exception representations may contain response bodies or tokens.
                self._events.put((action, None, "Unexpected error; please try again."))

        threading.Thread(target=worker, daemon=True).start()

    def _process_events(self):
        try:
            while True:
                action, result, error = self._events.get_nowait()
                if action == "categories":
                    self._receive_categories(result, error)
                    continue
                self._busy = False
                if error == "expired":
                    self._invalidate_token()
                elif error:
                    self.set_status("Streamlabs request failed", error + (
                        " Use Load from Web to reconnect if it keeps failing."
                        if action in ("start", "restore", "connect") else ""
                    ))
                elif action in ("restore", "connect"):
                    if result is None:
                        self.set_status("No saved session",
                                        "Click Load from Web once, then Save to remember the token.")
                    else:
                        token, account = result
                        if self._client is not None:
                            self._client.disconnect()
                        self._client = StreamlabsTikTok(token)
                        self._selected_category = None
                        self._category_generation += 1
                        self._hide_categories()
                        self.category_hint.set(
                            "Search for a game, then select one of the results.")
                        self.account_status.set(
                            f"@{account.username} | " +
                            ("LIVE enabled" if account.can_go_live else "LIVE access unavailable")
                        )
                        self.set_status("Streamlabs connected",
                                        "Click Save to remember this login, or Start to get new credentials."
                                        if action == "connect" else
                                        "Saved Streamlabs token restored. Click Start to get new credentials.")
                elif action == "start":
                    self._stream_id = result.stream_id
                    self.credentials = result.credentials
                    self.server_display.set(result.credentials.server)
                    self.key_display.set("••••••••••••••••••••")
                    self.set_status("RTMP credentials generated",
                                    "Copy the URL and key into OBS. Click Stop when finished.")
                elif action == "stop":
                    self._stream_id = ""
                    self.clear_credentials()
                    self.set_status("TikTok LIVE ended",
                                    "Stream key cleared; saved Streamlabs token is still available.")
                self._sync_buttons()
        except queue.Empty:
            pass
        if self.root.winfo_exists():
            self.root.after(120, self._process_events)

    def _connect_token(self, token):
        client = StreamlabsTikTok(token)
        try:
            return token, client.get_account()
        finally:
            client.disconnect()

    def restore_saved(self):
        self._task("restore", lambda: self._restore_saved_worker())

    def _restore_saved_worker(self):
        token = self.token_store.load()
        return self._connect_token(token) if token else None

    def connect_web(self):
        if self._stream_id:
            self.set_status("Stop LIVE first", "End your current session before reconnecting.")
            return
        self.set_status("Streamlabs sign-in", "Complete login in your browser.")
        self._task("connect", lambda: self._connect_token(login_from_web()))

    def save_token(self):
        if self._busy or self._client is None:
            self.set_status("Nothing to save", "Connect with Load from Web first.")
            return
        try:
            self.token_store.save(self._client.token)
        except TokenStoreError as exc:
            self.set_status("Save failed", str(exc))
            return
        self.set_status("Streamlabs token saved",
                        "It will load automatically the next time you open StreamKey.")

    def _invalidate_token(self):
        if self._client is not None:
            self._client.disconnect()
        self._client = None
        # Invalid tokens should not be restored on a later launch.
        try:
            self.token_store.clear()
            detail = "Use Load from Web to sign in again, then Save the new token."
        except TokenStoreError:
            detail = ("Use Load from Web, then Save again. "
                      "Could not remove the expired token from Windows Credential Manager.")
        self.account_status.set("Streamlabs: token expired or rejected")
        self._category_generation += 1
        self._selected_category = None
        self._hide_categories()
        self.category_hint.set("Reconnect Streamlabs to search for games.")
        self.clear_credentials()
        self._stream_id = ""
        self.set_status("Streamlabs session expired", detail)

    def start_live(self):
        if self._client is None:
            self.set_status("Not connected", "Use Load from Web and Save your login.")
            return
        if self._stream_id:
            self.set_status("Already started", "Stop the current LIVE session first.")
            return
        title = self.live_title.get().strip()
        if not title:
            self.set_status("LIVE title required", "Enter a title before pressing Start.")
            self.title_entry.focus_set()
            return
        category = self._selected_category
        if category is None or category.name != self.live_game.get().strip():
            self.set_status("Select a game",
                            "Search for a game and select it from the results before starting.")
            self.category_entry.focus_set()
            return
        audience = self.live_audience.get()
        if audience not in ("Everyone", "18+"):
            self.set_status("Invalid audience", "Choose Everyone or 18+.")
            return
        self._hide_categories()
        self.set_status("Requesting TikTok credentials",
                        "Starting a TikTok LIVE session through Streamlabs.")
        def work():
            account = self._client.get_account()
            if not account.can_go_live:
                raise StreamlabsError("Streamlabs says this account does not have LIVE access.")
            return self._client.start_live(
                title, category.name, audience == "18+", category_id=category.id)
        self._task("start", work)

    def stop_live(self):
        if self._client is None or not self._stream_id:
            return
        stream_id = self._stream_id
        self.set_status("Ending TikTok LIVE", "Waiting for Streamlabs to confirm Stop.")
        self._task("stop", lambda: self._client.end_live(stream_id))

    def copy(self, name):
        if self.credentials is None or name not in ("server", "key"):
            return
        value = getattr(self.credentials, name)
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(value)
        except tk.TclError:
            self.set_status("Clipboard unavailable", "Close other clipboard tools and try again.")
            return
        self.clipboard_value = value
        self.set_status("Copied", "RTMP URL copied." if name == "server" else "Stream key copied.")

    def clear_credentials(self):
        if self.clipboard_value is not None:
            try:
                if self.root.clipboard_get() == self.clipboard_value:
                    self.root.clipboard_clear()
            except tk.TclError:
                pass
        self.clipboard_value = None
        self.credentials = None
        self.server_display.set("Not generated")
        self.key_display.set("Not generated")

    def forget_saved(self):
        if self._stream_id:
            self.set_status("Stop LIVE first", "End the current session before forgetting your login.")
            return
        try:
            self.token_store.clear()
        except TokenStoreError as exc:
            self.set_status("Could not forget token", str(exc))
            return
        if self._client is not None:
            self._client.disconnect()
        self._client = None
        self.account_status.set("Streamlabs: disconnected")
        self._category_generation += 1
        self._selected_category = None
        self._hide_categories()
        self.clear_credentials()
        self._sync_buttons()
        self.set_status("Saved token forgotten", "Use Load from Web again to sign in.")

    def _on_tab_changed(self, _event=None):
        selected = self.tabs.select()
        if selected == str(self.help_tab):
            # Need Help? behaves as an action next to Settings, not a blank page.
            self.tabs.select(self.last_content_tab)
            self.root.after(0, self.need_help)
        else:
            self.last_content_tab = selected

    def need_help(self):
        messagebox.showinfo(
            "T0G StreamKey help",
            "1. Click Load from Web and complete Streamlabs / TikTok login.\n"
            "2. Click Save once to remember the Streamlabs token on this PC.\n"
            "3. Enter a LIVE title, search and select your game/category, "
            "and choose Everyone or 18+.\n"
            "4. Click Start to create a TikTok LIVE session and generate credentials.\n"
            "5. Use Copy URL and Copy Key in OBS.\n"
            "6. Click Stop to end your LIVE session.\n\n"
            "Only sign in again if the token expires or Streamlabs cannot generate "
            "credentials. An eligible TikTok LIVE account is required."
        )
        webbrowser.open(STREAMLABS_GUIDE)

    def close(self):
        if self._busy:
            messagebox.showwarning("Please finish the current request",
                                   "A Streamlabs request is in progress.")
            return
        if self._client is not None:
            self._client.disconnect()
        self.clear_credentials()
        self.root.destroy()


def main():
    root = tk.Tk()
    StreamKeyWindow(root)
    root.mainloop()
