from __future__ import annotations

import getpass
import queue
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, ttk

from .achievements import AchievementEngine, default_achievements, load_state, save_state
from .core import create_backup, export_pack, human_size, import_pack, preview_import_pack, restore_backup, scan_codex
from .phase2 import LocalAuthStore, ShareCodeStore
from .paths import ACHIEVEMENT_ICON_DIR, BACKUP_DIR, DATA_DIR, EXPORT_DIR, IMPORT_HISTORY_FILE, STATE_FILE, ensure_runtime_dirs, startup_diagnostics
from .workflow import edit_memory_file, list_memories, list_skills


APP_NAME = "Codex Vault"

BG = "#080b12"
PANEL = "#121827"
PANEL_2 = "#182236"
PANEL_3 = "#202c44"
TEXT = "#f5f7fb"
MUTED = "#94a3b8"
DIM = "#5f6b80"
CYAN = "#22d3ee"
TEAL = "#2dd4bf"
GOLD = "#f8c555"
PURPLE = "#a78bfa"
ORANGE = "#fb923c"
GREEN = "#4ade80"


def default_codex_path() -> Path:
    home_path = Path.home() / ".codex"
    if home_path.exists():
        return home_path
    return Path("D:/AI_cpt/.codex")


class VaultCard(tk.Frame):
    def __init__(self, master, title: str = "", accent: str = CYAN, **kwargs):
        super().__init__(master, bg=PANEL, highlightthickness=1, highlightbackground="#263247", **kwargs)
        if title:
            top = tk.Frame(self, bg=PANEL)
            top.pack(fill="x", padx=16, pady=(12, 4))
            tk.Label(top, text="●", fg=accent, bg=PANEL, font=("Consolas", 12)).pack(side="left")
            tk.Label(top, text=title, fg=TEXT, bg=PANEL, font=("Segoe UI Semibold", 12)).pack(side="left", padx=(8, 0))


class CodexVaultApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Codex Vault")
        self.overrideredirect(True)
        self.geometry("1360x820")
        self.minsize(1180, 720)
        self.configure(bg=BG)

        self.codex_path = default_codex_path()
        self.scan = None
        self.skills = []
        self.memories = []
        self.current_memory_path: str | None = None
        self.current_user: str | None = None
        self.achievement_rects: dict[int, object] = {}
        self.auth = LocalAuthStore(DATA_DIR / "auth")
        self.share_store = ShareCodeStore(DATA_DIR / "share_codes")
        self.state_data = load_state(STATE_FILE)
        self.metrics = dict(self.state_data.get("metrics", {}))
        self.notification_history = list(self.state_data.get("notifications", []))
        self.activated_achievement_ids = set(self.state_data.get("activated", []))
        self.achievement_history_details = dict(self.state_data.get("achievementHistory", {}))
        self.engine = AchievementEngine(default_achievements(), set(self.state_data.get("unlocked", [])))
        self.views: dict[str, tk.Frame] = {}
        self.achievement_bounds: dict[int, tuple[int, int, int, int]] = {}
        self.achievement_button_bounds: dict[int, tuple[int, int, int, int]] = {}
        self.achievement_activate_bounds: dict[int, tuple[int, int, int, int]] = {}
        self.achievement_progress_bounds: dict[int, tuple[int, int, int, int]] = {}
        self.achievement_description_items: dict[int, object] = {}
        self.achievement_icon_items: dict[int, object] = {}
        self.achievement_icon_images = self.load_achievement_icons("card")
        self.achievement_detail_icon_images = self.load_achievement_icons("detail")
        self.activation_animation_items: list[object] = []
        self.activation_animation_target: int | None = None
        self.activation_animation_job: str | None = None
        self._achievement_render_width = 0
        self._achievement_resize_job: str | None = None
        self.toast_messages: list[dict[str, str]] = []
        self.status_events: list[str] = []
        self.active_toasts: list[tk.Frame] = []
        self.status_reset_job: str | None = None
        self._scan_in_progress = False
        self._scan_token = 0
        self._pending_scan_root: Path | None = None
        self._scan_results: queue.Queue = queue.Queue()
        self._scan_poll_job: str | None = None
        self._startup_scan_job: str | None = None
        self._task_results: queue.Queue = queue.Queue()
        self._task_callbacks: dict[int, tuple[object, object | None]] = {}
        self._task_token = 0
        self._task_poll_job: str | None = None
        self._task_in_progress = False
        self._toast_jobs: list[str] = []
        self._close_requested = False
        self._drag_start: tuple[int, int] | None = None
        self._normal_geometry = "1360x820"

        self._style()
        self.protocol("WM_DELETE_WINDOW", self.request_close)
        self.bind("<Escape>", lambda _event: self.hide_detail_overlay())
        self._build_shell()
        self.report_startup_diagnostics()
        self.bind("<Map>", self._restore_chrome_after_minimize)
        self.show_view("overview")
        self._startup_scan_job = self.after(500, self.refresh_in_background)

    def load_achievement_icons(self, variant: str) -> list[tk.PhotoImage]:
        icons: list[tk.PhotoImage] = []
        for index in range(25):
            path = ACHIEVEMENT_ICON_DIR / f"ach_{index:02d}_{variant}.png"
            if not path.exists():
                continue
            icons.append(tk.PhotoImage(file=str(path)))
        return icons

    def report_startup_diagnostics(self) -> None:
        issues = startup_diagnostics()
        if not issues:
            self.append_status_log(f"Runtime data: {DATA_DIR}", "info")
            return
        self.set_status(issues[0], "error")
        for issue in issues:
            self.append_status_log(issue, "error")

    def request_close(self) -> None:
        self._close_requested = True
        self.hide_detail_overlay()
        self.quit()
        self.destroy()

    def destroy(self) -> None:
        for job in [self.status_reset_job, self._scan_poll_job, self._task_poll_job, self._startup_scan_job, self.activation_animation_job, *self._toast_jobs]:
            if job:
                try:
                    self.after_cancel(job)
                except tk.TclError:
                    pass
        super().destroy()

    def _style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Treeview", background="#0d1320", fieldbackground="#0d1320", foreground=TEXT, rowheight=30, borderwidth=0)
        style.configure("Treeview.Heading", background=PANEL_2, foreground=TEXT, font=("Segoe UI Semibold", 10), borderwidth=0)
        style.map("Treeview", background=[("selected", "#1f3a5a")], foreground=[("selected", TEXT)])
        style.configure(
            "Vault.Vertical.TScrollbar",
            gripcount=0,
            background="#24324a",
            darkcolor="#24324a",
            lightcolor="#24324a",
            troughcolor="#0a0f1c",
            bordercolor="#0a0f1c",
            arrowcolor=CYAN,
            relief="flat",
            width=12,
        )
        style.map(
            "Vault.Vertical.TScrollbar",
            background=[("active", CYAN), ("pressed", TEAL)],
            arrowcolor=[("active", TEXT)],
        )

    def _build_shell(self) -> None:
        self.window = tk.Frame(self, bg=BG, highlightthickness=1, highlightbackground="#1f2a3d")
        self.window.pack(fill="both", expand=True)
        self._build_titlebar()

        self.body = tk.Frame(self.window, bg=BG)
        self.body.pack(fill="both", expand=True)

        self.sidebar = tk.Frame(self.body, bg="#070a10", width=220)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        brand = tk.Frame(self.sidebar, bg="#070a10")
        brand.pack(fill="x", padx=18, pady=(22, 18))
        tk.Label(brand, text="CODEX", fg=CYAN, bg="#070a10", font=("Consolas", 10, "bold")).pack(anchor="w")
        tk.Label(brand, text="VAULT", fg=TEXT, bg="#070a10", font=("Segoe UI Black", 24)).pack(anchor="w")
        tk.Label(brand, text="Phase 2 Local Sync Lab", fg=MUTED, bg="#070a10", font=("Segoe UI", 9)).pack(anchor="w", pady=(2, 0))

        self.nav_buttons: dict[str, tk.Button] = {}
        for key, label in [
            ("overview", "Dashboard"),
            ("skills", "Skills"),
            ("memory", "Memory"),
            ("sync", "Sync / Packs"),
            ("achievements", "Achievements"),
            ("account", "Account"),
        ]:
            btn = tk.Button(
                self.sidebar,
                text=label,
                anchor="w",
                bg="#070a10",
                fg=MUTED,
                activebackground="#101827",
                activeforeground=TEXT,
                relief="flat",
                font=("Segoe UI Semibold", 11),
                padx=18,
                pady=12,
                command=lambda name=key: self.show_view(name),
            )
            btn.pack(fill="x", padx=10, pady=2)
            self.nav_buttons[key] = btn

        bottom = tk.Frame(self.sidebar, bg="#070a10")
        bottom.pack(side="bottom", fill="x", padx=18, pady=18)
        tk.Label(bottom, text="LOCAL ONLY", fg=TEAL, bg="#070a10", font=("Consolas", 9, "bold")).pack(anchor="w")
        tk.Label(bottom, text="No cloud upload in this build", fg=DIM, bg="#070a10", font=("Segoe UI", 8)).pack(anchor="w")

        self.main = tk.Frame(self.body, bg=BG)
        self.main.pack(side="left", fill="both", expand=True)
        self._build_header()
        self.content = tk.Frame(self.main, bg=BG)
        self.content.pack(fill="both", expand=True, padx=22, pady=(0, 12))

        for key in ["overview", "skills", "memory", "sync", "achievements", "account"]:
            self.views[key] = tk.Frame(self.content, bg=BG)
        self._build_overview()
        self._build_skills()
        self._build_memory()
        self._build_sync()
        self._build_achievements()
        self._build_account()
        self._build_statusbar()
        self._build_toast_host()
        self._build_detail_overlay()
        self.set_status("Ready. Scan your .codex vault to begin.", "info")

    def _build_titlebar(self) -> None:
        bar = tk.Frame(self.window, bg="#050812", height=42, highlightthickness=0)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        grip = tk.Frame(bar, bg="#050812")
        grip.pack(side="left", fill="both", expand=True)
        for widget in (bar, grip):
            widget.bind("<ButtonPress-1>", self._start_window_drag)
            widget.bind("<B1-Motion>", self._drag_window)

        brand = tk.Frame(grip, bg="#050812")
        brand.pack(side="left", padx=16, fill="y")
        tk.Label(brand, text="CODEX VAULT", fg=TEXT, bg="#050812", font=("Segoe UI Semibold", 11)).pack(side="left")
        tk.Label(brand, text="v0.2 local confidence build", fg=TEAL, bg="#101827", font=("Consolas", 9), padx=10, pady=3).pack(side="left", padx=(12, 0))
        tk.Label(grip, text="local-first .codex migration cockpit", fg=MUTED, bg="#050812", font=("Segoe UI", 9)).pack(side="left", padx=(14, 0))

        controls = tk.Frame(bar, bg="#050812")
        controls.pack(side="right", fill="y")
        for text, command, hover in [
            ("-", self._minimize_window, "#132238"),
            ("□", self._toggle_maximize, "#132238"),
            ("×", self.request_close, "#4a1720"),
        ]:
            btn = tk.Button(
                controls,
                text=text,
                command=command,
                width=5,
                bg="#050812",
                fg=TEXT,
                activebackground=hover,
                activeforeground=TEXT,
                relief="flat",
                font=("Segoe UI", 11),
                cursor="hand2",
                takefocus=0,
            )
            btn.pack(side="left", fill="y")

    def _start_window_drag(self, event) -> None:
        self._drag_start = (event.x_root - self.winfo_x(), event.y_root - self.winfo_y())

    def _drag_window(self, event) -> None:
        if self._drag_start and self.state() == "normal":
            dx, dy = self._drag_start
            self.geometry(f"+{event.x_root - dx}+{event.y_root - dy}")

    def _minimize_window(self) -> None:
        self.overrideredirect(False)
        self.iconify()

    def _restore_chrome_after_minimize(self, _event=None) -> None:
        if self.state() == "normal":
            self.after(10, lambda: self.overrideredirect(True))

    def _toggle_maximize(self) -> None:
        if self.state() == "zoomed":
            self.state("normal")
            self.geometry(self._normal_geometry)
        else:
            self._normal_geometry = self.geometry()
            self.state("zoomed")

    def _build_header(self) -> None:
        header = tk.Frame(self.main, bg=BG)
        header.pack(fill="x", padx=22, pady=(20, 14))
        left = tk.Frame(header, bg=BG)
        left.pack(side="left", fill="x", expand=True)
        tk.Label(left, text="Vault Control Center", fg=TEXT, bg=BG, font=("Segoe UI Black", 22)).pack(anchor="w")
        tk.Label(left, text="Skills health, memory editor, local share codes, achievements", fg=MUTED, bg=BG, font=("Segoe UI", 10)).pack(anchor="w")
        right = tk.Frame(header, bg=BG)
        right.pack(side="right")
        self.path_var = tk.StringVar(value=str(self.codex_path))
        self.path_entry = tk.Entry(right, textvariable=self.path_var, width=56, bg="#0d1320", fg=TEXT, insertbackground=TEXT, relief="flat", font=("Consolas", 9))
        self.path_entry.pack(side="left", ipady=8, padx=(0, 8))
        self.path_entry.bind("<Return>", lambda _event: self.refresh_in_background())
        self.action_button(right, "Browse", self.choose_path, CYAN).pack(side="left", padx=4)
        self.action_button(right, "Scan", self.refresh_in_background, TEAL).pack(side="left", padx=4)

    def _build_statusbar(self) -> None:
        self.status_bar = tk.Frame(self.main, bg="#0a0f1c", highlightthickness=1, highlightbackground="#1f2a3d")
        self.status_bar.pack(fill="x", padx=22, pady=(0, 18))
        top = tk.Frame(self.status_bar, bg="#0a0f1c")
        top.pack(fill="x")
        self.status_dot = tk.Label(top, text="●", fg=CYAN, bg="#0a0f1c", font=("Consolas", 10))
        self.status_dot.pack(side="left", padx=(12, 8), pady=(8, 2))
        self.status_var = tk.StringVar()
        self.status_label = tk.Label(top, textvariable=self.status_var, fg=MUTED, bg="#0a0f1c", font=("Segoe UI", 9), anchor="w")
        self.status_label.pack(side="left", fill="x", expand=True, pady=(8, 2))
        self.status_meta = tk.Label(top, text="LOCAL", fg=TEAL, bg="#0a0f1c", font=("Consolas", 9, "bold"))
        self.status_meta.pack(side="right", padx=12, pady=(8, 2))
        self.status_log = tk.Text(self.status_bar, height=2, bg="#070a10", fg=DIM, insertbackground=TEXT, relief="flat", wrap="none", font=("Consolas", 8))
        self.status_log.pack(fill="x", padx=12, pady=(0, 8))
        self.status_log.configure(state="disabled")

    def _build_toast_host(self) -> None:
        self.toast_host = tk.Frame(self.main, bg=BG)

    def show_toast_host(self) -> None:
        if not self.toast_host.place_info():
            self.toast_host.place(relx=1.0, rely=0.0, x=-24, y=88, anchor="ne")

    def dismiss_toast(self, toast: tk.Frame) -> None:
        if toast in self.active_toasts:
            self.active_toasts.remove(toast)
        try:
            if toast.winfo_exists():
                toast.destroy()
        except tk.TclError:
            pass
        if not self.active_toasts and hasattr(self, "toast_host"):
            self.toast_host.place_forget()

    def _build_detail_overlay(self) -> None:
        self.detail_overlay = tk.Frame(self.main, bg="#050812")
        self.detail_overlay.place_forget()
        self.detail_overlay.bind("<Button-1>", lambda _event: self.hide_detail_overlay())
        self.detail_card = tk.Frame(self.detail_overlay, bg=PANEL, highlightthickness=1, highlightbackground="#334155")
        self.detail_card.place(relx=0.5, rely=0.5, anchor="center", width=620, height=430)
        self.detail_card.bind("<Button-1>", lambda event: "break")
        chrome = tk.Frame(self.detail_card, bg="#050812", height=40)
        chrome.pack(fill="x")
        chrome.pack_propagate(False)
        self.detail_title_var = tk.StringVar(value="Achievement Detail")
        tk.Label(chrome, textvariable=self.detail_title_var, fg=TEXT, bg="#050812", font=("Segoe UI Semibold", 10)).pack(side="left", padx=14)
        close_btn = tk.Button(chrome, text="×", command=self.hide_detail_overlay, bg="#050812", fg=TEXT, activebackground="#4a1720", activeforeground=TEXT, relief="flat", width=5, cursor="hand2", takefocus=0, font=("Segoe UI", 12))
        close_btn.pack(side="right", fill="y")
        body = tk.Frame(self.detail_card, bg=PANEL)
        body.pack(fill="both", expand=True, padx=20, pady=18)
        self.detail_icon_label = tk.Label(body, bg=PANEL)
        self.detail_icon_label.grid(row=0, column=0, rowspan=2, sticky="nw", padx=(0, 18))
        self.detail_name_var = tk.StringVar()
        tk.Label(body, textvariable=self.detail_name_var, fg=TEXT, bg=PANEL, font=("Segoe UI Black", 24)).grid(row=0, column=1, sticky="w")
        self.detail_meta_var = tk.StringVar()
        tk.Label(body, textvariable=self.detail_meta_var, fg=GOLD, bg=PANEL, font=("Consolas", 10, "bold")).grid(row=1, column=1, sticky="w", pady=(2, 10))
        self.detail_body = tk.Text(body, height=9, bg="#0d1320", fg=TEXT, insertbackground=TEXT, relief="flat", wrap="word", font=("Segoe UI", 10))
        self.detail_body.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(8, 14))
        self.detail_body.configure(state="disabled")
        self.detail_progress = tk.Canvas(body, height=28, bg=PANEL, highlightthickness=0)
        self.detail_progress.grid(row=3, column=0, columnspan=2, sticky="ew")
        self.detail_close_button = self.ghost_button(body, "Close", self.hide_detail_overlay)
        self.detail_close_button.grid(row=4, column=1, sticky="e", pady=(16, 0))
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(2, weight=1)

    def hide_detail_overlay(self) -> None:
        if hasattr(self, "detail_overlay"):
            self.detail_overlay.place_forget()

    def append_status_log(self, message: str, kind: str = "info") -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self.status_events.append(f"[{stamp}] {kind.upper():7} {message}")
        self.status_events = self.status_events[-4:]
        if not hasattr(self, "status_log"):
            return
        self.status_log.configure(state="normal")
        self.status_log.delete("1.0", "end")
        self.status_log.insert("end", "\n".join(self.status_events))
        self.status_log.configure(state="disabled")

    def set_status(self, message: str, kind: str = "info", timeout_ms: int | None = None) -> None:
        colors = {"info": CYAN, "success": GREEN, "error": ORANGE}
        color = colors.get(kind, CYAN)
        self.status_var.set(message)
        self.append_status_log(message, kind)
        if hasattr(self, "status_dot"):
            self.status_dot.configure(fg=color)
            self.status_label.configure(fg=TEXT if kind in {"success", "error"} else MUTED)
        if self.status_reset_job:
            try:
                self.after_cancel(self.status_reset_job)
            except tk.TclError:
                pass
            self.status_reset_job = None
        if timeout_ms:
            self.status_reset_job = self.after(timeout_ms, lambda: self.set_status("Ready.", "info"))

    def notify(self, message: str, kind: str = "info", title: str | None = None, timeout_ms: int = 3600) -> None:
        colors = {"info": CYAN, "success": GREEN, "error": ORANGE}
        color = colors.get(kind, CYAN)
        title = title or {"info": "Notice", "success": "Complete", "error": "Needs attention"}.get(kind, "Notice")
        self.toast_messages.append({"message": message, "kind": kind, "title": title})
        self.toast_messages = self.toast_messages[-30:]
        self.set_status(message, kind, timeout_ms)
        if not hasattr(self, "toast_host"):
            return
        self.show_toast_host()
        toast = tk.Frame(self.toast_host, bg="#0d1320", highlightthickness=1, highlightbackground=color)
        self.active_toasts.append(toast)
        toast.pack(anchor="e", fill="x", pady=(0, 8))
        toast.configure(width=340)
        top = tk.Frame(toast, bg="#0d1320")
        top.pack(fill="x", padx=12, pady=(10, 2))
        tk.Label(top, text=title, fg=color, bg="#0d1320", font=("Segoe UI Semibold", 10)).pack(side="left")
        tk.Button(top, text="x", command=lambda item=toast: self.dismiss_toast(item), bg="#0d1320", fg=MUTED, activebackground=PANEL_2, activeforeground=TEXT, relief="flat", width=2, cursor="hand2").pack(side="right")
        tk.Label(toast, text=message, fg=TEXT, bg="#0d1320", font=("Segoe UI", 9), wraplength=300, justify="left").pack(anchor="w", padx=12, pady=(0, 12))
        job = self.after(timeout_ms, lambda item=toast: self.dismiss_toast(item))
        self._toast_jobs.append(job)

    def confirm_action(self, title: str, message: str, on_confirm, accent: str = ORANGE) -> None:
        modal = self.create_modal(title, 560, 300)
        card = tk.Frame(modal.content, bg=PANEL, highlightthickness=1, highlightbackground=accent)
        card.pack(fill="both", expand=True, padx=16, pady=16)
        tk.Label(card, text=title, fg=TEXT, bg=PANEL, font=("Segoe UI Black", 20)).pack(anchor="w", padx=20, pady=(18, 8))
        tk.Label(card, text=message, fg=MUTED, bg=PANEL, font=("Segoe UI", 10), wraplength=486, justify="left").pack(anchor="w", padx=20, pady=(0, 20))
        buttons = tk.Frame(card, bg=PANEL)
        buttons.pack(fill="x", padx=20, pady=(0, 18))
        self.ghost_button(buttons, "Cancel", lambda: (modal.destroy(), self.notify("Action cancelled.", "info"))).pack(side="right")
        self.action_button(buttons, "Confirm", lambda: (modal.destroy(), on_confirm()), accent).pack(side="right", padx=(0, 10))


    def bind_button_feedback(self, button: tk.Button, normal_bg: str, hover_bg: str, press_bg: str | None = None) -> tk.Button:
        press_bg = press_bg or hover_bg
        button.bind("<Enter>", lambda _event: button.configure(bg=hover_bg))
        button.bind("<Leave>", lambda _event: button.configure(bg=normal_bg))
        button.bind("<ButtonPress-1>", lambda _event: button.configure(bg=press_bg))
        button.bind("<ButtonRelease-1>", lambda _event: button.configure(bg=hover_bg))
        return button

    def action_button(self, master, text: str, command, color: str = CYAN) -> tk.Button:
        button = tk.Button(master, text=text, command=command, bg=color, fg="#071016", activebackground=color, activeforeground="#071016", relief="flat", font=("Segoe UI Semibold", 10), padx=14, pady=8, cursor="hand2")
        return self.bind_button_feedback(button, color, "#f8fafc", "#dbeafe")

    def ghost_button(self, master, text: str, command) -> tk.Button:
        button = tk.Button(master, text=text, command=command, bg=PANEL_2, fg=TEXT, activebackground=PANEL_3, activeforeground=TEXT, relief="flat", font=("Segoe UI Semibold", 10), padx=14, pady=8, cursor="hand2")
        return self.bind_button_feedback(button, PANEL_2, PANEL_3, "#26344f")

    def show_view(self, name: str) -> None:
        for view in self.views.values():
            view.pack_forget()
        for key, btn in self.nav_buttons.items():
            btn.configure(bg="#111827" if key == name else "#070a10", fg=TEXT if key == name else MUTED)
        self.views[name].pack(fill="both", expand=True)
        self.set_status(f"Viewing {self.nav_buttons[name].cget('text')}.", "info", 1600)
        if name == "achievements":
            self.render_achievements()

    def _build_overview(self) -> None:
        root = self.views["overview"]
        self.metric_frame = tk.Frame(root, bg=BG)
        self.metric_frame.pack(fill="x")
        self.metric_labels = {}
        for key, title, accent in [
            ("skills", "Skills", CYAN),
            ("valid_skills", "Valid Skills", GREEN),
            ("memories", "Memories", GOLD),
            ("packs", "Share Codes", PURPLE),
            ("achievements", "Achievements", ORANGE),
        ]:
            card = VaultCard(self.metric_frame, accent=accent)
            card.pack(side="left", fill="x", expand=True, padx=(0, 12))
            tk.Label(card, text=title, fg=MUTED, bg=PANEL, font=("Segoe UI", 9)).pack(anchor="w", padx=16, pady=(14, 0))
            value = tk.Label(card, text="--", fg=TEXT, bg=PANEL, font=("Segoe UI Black", 26))
            value.pack(anchor="w", padx=16, pady=(0, 12))
            self.metric_labels[key] = value
        row = tk.Frame(root, bg=BG)
        row.pack(fill="both", expand=True, pady=(16, 0))
        status = VaultCard(row, "System Status", CYAN)
        status.pack(side="left", fill="both", expand=True, padx=(0, 12))
        self.status_text = tk.Text(status, height=18, bg=PANEL, fg=TEXT, insertbackground=TEXT, relief="flat", wrap="word", font=("Consolas", 10))
        self.status_text.pack(fill="both", expand=True, padx=16, pady=12)
        quick = VaultCard(row, "Quick Actions", TEAL, width=340)
        quick.pack(side="left", fill="y")
        quick.pack_propagate(False)
        self.action_button(quick, "Create Backup", self.create_backup_action, TEAL).pack(fill="x", padx=16, pady=(16, 8))
        self.action_button(quick, "Export Pack", self.export_action, CYAN).pack(fill="x", padx=16, pady=8)
        self.action_button(quick, "Create Share Code", self.create_share_code_action, PURPLE).pack(fill="x", padx=16, pady=8)
        self.ghost_button(quick, "Import Pack", self.import_action).pack(fill="x", padx=16, pady=8)
        self.ghost_button(quick, "Import Share Code", self.import_share_code_action).pack(fill="x", padx=16, pady=8)
        self.ghost_button(quick, "Achievement Pop", self.demo_achievement).pack(fill="x", padx=16, pady=8)

    def _build_skills(self) -> None:
        root = self.views["skills"]
        top = VaultCard(root, "Skill Health", CYAN)
        top.pack(fill="x")
        self.skill_summary = tk.Label(top, text="--", fg=TEXT, bg=PANEL, font=("Segoe UI Semibold", 14))
        self.skill_summary.pack(anchor="w", padx=16, pady=(8, 14))
        body = tk.Frame(root, bg=BG)
        body.pack(fill="both", expand=True, pady=(14, 0))
        left = VaultCard(body, "Skill Index", CYAN)
        left.pack(side="left", fill="both", expand=True, padx=(0, 12))
        self.skill_tree = ttk.Treeview(left, columns=("valid", "size"), show="tree headings")
        self.skill_tree.heading("#0", text="Skill")
        self.skill_tree.heading("valid", text="Valid")
        self.skill_tree.heading("size", text="SKILL.md")
        self.skill_tree.column("#0", width=260)
        self.skill_tree.column("valid", width=100)
        self.skill_tree.column("size", width=110)
        self.skill_tree.pack(fill="both", expand=True, padx=12, pady=12)
        self.skill_tree.bind("<<TreeviewSelect>>", self.preview_skill)
        right = VaultCard(body, "SKILL.md Preview", TEAL)
        right.pack(side="left", fill="both", expand=True)
        self.skill_preview = tk.Text(right, bg="#0a0f1c", fg=TEXT, insertbackground=TEXT, relief="flat", wrap="word", font=("Consolas", 10))
        self.skill_preview.pack(fill="both", expand=True, padx=12, pady=12)

    def _build_memory(self) -> None:
        root = self.views["memory"]
        body = tk.Frame(root, bg=BG)
        body.pack(fill="both", expand=True)
        left = VaultCard(body, "Memory Files", GOLD, width=360)
        left.pack(side="left", fill="y", padx=(0, 12))
        left.pack_propagate(False)
        self.memory_list = tk.Listbox(left, bg="#0d1320", fg=TEXT, selectbackground="#3b2f17", selectforeground=TEXT, relief="flat", font=("Segoe UI", 10))
        self.memory_list.pack(fill="both", expand=True, padx=12, pady=12)
        self.memory_list.bind("<<ListboxSelect>>", self.preview_memory)
        right = VaultCard(body, "Memory Editor", GOLD)
        right.pack(side="left", fill="both", expand=True)
        toolbar = tk.Frame(right, bg=PANEL)
        toolbar.pack(fill="x", padx=12, pady=(8, 0))
        self.memory_path_label = tk.Label(toolbar, text="Select a memory file · read-only in this build", fg=MUTED, bg=PANEL, font=("Consolas", 9))
        self.memory_path_label.pack(side="left")
        tk.Label(toolbar, text="READ ONLY", fg=GOLD, bg=PANEL, font=("Consolas", 9, "bold")).pack(side="right")
        self.memory_editor = tk.Text(right, bg="#0a0f1c", fg=TEXT, insertbackground=TEXT, relief="flat", wrap="word", font=("Consolas", 10))
        self.memory_editor.pack(fill="both", expand=True, padx=12, pady=12)

    def _build_sync(self) -> None:
        root = self.views["sync"]
        row = tk.Frame(root, bg=BG)
        row.pack(fill="both", expand=True)
        left = VaultCard(row, "Local Packs", PURPLE)
        left.pack(side="left", fill="both", expand=True, padx=(0, 12))
        self.sync_text = tk.Text(left, bg=PANEL, fg=TEXT, insertbackground=TEXT, relief="flat", wrap="word", font=("Consolas", 10))
        self.sync_text.pack(fill="both", expand=True, padx=12, pady=12)
        right = VaultCard(row, "Share Code Lab", PURPLE, width=390)
        right.pack(side="left", fill="y")
        right.pack_propagate(False)
        tk.Label(right, text="Phase 2 local simulation:\nshare codes map to packs in data/share_codes.", fg=MUTED, bg=PANEL, justify="left", font=("Segoe UI", 10)).pack(anchor="w", padx=16, pady=16)
        self.share_code_var = tk.StringVar()
        tk.Entry(right, textvariable=self.share_code_var, bg="#0d1320", fg=TEXT, insertbackground=TEXT, relief="flat", font=("Consolas", 14), justify="center").pack(fill="x", padx=16, ipady=10, pady=(0, 12))
        self.action_button(right, "Create Code From Latest Export", self.create_share_code_action, PURPLE).pack(fill="x", padx=16, pady=8)
        self.ghost_button(right, "Import This Code", self.import_share_code_action).pack(fill="x", padx=16, pady=8)
        self.ghost_button(right, "Refresh Registry", self.update_sync_view).pack(fill="x", padx=16, pady=8)
        rollback = VaultCard(right, "Recovery / Rollback", ORANGE)
        rollback.pack(fill="both", expand=True, padx=16, pady=(16, 16))
        tk.Label(rollback, text="Restore from the latest safe backup point.", fg=MUTED, bg=PANEL, justify="left", font=("Segoe UI", 9)).pack(anchor="w", padx=12, pady=(8, 6))
        self.backup_list = tk.Listbox(rollback, height=5, bg="#0d1320", fg=TEXT, selectbackground="#4a2a15", selectforeground=TEXT, relief="flat", font=("Consolas", 9))
        self.backup_list.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        self.ghost_button(rollback, "Refresh Backups", self.update_backup_list).pack(fill="x", padx=12, pady=(0, 6))
        self.action_button(rollback, "Rollback Selected", self.rollback_selected_backup, ORANGE).pack(fill="x", padx=12, pady=(0, 12))

    def _build_achievements(self) -> None:
        root = self.views["achievements"]
        hero = VaultCard(root, "Achievement Wall", GOLD)
        hero.pack(fill="x", pady=(0, 14))
        tk.Label(hero, text="One row per achievement. Descriptions, requirements, progress, and manual activation are visible inline.", fg=MUTED, bg=PANEL, font=("Segoe UI", 10)).pack(anchor="w", padx=16, pady=(4, 8))
        filters = tk.Frame(hero, bg=PANEL)
        filters.pack(fill="x", padx=16, pady=(0, 10))
        self.achievement_filter_var = tk.StringVar(value="全部")
        self.achievement_filter_buttons: dict[str, tk.Button] = {}
        for label in ["全部", "已达成", "未达成", "普通", "稀有", "史诗", "传说"]:
            button = tk.Button(
                filters,
                text=label,
                command=lambda value=label: self.set_achievement_filter(value),
                bg="#0d1320",
                fg=MUTED,
                activebackground=PANEL_3,
                activeforeground=TEXT,
                relief="flat",
                font=("Segoe UI Semibold", 9),
                padx=12,
                pady=5,
                cursor="hand2",
            )
            button.pack(side="left", padx=(0, 8))
            self.achievement_filter_buttons[label] = button
        for label in ["Activated", "Not activated"]:
            button = tk.Button(
                filters,
                text=label,
                command=lambda value=label: self.set_achievement_filter(value),
                bg="#0d1320",
                fg=MUTED,
                activebackground=PANEL_3,
                activeforeground=TEXT,
                relief="flat",
                font=("Segoe UI Semibold", 9),
                padx=12,
                pady=5,
                cursor="hand2",
            )
            button.pack(side="left", padx=(0, 8))
            self.achievement_filter_buttons[label] = button
        self.achievement_history_label = tk.Label(hero, text="Recent unlocks: none yet", fg=GOLD, bg="#0d1320", font=("Consolas", 9), anchor="w", padx=10, pady=6)
        self.achievement_history_label.pack(fill="x", padx=16, pady=(0, 14))
        canvas_shell = tk.Frame(root, bg=BG)
        canvas_shell.pack(fill="both", expand=True)
        self.achievement_canvas = tk.Canvas(canvas_shell, bg=BG, highlightthickness=0)
        self.achievement_canvas.pack(side="left", fill="both", expand=True)
        self.achievement_scrollbar = ttk.Scrollbar(canvas_shell, orient="vertical", command=self.achievement_canvas.yview, style="Vault.Vertical.TScrollbar")
        self.achievement_scrollbar.pack(side="right", fill="y")
        self.achievement_canvas.configure(yscrollcommand=self.achievement_scrollbar.set)
        self.achievement_canvas.bind("<Button-1>", self.on_achievement_canvas_click)
        self.achievement_canvas.bind("<Motion>", self.on_achievement_canvas_motion)
        self.achievement_canvas.bind("<MouseWheel>", self.on_achievement_mousewheel)
        self.achievement_canvas.bind("<Configure>", self.on_achievement_canvas_configure)

    def _build_account(self) -> None:
        root = self.views["account"]
        row = tk.Frame(root, bg=BG)
        row.pack(fill="both", expand=True)
        left = VaultCard(row, "Local Account", TEAL, width=420)
        left.pack(side="left", fill="y", padx=(0, 12))
        left.pack_propagate(False)
        self.username_var = tk.StringVar(value="local-user")
        self.password_var = tk.StringVar(value="codex-vault-local")
        for label, var, show in [("Username", self.username_var, ""), ("Password", self.password_var, "*")]:
            tk.Label(left, text=label, fg=MUTED, bg=PANEL, font=("Segoe UI", 9)).pack(anchor="w", padx=16, pady=(14, 2))
            tk.Entry(left, textvariable=var, show=show, bg="#0d1320", fg=TEXT, insertbackground=TEXT, relief="flat", font=("Segoe UI", 11)).pack(fill="x", padx=16, ipady=8)
        self.action_button(left, "Register", self.register_action, TEAL).pack(fill="x", padx=16, pady=(18, 8))
        self.action_button(left, "Login + Bind Device", self.login_action, CYAN).pack(fill="x", padx=16, pady=8)
        right = VaultCard(row, "Device State", TEAL)
        right.pack(side="left", fill="both", expand=True)
        self.account_text = tk.Text(right, bg=PANEL, fg=TEXT, insertbackground=TEXT, relief="flat", wrap="word", font=("Consolas", 10))
        self.account_text.pack(fill="both", expand=True, padx=12, pady=12)

    def choose_path(self) -> None:
        path = filedialog.askdirectory(title="Choose .codex directory", initialdir=str(self.codex_path.parent if self.codex_path.exists() else Path.home()))
        if path:
            self.codex_path = Path(path)
            self.path_var.set(str(self.codex_path))
            self.set_status(f"Selected vault path: {self.codex_path}", "info")
            self.refresh_in_background()

    def collect_vault_state(self, root: Path):
        return scan_codex(root), list_skills(root), list_memories(root)

    def refresh_all(self) -> None:
        self.codex_path = Path(self.path_var.get()).expanduser()
        self.set_status(f"Scanning {self.codex_path} ...", "info")
        self.update_idletasks()
        try:
            scan, skills, memories = self.collect_vault_state(self.codex_path)
        except Exception as exc:
            self.status_text.delete("1.0", "end")
            self.status_text.insert("end", f"Scan failed: {exc}")
            self.set_status(f"Scan failed: {exc}", "error")
            return
        self.apply_vault_state(scan, skills, memories)

    def refresh_in_background(self) -> None:
        root = Path(self.path_var.get()).expanduser()
        self.codex_path = root
        if self._scan_in_progress:
            self._pending_scan_root = root
            self.set_status(f"Scan already running. Queued {root}.", "info", 2400)
            return
        self._start_background_scan(root)

    def _start_background_scan(self, root: Path) -> None:
        self._scan_in_progress = True
        self._scan_token += 1
        token = self._scan_token
        self.set_status(f"Scanning {root} in the background ...", "info")
        self.status_text.delete("1.0", "end")
        self.status_text.insert("end", f"Scanning {root}\n\nThe window stays responsive while Codex Vault reads your local files.")
        if self._scan_poll_job is None:
            self._scan_poll_job = self.after(50, self._poll_scan_results)
        thread = threading.Thread(target=self._scan_worker, args=(token, root), daemon=True)
        thread.start()

    def _scan_worker(self, token: int, root: Path) -> None:
        try:
            result = (*self.collect_vault_state(root), None)
        except Exception as exc:
            result = (None, None, None, exc)
        self._scan_results.put((token, root, result))

    def _poll_scan_results(self) -> None:
        self._scan_poll_job = None
        while True:
            try:
                token, root, result = self._scan_results.get_nowait()
            except queue.Empty:
                break
            self._finish_background_scan(token, root, result)
        if self._scan_in_progress and self._scan_poll_job is None:
            self._scan_poll_job = self.after(50, self._poll_scan_results)

    def run_background_task(self, label: str, worker, on_success, on_error=None) -> None:
        if self._task_in_progress:
            self.notify(f"Another task is already running. Try again after it finishes: {label}.", "info", "Task queued")
            return
        self._task_in_progress = True
        self._task_token += 1
        token = self._task_token
        self._task_callbacks[token] = (on_success, on_error)
        self.set_status(f"{label} in the background ...", "info")
        if self._task_poll_job is None:
            self._task_poll_job = self.after(50, self._poll_task_results)
        thread = threading.Thread(target=self._task_worker, args=(token, worker), daemon=True)
        thread.start()

    def _task_worker(self, token: int, worker) -> None:
        try:
            result = worker()
            self._task_results.put((token, result, None))
        except Exception as exc:
            self._task_results.put((token, None, exc))

    def _poll_task_results(self) -> None:
        self._task_poll_job = None
        while True:
            try:
                token, result, error = self._task_results.get_nowait()
            except queue.Empty:
                break
            on_success, on_error = self._task_callbacks.pop(token, (None, None))
            self._task_in_progress = False
            if error:
                if on_error:
                    on_error(error)
                else:
                    self.notify(f"Task failed: {error}", "error", "Task failed")
            elif on_success:
                on_success(result)
        if self._task_in_progress and self._task_poll_job is None:
            self._task_poll_job = self.after(50, self._poll_task_results)

    def _finish_background_scan(self, token: int, root: Path, result: tuple) -> None:
        if token != self._scan_token:
            return
        self._scan_in_progress = False
        scan, skills, memories, error = result
        if error:
            self.status_text.delete("1.0", "end")
            self.status_text.insert("end", f"Scan failed: {error}")
            self.notify(f"Scan failed: {error}", "error", "Scan failed")
        else:
            self.codex_path = root
            self.apply_vault_state(scan, skills, memories)
        if self._pending_scan_root is not None:
            pending = self._pending_scan_root
            self._pending_scan_root = None
            self.after(60, lambda: self._start_background_scan(pending))

    def apply_vault_state(self, scan, skills, memories) -> None:
        self.scan = scan
        self.skills = skills
        self.memories = memories
        self.update_overview()
        self.update_skills()
        self.update_memories()
        self.update_sync_view()
        self.render_achievements()
        self.evaluate_achievements({
            "event": "scan.completed",
            "counts": self.scan.counts,
            "total_files": self.scan.total_files,
            "total_size": self.scan.total_size,
            "sensitive_blocks": len(self.scan.sensitive_items),
            "backups": self.metrics.get("backups", 0),
            "exports": self.metrics.get("exports", 0),
            "imports": self.metrics.get("imports", 0),
        })
        self.set_status(f"Scan complete: {self.scan.total_files} files, {len(self.skills)} skills, {len(self.memories)} memories.", "success", 3500)

    def update_overview(self) -> None:
        valid = len([skill for skill in self.skills if skill.valid])
        codes = len(self.share_store.all_codes())
        values = {
            "skills": str(len(self.skills)),
            "valid_skills": f"{valid}/{len(self.skills)}",
            "memories": str(len(self.memories)),
            "packs": str(codes),
            "achievements": f"{len(self.engine.unlocked_ids)}/25",
        }
        for key, value in values.items():
            self.metric_labels[key].configure(text=value)
        lines = [
            "SYSTEM ONLINE",
            f"Root: {self.scan.root}",
            f"Files scanned: {self.scan.total_files}",
            f"Total size: {human_size(self.scan.total_size)}",
            f"Skills: {len(self.skills)} ({valid} valid, {len(self.skills) - valid} invalid)",
            f"Memory files: {len(self.memories)}",
            f"Sensitive excluded: {len(self.scan.sensitive_items)}",
            f"Runtime/volatile excluded: {len(self.scan.volatile_items)}",
            "",
            "MVP acceptance:",
            "- Phase 1 local scan / backup / export / import is available.",
            "- Phase 2 account / device / share code is local-simulated.",
            "- No cloud upload, no network, no admin permission.",
        ]
        self.status_text.delete("1.0", "end")
        self.status_text.insert("end", "\n".join(lines))

    def update_skills(self) -> None:
        self.skill_tree.delete(*self.skill_tree.get_children())
        valid = len([skill for skill in self.skills if skill.valid])
        self.skill_summary.configure(text=f"{len(self.skills)} skills detected · {valid} valid · {len(self.skills) - valid} need attention")
        for skill in self.skills:
            self.skill_tree.insert("", "end", iid=skill.path, text=skill.name, values=("OK" if skill.valid else "Missing", human_size(skill.size)))

    def preview_skill(self, _event=None) -> None:
        selection = self.skill_tree.selection()
        if not selection:
            return
        path = selection[0]
        skill = next((item for item in self.skills if item.path == path), None)
        self.skill_preview.delete("1.0", "end")
        if skill:
            self.skill_preview.insert("end", skill.preview)

    def update_memories(self) -> None:
        self.memory_list.delete(0, "end")
        for memory in self.memories:
            self.memory_list.insert("end", memory.path)

    def preview_memory(self, _event=None) -> None:
        selection = self.memory_list.curselection()
        if not selection:
            return
        memory = self.memories[selection[0]]
        self.current_memory_path = memory.path
        self.memory_path_label.configure(text=memory.path)
        self.memory_editor.configure(state="normal")
        self.memory_editor.delete("1.0", "end")
        self.memory_editor.insert("end", memory.content)
        self.memory_editor.configure(state="disabled")

    def update_sync_view(self) -> None:
        codes = self.share_store.all_codes()
        lines = ["LOCAL SHARE REGISTRY", ""]
        if not codes:
            lines.append("No share codes yet. Export a pack, then create a code.")
        for code, record in codes.items():
            lines.append(f"{code}  owner={record.get('owner')}  pack={Path(record.get('packPath', '')).name}")
        self.sync_text.delete("1.0", "end")
        self.sync_text.insert("end", "\n".join(lines))
        if hasattr(self, "backup_list"):
            self.update_backup_list()

    def update_backup_list(self) -> None:
        if not hasattr(self, "backup_list"):
            return
        self.backup_list.delete(0, "end")
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        backups = sorted([path for path in BACKUP_DIR.iterdir() if path.is_dir()], key=lambda p: p.stat().st_mtime, reverse=True)
        for backup in backups[:20]:
            self.backup_list.insert("end", backup.name)

    def selected_backup_path(self) -> Path | None:
        selection = self.backup_list.curselection() if hasattr(self, "backup_list") else ()
        if not selection:
            return None
        return BACKUP_DIR / self.backup_list.get(selection[0])

    def create_backup_action(self) -> None:
        def done(path: Path) -> None:
            self.bump_metric("backups")
            self.update_backup_list()
            self.notify(f"Backup created: {path.name}", "success", "Backup ready")

        self.run_background_task(
            "Creating local backup",
            lambda: create_backup(self.codex_path, BACKUP_DIR, reason="manual"),
            done,
            lambda exc: self.notify(f"Backup failed: {exc}", "error", "Backup failed"),
        )

    def export_action(self) -> Path | None:
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        default_name = f"codex-vault-{datetime.now().strftime('%Y%m%d-%H%M%S')}.codexvault.zip"
        output = filedialog.asksaveasfilename(title="Export Codex Vault Pack", initialdir=str(EXPORT_DIR), initialfile=default_name, defaultextension=".zip", filetypes=[("Codex Vault Pack", "*.zip"), ("All files", "*.*")])
        if not output:
            self.set_status("Export cancelled.", "info", 2500)
            return None
        output_path = Path(output)

        def done(path: Path) -> None:
            self.bump_metric("exports")
            self.notify(f"Pack exported: {path.name}", "success", "Export complete")

        self.run_background_task(
            "Exporting safe pack",
            lambda: (export_pack(self.codex_path, output_path, author=self.current_user or getpass.getuser(), name="Codex Vault Local Pack"), output_path)[1],
            done,
            lambda exc: self.notify(f"Export failed: {exc}", "error", "Export failed"),
        )
        return output_path

    def latest_export(self) -> Path | None:
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        packs = sorted(EXPORT_DIR.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
        if packs:
            return packs[0]
        pack = EXPORT_DIR / f"codex-vault-{datetime.now().strftime('%Y%m%d-%H%M%S')}.codexvault.zip"
        export_pack(self.codex_path, pack, author=self.current_user or getpass.getuser(), name="Codex Vault Local Pack")
        self.bump_metric("exports")
        return pack

    def import_action(self) -> None:
        pack_path = filedialog.askopenfilename(title="Import Codex Vault Pack", initialdir=str(EXPORT_DIR), filetypes=[("Codex Vault Pack", "*.zip"), ("All files", "*.*")])
        if not pack_path:
            self.set_status("Import cancelled.", "info", 2500)
            return
        self.set_status("Building import preview ...", "info")
        self.update_idletasks()
        try:
            preview = preview_import_pack(pack_path, self.codex_path)
        except Exception as exc:
            self.notify(f"Import preview failed: {exc}", "error", "Preview failed")
            return
        self.set_status("Import preview ready. Confirm in the modal to write files.", "success", 4500)
        self.show_import_preview_dialog(preview, lambda: self.perform_import_pack(Path(pack_path), "before-import"))

    def perform_import_pack(self, pack_path: Path, backup_reason: str) -> None:
        def work() -> dict:
            backup = create_backup(self.codex_path, BACKUP_DIR, reason=backup_reason)
            result = import_pack(pack_path, self.codex_path, history_path=IMPORT_HISTORY_FILE, backup_path=backup)
            result["backup"] = str(backup)
            return result

        def done(result: dict) -> None:
            self.bump_metric("imports")
            self.bump_metric("safe_imports")
            self.refresh_in_background()
            self.notify(
                f"Imported {result['imported']} files, skipped {result['skipped']}. Backup: {Path(result.get('backup', '')).name}",
                "success",
                "Import complete",
            )
            self.show_post_import_summary(result)

        self.run_background_task(
            "Creating backup and importing pack",
            work,
            done,
            lambda exc: self.notify(f"Import failed: {exc}", "error", "Import failed"),
        )

    def create_share_code_action(self) -> None:
        self.set_status("Creating local share code ...", "info")
        self.update_idletasks()
        try:
            pack = self.latest_export()
            if not pack:
                self.set_status("Share-code creation cancelled.", "info", 2500)
                return
            code = self.share_store.create_code(pack, owner=self.current_user or "local")
            self.share_code_var.set(code)
            self.bump_metric("share_codes")
            self.update_sync_view()
        except Exception as exc:
            self.notify(f"Share code failed: {exc}", "error", "Share failed")
            return
        self.notify(f"Share code created: {code}", "success", "Share code ready")

    def import_share_code_action(self) -> None:
        code = self.share_code_var.get().strip().upper()
        if not code:
            self.notify("Enter a share code before importing.", "error", "Missing code")
            return
        self.set_status(f"Resolving share code {code} ...", "info")
        self.update_idletasks()
        try:
            record = self.share_store.resolve(code)
            pack_path = Path(record["packPath"])
            preview = preview_import_pack(pack_path, self.codex_path)
        except Exception as exc:
            self.notify(f"Share import preview failed: {exc}", "error", "Preview failed")
            return
        self.set_status(f"Share code {code} preview ready.", "success", 4500)
        self.show_import_preview_dialog(preview, lambda: self.perform_import_pack(pack_path, "before-share-code-import"))

    def format_import_preview(self, preview: dict) -> str:
        manifest = preview.get("manifest", {})
        lines = [
            f"Pack: {manifest.get('name', 'Codex Vault Pack')}",
            f"Author: {manifest.get('author', 'unknown')}",
            f"Schema: {manifest.get('schemaVersion', 'unknown')}",
            f"Payload: {human_size(int(preview.get('totalSize', 0)))}",
            "",
            f"Add: {len(preview.get('added', []))} files",
            f"Replace: {len(preview.get('replaced', []))} files",
            f"Skip: {len(preview.get('skipped', []))} files",
            f"Warnings: {len(preview.get('warnings', []))}",
            "",
            "Preview:",
        ]
        for item in preview.get("files", [])[:12]:
            action = str(item.get("defaultAction", "skip")).upper()
            status = str(item.get("status", "unknown")).upper()
            lines.append(f"{action:<7} {status:<8} {item.get('path')}")
            for warning in item.get("warnings", []):
                lines.append(f"  ! {warning.get('message')}")
            diff = item.get("markdownDiff")
            if diff:
                lines.append("  markdown diff:")
                lines.extend(f"  {line}" for line in str(diff).splitlines()[:12])
        for item in preview.get("skipped", [])[:8]:
            lines.append(f"- SKIP    {item.get('path')} ({item.get('reason')})")
        if len(preview.get("files", [])) + len(preview.get("skipped", [])) > 20:
            lines.append("... more files hidden in preview")
        return "\n".join(lines)

    def show_import_preview_dialog(self, preview: dict, confirm_callback) -> None:
        modal = self.create_modal("Import Preview", 660, 520)
        shell = tk.Frame(modal.content, bg=PANEL, highlightthickness=1, highlightbackground="#334155")
        shell.pack(fill="both", expand=True, padx=16, pady=16)
        tk.Label(shell, text="Review before writing", fg=TEXT, bg=PANEL, font=("Segoe UI Black", 22)).pack(anchor="w", padx=18, pady=(16, 2))
        tk.Label(shell, text="A backup point will be created before import. Cancel leaves your files unchanged.", fg=MUTED, bg=PANEL, font=("Segoe UI", 10)).pack(anchor="w", padx=18, pady=(0, 12))
        body = tk.Text(shell, height=16, bg="#0a0f1c", fg=TEXT, insertbackground=TEXT, relief="flat", wrap="none", font=("Consolas", 10))
        body.pack(fill="both", expand=True, padx=18, pady=(0, 14))
        body.insert("end", self.format_import_preview(preview))
        body.configure(state="disabled")
        buttons = tk.Frame(shell, bg=PANEL)
        buttons.pack(fill="x", padx=18, pady=(0, 16))
        self.ghost_button(buttons, "Cancel", modal.destroy).pack(side="right")
        self.action_button(buttons, "Create Backup + Import", lambda: (modal.destroy(), confirm_callback()), TEAL).pack(side="right", padx=(0, 10))

    def show_post_import_summary(self, result: dict) -> None:
        modal = self.create_modal("Import Summary", 560, 420)
        shell = tk.Frame(modal.content, bg=PANEL, highlightthickness=1, highlightbackground="#334155")
        shell.pack(fill="both", expand=True, padx=16, pady=16)
        tk.Label(shell, text="Import complete", fg=TEXT, bg=PANEL, font=("Segoe UI Black", 20)).pack(anchor="w", padx=18, pady=(16, 4))
        lines = [
            f"Imported: {result.get('imported', 0)}",
            f"Added: {result.get('added', 0)}",
            f"Replaced: {result.get('replaced', 0)}",
            f"Renamed: {result.get('renamed', 0)}",
            f"Skipped: {result.get('skipped', 0)}",
            f"Backup: {Path(result.get('backup', '')).name}",
            "",
            "Affected files:",
        ]
        lines.extend(f"- {path}" for path in result.get("affected", [])[:20])
        body = tk.Text(shell, height=14, bg="#0a0f1c", fg=TEXT, insertbackground=TEXT, relief="flat", wrap="none", font=("Consolas", 10))
        body.pack(fill="both", expand=True, padx=18, pady=(0, 14))
        body.insert("end", "\n".join(lines))
        body.configure(state="disabled")
        self.action_button(shell, "Close", modal.destroy, TEAL).pack(anchor="e", padx=18, pady=(0, 16))

    def rollback_selected_backup(self) -> None:
        backup = self.selected_backup_path()
        if not backup:
            self.notify("Select a backup point before rollback.", "error", "No backup selected")
            return
        self.confirm_action(
            "Restore backup?",
            f"Restore files from backup {backup.name} into {self.codex_path}. Current files with matching paths will be replaced.",
            lambda: self.perform_rollback(backup),
            ORANGE,
        )

    def perform_rollback(self, backup: Path) -> None:
        def done(result: dict) -> None:
            self.bump_metric("restores")
            self.refresh_in_background()
            self.notify(f"Restored {result['restored']} files, skipped {result['skipped']}.", "success", "Rollback complete")

        self.run_background_task(
            f"Restoring backup {backup.name}",
            lambda: restore_backup(backup, self.codex_path),
            done,
            lambda exc: self.notify(f"Rollback failed: {exc}", "error", "Rollback failed"),
        )

    def register_action(self) -> None:
        self.set_status("Registering local account ...", "info")
        try:
            profile = self.auth.register(self.username_var.get(), self.password_var.get())
        except Exception as exc:
            self.notify(f"Register failed: {exc}", "error", "Register failed")
            return
        self.account_text.insert("end", f"Registered {profile['username']} at {profile['createdAt']}\n")
        self.notify(f"Registered local account: {profile['username']}", "success", "Account ready")

    def login_action(self) -> None:
        self.set_status("Logging in and binding this Windows device ...", "info")
        try:
            session = self.auth.login(self.username_var.get(), self.password_var.get())
            self.auth.register_device(session["sessionToken"], "Windows Dev Box")
        except Exception as exc:
            self.notify(f"Login failed: {exc}", "error", "Login failed")
            return
        self.current_user = session["username"]
        devices = self.auth.devices(self.current_user)
        self.account_text.delete("1.0", "end")
        self.account_text.insert("end", f"Logged in as {self.current_user}\nSession: {session['sessionToken'][:10]}...\n\nDevices:\n")
        for item in devices:
            self.account_text.insert("end", f"- {item['name']} ({item['platform']}) {item['lastSeenAt']}\n")
        self.notify(f"Logged in as {self.current_user}; device bound.", "success", "Device bound")

    def bump_metric(self, key: str, amount: int = 1) -> None:
        self.metrics[key] = int(self.metrics.get(key, 0)) + amount
        self.persist_state()

    def evaluate_achievements(self, event: dict) -> None:
        payload = dict(event)
        payload.update(self.metrics)
        payload["unlocked_count"] = len(self.engine.unlocked_ids)
        new_items = self.engine.evaluate(payload)
        if new_items:
            self.persist_state()
            for index, achievement in enumerate(new_items[:2]):
                self.after(250 + index * 850, lambda item=achievement: self.show_achievement_popup(item))
        self.render_achievements()
        if self.scan:
            self.update_overview()

    def persist_state(self) -> None:
        save_state(
            STATE_FILE,
            {
                "unlocked": sorted(self.engine.unlocked_ids),
                "metrics": self.metrics,
                "progress": self.progress_snapshot(),
                "notifications": self.notification_history[-20:],
                "activated": sorted(self.activated_achievement_ids),
                "achievementHistory": self.achievement_history_details,
            },
        )

    def progress_snapshot(self) -> dict[str, dict[str, int]]:
        snapshot = {}
        for achievement in default_achievements():
            snapshot[achievement.id] = {
                "value": self.achievement_current_value(achievement),
                "threshold": achievement.threshold,
            }
        return snapshot

    def set_achievement_filter(self, value: str) -> None:
        self.achievement_filter_var.set(value)
        for label, button in getattr(self, "achievement_filter_buttons", {}).items():
            active = label == value
            button.configure(bg=CYAN if active else "#0d1320", fg="#071016" if active else MUTED)
        self.render_achievements()
        self.set_status(f"Achievement filter: {value}.", "info", 1400)

    def is_achievement_unlocked(self, achievement) -> bool:
        return achievement.id in self.engine.unlocked_ids

    def filtered_achievements(self):
        selected = self.achievement_filter_var.get() if hasattr(self, "achievement_filter_var") else "全部"
        achievements = default_achievements()
        if selected == "全部":
            return achievements
        if selected == "已达成":
            return [item for item in achievements if self.is_achievement_unlocked(item)]
        if selected == "未达成":
            return [item for item in achievements if not self.is_achievement_unlocked(item)]
        if selected == "Activated":
            return [item for item in achievements if item.id in self.activated_achievement_ids]
        if selected == "Not activated":
            return [item for item in achievements if item.id not in self.activated_achievement_ids]
        return [item for item in achievements if item.rarity == selected]

    def on_achievement_canvas_configure(self, event) -> None:
        new_width = int(getattr(event, "width", 0) or 0)
        if abs(new_width - self._achievement_render_width) < 12:
            return
        self._achievement_render_width = new_width
        if self._achievement_resize_job:
            try:
                self.after_cancel(self._achievement_resize_job)
            except tk.TclError:
                pass
        self._achievement_resize_job = self.after_idle(self.render_achievements)

    def achievement_row_layout(self, canvas_width: int) -> dict[str, int]:
        width = max(canvas_width, 720)
        x = 18
        card_w = max(680, width - 44)
        button_w = max(124, min(168, int(card_w * 0.12)))
        button_right = x + card_w - 28
        button_left = button_right - button_w
        status_x = max(x + 430, button_left - 62)
        text_x = x + 92
        text_w = max(260, button_left - text_x - 38)
        progress_left = text_x
        progress_right = max(progress_left + 180, button_left - 34)
        card_h = 148 if card_w < 860 else 136
        return {
            "x": x,
            "card_w": card_w,
            "card_h": card_h,
            "gap": 14,
            "button_left": button_left,
            "button_right": button_right,
            "button_w": button_w,
            "status_x": status_x,
            "text_x": text_x,
            "text_w": text_w,
            "progress_left": progress_left,
            "progress_right": progress_right,
        }

    def render_achievements(self) -> None:
        if not hasattr(self, "achievement_canvas"):
            return
        canvas = self.achievement_canvas
        canvas.delete("all")
        self.achievement_rects = {}
        self.achievement_bounds = {}
        self.achievement_button_bounds = {}
        self.achievement_activate_bounds = {}
        self.achievement_progress_bounds = {}
        self.achievement_description_items = {}
        configured_width = int(float(canvas.cget("width") or 0))
        width = max(canvas.winfo_width(), configured_width, self._achievement_render_width, 720)
        layout = self.achievement_row_layout(width)
        x = layout["x"]
        card_w = layout["card_w"]
        card_h = layout["card_h"]
        gap = layout["gap"]
        all_achievements = default_achievements()
        visible = self.filtered_achievements()
        if not visible:
            canvas.create_text(24, 40, text="No achievements match this filter.", fill=MUTED, anchor="nw", font=("Segoe UI Semibold", 12))
            canvas.configure(scrollregion=(0, 0, width, 120))
            self.update_achievement_history()
            return
        for row, ach in enumerate(visible):
            idx = all_achievements.index(ach)
            y = 14 + row * (card_h + gap)
            unlocked = ach.id in self.engine.unlocked_ids
            activated = ach.id in self.activated_achievement_ids
            border = self.rarity_color(ach.rarity) if unlocked else "#293348"
            fill = "#142033" if activated else ("#101827" if unlocked else "#0d1320")
            rect = canvas.create_rectangle(x, y, x + card_w, y + card_h, fill=fill, outline=border, width=2, tags=(f"ach-{idx}", "achievement"))
            self.achievement_rects[idx] = rect
            self.achievement_bounds[idx] = (x, y, x + card_w, y + card_h)
            self.draw_achievement_icon(canvas, idx, x + 16, y + 22, unlocked, border)
            text_x = layout["text_x"]
            text_w = layout["text_w"]
            canvas.create_text(text_x, y + 18, text=ach.name, fill=TEXT if unlocked else MUTED, anchor="nw", font=("Segoe UI Semibold", 14), width=text_w, tags=(f"ach-{idx}",))
            desc = canvas.create_text(text_x, y + 48, text=ach.description, fill=TEXT if unlocked else MUTED, anchor="nw", font=("Segoe UI", 10), width=text_w, tags=(f"ach-{idx}",))
            self.achievement_description_items[idx] = desc
            current = self.achievement_current_value(ach)
            requirement = f"Requirement: {ach.metric} >= {ach.threshold}    Progress: {min(current, ach.threshold)} / {ach.threshold}"
            canvas.create_text(text_x, y + 78, text=requirement, fill=DIM, anchor="nw", font=("Consolas", 9), width=text_w, tags=(f"ach-{idx}",))
            canvas.create_text(layout["status_x"], y + 20, text=ach.rarity, fill=border, anchor="nw", font=("Consolas", 10, "bold"), tags=(f"ach-{idx}",))
            status = "已达成" if unlocked else "未达成"
            status_color = GREEN if unlocked else DIM
            canvas.create_text(layout["status_x"], y + 44, text=status, fill=status_color, anchor="nw", font=("Segoe UI Semibold", 10), tags=(f"ach-{idx}",))
            btn_x1, btn_y1 = layout["button_left"], y + card_h - 54
            btn_x2, btn_y2 = layout["button_right"], y + card_h - 20
            self.achievement_button_bounds[idx] = (btn_x1, btn_y1, btn_x2, btn_y2)
            if activated:
                btn_fill = GREEN
                btn_outline = border
                btn_text = "已激活"
                btn_text_color = "#071016"
            elif unlocked:
                btn_fill = "#0f2a37"
                btn_outline = CYAN
                btn_text = "激活"
                btn_text_color = TEXT
                self.achievement_activate_bounds[idx] = (btn_x1, btn_y1, btn_x2, btn_y2)
            else:
                btn_fill = "#111827"
                btn_outline = "#293348"
                btn_text = "待达成"
                btn_text_color = DIM
            canvas.create_rectangle(btn_x1, btn_y1, btn_x2, btn_y2, fill=btn_fill, outline=btn_outline, width=1, tags=(f"activate-{idx}", f"ach-{idx}"))
            canvas.create_text((btn_x1 + btn_x2) // 2, (btn_y1 + btn_y2) // 2, text=btn_text, fill=btn_text_color, anchor="center", font=("Segoe UI Semibold", 10), tags=(f"activate-{idx}", f"ach-{idx}"))
            progress_y1 = y + card_h - 34
            progress_y2 = progress_y1 + 6
            progress_x1 = layout["progress_left"]
            progress_x2 = layout["progress_right"]
            self.achievement_progress_bounds[idx] = (progress_x1, progress_y1, progress_x2, progress_y2)
            canvas.create_rectangle(progress_x1, progress_y1, progress_x2, progress_y2, fill="#0a0f1c", outline="")
            progress = self.achievement_progress(ach)
            canvas.create_rectangle(progress_x1, progress_y1, progress_x1 + int((progress_x2 - progress_x1) * progress), progress_y2, fill=border, outline="", tags=(f"ach-{idx}",))
        bottom = max((bounds[3] for bounds in self.achievement_bounds.values()), default=0) + 24
        canvas.configure(scrollregion=(0, 0, width, bottom))
        self.update_achievement_history()

    def achievement_index_at_point(self, x: int, y: int) -> int | None:
        y = int(self.achievement_canvas.canvasy(y)) if hasattr(self, "achievement_canvas") else y
        for index, (x1, y1, x2, y2) in self.achievement_bounds.items():
            if x1 <= x <= x2 and y1 <= y <= y2:
                return index
        return None

    def achievement_activation_index_at_point(self, x: int, y: int) -> int | None:
        y = int(self.achievement_canvas.canvasy(y)) if hasattr(self, "achievement_canvas") else y
        for index, (x1, y1, x2, y2) in self.achievement_activate_bounds.items():
            if x1 <= x <= x2 and y1 <= y <= y2:
                return index
        return None

    def on_achievement_canvas_click(self, event) -> None:
        index = self.achievement_activation_index_at_point(event.x, event.y)
        if index is None:
            return
        self.activate_achievement(index)

    def on_achievement_canvas_motion(self, event) -> None:
        activation_index = self.achievement_activation_index_at_point(event.x, event.y)
        index = self.achievement_index_at_point(event.x, event.y)
        self.achievement_canvas.configure(cursor="hand2" if activation_index is not None else "")
        for item_index in self.achievement_rects:
            self.highlight_achievement(item_index, item_index == index)

    def on_achievement_mousewheel(self, event) -> str:
        direction = -1 if event.delta > 0 else 1
        self.achievement_canvas.yview_scroll(direction * 3, "units")
        return "break"

    def achievement_current_value(self, achievement) -> int:
        metrics = {}
        if self.scan:
            metrics = AchievementEngine.metrics_from_event(
                {
                    "event": "scan.completed",
                    "counts": self.scan.counts,
                    "total_files": self.scan.total_files,
                    "total_size": self.scan.total_size,
                    **self.metrics,
                }
            )
        return int(metrics.get(achievement.metric, self.metrics.get(achievement.metric, 0)))

    def achievement_progress(self, achievement) -> float:
        if achievement.id in self.engine.unlocked_ids:
            return 1.0
        value = self.achievement_current_value(achievement)
        return min(value / achievement.threshold, 1.0)

    def highlight_achievement(self, index: int, active: bool) -> None:
        rect = self.achievement_rects.get(index)
        if rect:
            self.achievement_canvas.itemconfigure(rect, width=3 if active else 2)

    def activate_achievement(self, index: int) -> None:
        achievement = default_achievements()[index]
        if not self.is_achievement_unlocked(achievement):
            self.notify("Reach this achievement before activation.", "info", "Achievement locked")
            return
        if achievement.id in self.activated_achievement_ids:
            self.notify(f"{achievement.name} is already active.", "info", "Achievement")
            return
        self.activated_achievement_ids.add(achievement.id)
        record = self.achievement_history_details.setdefault(achievement.id, {})
        record["activatedAt"] = datetime.now().isoformat(timespec="seconds")
        record["sourceEvent"] = "manual.activation"
        self.persist_state()
        self.notify(f"Activated {achievement.name}.", "success", "Achievement")
        self.render_achievements()
        self.start_activation_animation(index)

    def start_activation_animation(self, index: int) -> None:
        if self.activation_animation_job:
            try:
                self.after_cancel(self.activation_animation_job)
            except tk.TclError:
                pass
            self.activation_animation_job = None
        for item in self.activation_animation_items:
            try:
                self.achievement_canvas.delete(item)
            except tk.TclError:
                pass
        self.activation_animation_items = []
        self.activation_animation_target = index
        bounds = self.achievement_bounds.get(index)
        if not bounds:
            return
        x1, y1, x2, y2 = bounds
        pulse = self.achievement_canvas.create_rectangle(x1 + 3, y1 + 3, x2 - 3, y2 - 3, outline=CYAN, width=3)
        sweep = self.achievement_canvas.create_rectangle(x1 + 4, y1 + 4, x1 + 12, y2 - 4, fill=CYAN, outline="", stipple="gray50")
        self.activation_animation_items = [pulse, sweep]
        self.animate_activation(index, 0)

    def animate_activation(self, index: int, step: int) -> None:
        if index != self.activation_animation_target or not self.activation_animation_items:
            return
        bounds = self.achievement_bounds.get(index)
        if not bounds:
            return
        x1, y1, x2, y2 = bounds
        width = x2 - x1
        sweep_x = x1 + 4 + int(width * min(step, 8) / 8)
        self.achievement_canvas.coords(self.activation_animation_items[1], sweep_x, y1 + 4, min(sweep_x + 54, x2 - 4), y2 - 4)
        self.achievement_canvas.itemconfigure(self.activation_animation_items[0], outline=CYAN if step % 2 == 0 else GREEN)
        if step < 8:
            self.activation_animation_job = self.after(55, lambda: self.animate_activation(index, step + 1))
        else:
            self.activation_animation_job = self.after(320, self.clear_activation_animation)

    def clear_activation_animation(self) -> None:
        for item in self.activation_animation_items:
            try:
                self.achievement_canvas.delete(item)
            except tk.TclError:
                pass
        self.activation_animation_items = []
        self.activation_animation_job = None

    def show_achievement_detail(self, index: int) -> None:
        achievement = default_achievements()[index]
        progress = self.achievement_progress(achievement)
        current = self.achievement_current_value(achievement)
        color = self.rarity_color(achievement.rarity)
        self.detail_card.configure(highlightbackground=color)
        self.detail_title_var.set("Achievement Detail")
        self.detail_name_var.set(achievement.name)
        self.detail_meta_var.set(f"{achievement.rarity} / {achievement.metric}")
        self.detail_icon_label.configure(image=self.achievement_detail_icon_images[index] if index < len(self.achievement_detail_icon_images) else "")
        self.detail_icon_label.image = self.achievement_detail_icon_images[index] if index < len(self.achievement_detail_icon_images) else None
        lines = [
            achievement.description,
            "",
            f"Requirement  {achievement.metric} >= {achievement.threshold}",
            f"Progress     {min(current, achievement.threshold)} / {achievement.threshold}",
        ]
        self.detail_body.configure(state="normal")
        self.detail_body.delete("1.0", "end")
        self.detail_body.insert("end", "\n".join(lines))
        self.detail_body.configure(state="disabled")
        self.detail_progress.delete("all")
        self.detail_progress.update_idletasks()
        width = max(self.detail_progress.winfo_width(), 480)
        self.detail_progress.create_rectangle(0, 8, width, 20, fill="#0a0f1c", outline="")
        self.detail_progress.create_rectangle(0, 8, int(width * progress), 20, fill=color, outline="")
        self.detail_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.detail_overlay.lift()
        self.notify(f"Viewing {achievement.name}.", "info", "Achievement")

    def create_modal(self, title: str, width: int, height: int) -> tk.Toplevel:
        modal = tk.Toplevel(self)
        modal.overrideredirect(True)
        modal.configure(bg="#050608")
        modal.transient(self)
        modal.grab_set()
        outer = tk.Frame(modal, bg="#050608", highlightthickness=1, highlightbackground="#334155")
        outer.place(relx=0, rely=0, relwidth=1, relheight=1)
        chrome = tk.Frame(outer, bg="#050812", height=38)
        chrome.pack(fill="x")
        chrome.pack_propagate(False)
        tk.Label(chrome, text=title, fg=TEXT, bg="#050812", font=("Segoe UI Semibold", 10)).pack(side="left", padx=12)
        self.ghost_button(chrome, "Close", modal.destroy).pack(side="right", fill="y")
        content = tk.Frame(outer, bg=BG)
        content.pack(fill="both", expand=True)
        modal.content = content
        self.center_window(modal, width, height)
        return modal

    def center_window(self, window: tk.Toplevel, width: int, height: int) -> None:
        self.update_idletasks()
        x = self.winfo_x() + max((self.winfo_width() - width) // 2, 0)
        y = self.winfo_y() + max((self.winfo_height() - height) // 2, 0)
        window.geometry(f"{width}x{height}+{x}+{y}")

    def update_achievement_history(self) -> None:
        if not hasattr(self, "achievement_history_label"):
            return
        if not self.notification_history:
            activated = [item_id for item_id, details in self.achievement_history_details.items() if details.get("activatedAt")]
            if activated:
                self.achievement_history_label.configure(text=f"Recent activity: activated {activated[-1]}")
            else:
                self.achievement_history_label.configure(text="Recent unlocks: none yet")
            return
        recent = "  /  ".join(
            f"{item['name']} @ {item.get('unlockedAt', '')}" for item in self.notification_history[-3:]
        )
        activated_count = len([details for details in self.achievement_history_details.values() if details.get("activatedAt")])
        self.achievement_history_label.configure(text=f"Recent unlocks: {recent}  /  Activated: {activated_count}")

    def record_notification(self, achievement: dict) -> None:
        unlocked_at = datetime.now().isoformat(timespec="seconds")
        self.notification_history.append(
            {
                "id": achievement.get("id", ""),
                "name": achievement.get("name", "Achievement"),
                "rarity": achievement.get("rarity", ""),
                "unlockedAt": unlocked_at,
                "sourceEvent": "achievement.evaluate",
            }
        )
        record = self.achievement_history_details.setdefault(achievement.get("id", ""), {})
        record.setdefault("unlockedAt", unlocked_at)
        record.setdefault("sourceEvent", "achievement.evaluate")
        self.notification_history = self.notification_history[-20:]
        self.persist_state()
        self.update_achievement_history()

    def rarity_color(self, rarity: str) -> str:
        return {"普通": GOLD, "稀有": CYAN, "史诗": PURPLE, "传说": "#fff176"}.get(rarity, GOLD)

    def draw_icon(self, canvas: tk.Canvas, x: int, y: int, unlocked: bool, color: str) -> None:
        body = "#f07b6e" if unlocked else "#354052"
        canvas.create_rectangle(x, y, x + 44, y + 44, fill="#080b12", outline=color, width=2)
        canvas.create_rectangle(x + 14, y + 18, x + 32, y + 34, fill=body, outline="")
        canvas.create_rectangle(x + 10, y + 12, x + 36, y + 22, fill=body, outline="")
        canvas.create_rectangle(x + 18, y + 23, x + 21, y + 26, fill="#050608", outline="")
        canvas.create_rectangle(x + 27, y + 23, x + 30, y + 26, fill="#050608", outline="")
        canvas.create_text(x + 4, y + 35, text="0101", fill=color, anchor="nw", font=("Consolas", 7))

    def draw_achievement_icon(self, canvas: tk.Canvas, index: int, x: int, y: int, unlocked: bool, color: str) -> None:
        if index < len(self.achievement_icon_images):
            image = self.achievement_icon_images[index]
            item = canvas.create_image(x + 29, y + 29, image=image, tags=(f"ach-{index}", "achievement-icon"))
            self.achievement_icon_items[index] = item
            if not unlocked:
                canvas.create_rectangle(x, y, x + 58, y + 58, fill="#050812", stipple="gray50", outline=color, tags=(f"ach-{index}",))
            return
        self.draw_icon(canvas, x, y, unlocked, color)

    def show_achievement_popup(self, achievement: dict) -> None:
        self.record_notification(achievement)
        popup = tk.Toplevel(self)
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        width, height = 390, 116
        popup.geometry(f"{width}x{height}+{popup.winfo_screenwidth() - width - 24}+{popup.winfo_screenheight() - height - 64}")
        canvas = tk.Canvas(popup, width=width, height=height, bg="#050608", highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        color = self.rarity_color(achievement.get("rarity", "普通"))
        canvas.create_rectangle(2, 2, width - 2, height - 2, fill="#111827", outline=color, width=2)
        self.draw_icon(canvas, 20, 34, True, color)
        canvas.create_text(86, 20, text="ACHIEVEMENT UNLOCKED", fill=color, anchor="nw", font=("Consolas", 9, "bold"))
        canvas.create_text(86, 44, text=achievement.get("name", "Achievement"), fill=TEXT, anchor="nw", font=("Segoe UI Black", 16))
        canvas.create_text(86, 76, text="0xCVLT · Binary milestone captured", fill=MUTED, anchor="nw", font=("Segoe UI", 9))
        popup.after(3800, popup.destroy)

    def demo_achievement(self) -> None:
        self.show_achievement_popup({"name": "二进制炼金术", "rarity": "史诗"})


def main() -> int:
    ensure_runtime_dirs()
    app = CodexVaultApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
