from __future__ import annotations

import getpass
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .achievements import AchievementEngine, default_achievements, load_state, save_state
from .core import create_backup, export_pack, human_size, import_pack, load_manifest_from_pack, scan_codex
from .native_toast import show_native_toast
from .phase2 import LocalAuthStore, ShareCodeStore
from .workflow import edit_memory_file, list_memories, list_skills


APP_NAME = "Codex Vault"
ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
BACKUP_DIR = DATA_DIR / "backups"
EXPORT_DIR = DATA_DIR / "exports"
STATE_FILE = DATA_DIR / "achievement_state.json"

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
        self.title("Codex Vault - Phase 2 Local")
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
        self.state = load_state(STATE_FILE)
        self.metrics = dict(self.state.get("metrics", {}))
        self.engine = AchievementEngine(default_achievements(), set(self.state.get("unlocked", [])))
        self.views: dict[str, tk.Frame] = {}

        self._style()
        self._build_shell()
        self.show_view("overview")
        self.after(180, self.refresh_all)

    def _style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Treeview", background="#0d1320", fieldbackground="#0d1320", foreground=TEXT, rowheight=30, borderwidth=0)
        style.configure("Treeview.Heading", background=PANEL_2, foreground=TEXT, font=("Segoe UI Semibold", 10), borderwidth=0)
        style.map("Treeview", background=[("selected", "#1f3a5a")], foreground=[("selected", TEXT)])

    def _build_shell(self) -> None:
        self.sidebar = tk.Frame(self, bg="#070a10", width=220)
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

        self.main = tk.Frame(self, bg=BG)
        self.main.pack(side="left", fill="both", expand=True)
        self._build_header()
        self.content = tk.Frame(self.main, bg=BG)
        self.content.pack(fill="both", expand=True, padx=22, pady=(0, 22))

        for key in ["overview", "skills", "memory", "sync", "achievements", "account"]:
            self.views[key] = tk.Frame(self.content, bg=BG)
        self._build_overview()
        self._build_skills()
        self._build_memory()
        self._build_sync()
        self._build_achievements()
        self._build_account()

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
        tk.Entry(right, textvariable=self.path_var, width=56, bg="#0d1320", fg=TEXT, insertbackground=TEXT, relief="flat", font=("Consolas", 9)).pack(side="left", ipady=8, padx=(0, 8))
        self.action_button(right, "Browse", self.choose_path, CYAN).pack(side="left", padx=4)
        self.action_button(right, "Scan", self.refresh_all, TEAL).pack(side="left", padx=4)

    def action_button(self, master, text: str, command, color: str = CYAN) -> tk.Button:
        return tk.Button(master, text=text, command=command, bg=color, fg="#071016", activebackground=color, activeforeground="#071016", relief="flat", font=("Segoe UI Semibold", 10), padx=14, pady=8, cursor="hand2")

    def ghost_button(self, master, text: str, command) -> tk.Button:
        return tk.Button(master, text=text, command=command, bg=PANEL_2, fg=TEXT, activebackground=PANEL_3, activeforeground=TEXT, relief="flat", font=("Segoe UI Semibold", 10), padx=14, pady=8, cursor="hand2")

    def show_view(self, name: str) -> None:
        for view in self.views.values():
            view.pack_forget()
        for key, btn in self.nav_buttons.items():
            btn.configure(bg="#111827" if key == name else "#070a10", fg=TEXT if key == name else MUTED)
        self.views[name].pack(fill="both", expand=True)
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
        right = VaultCard(row, "Share Code Lab", PURPLE, width=360)
        right.pack(side="left", fill="y")
        right.pack_propagate(False)
        tk.Label(right, text="Phase 2 local simulation:\nshare codes map to packs in data/share_codes.", fg=MUTED, bg=PANEL, justify="left", font=("Segoe UI", 10)).pack(anchor="w", padx=16, pady=16)
        self.share_code_var = tk.StringVar()
        tk.Entry(right, textvariable=self.share_code_var, bg="#0d1320", fg=TEXT, insertbackground=TEXT, relief="flat", font=("Consolas", 14), justify="center").pack(fill="x", padx=16, ipady=10, pady=(0, 12))
        self.action_button(right, "Create Code From Latest Export", self.create_share_code_action, PURPLE).pack(fill="x", padx=16, pady=8)
        self.ghost_button(right, "Import This Code", self.import_share_code_action).pack(fill="x", padx=16, pady=8)
        self.ghost_button(right, "Refresh Registry", self.update_sync_view).pack(fill="x", padx=16, pady=8)

    def _build_achievements(self) -> None:
        root = self.views["achievements"]
        hero = VaultCard(root, "Achievement Wall", GOLD)
        hero.pack(fill="x", pady=(0, 14))
        tk.Label(hero, text="5 x 5 fixed wall. No drag, no condition spoilers.", fg=MUTED, bg=PANEL, font=("Segoe UI", 10)).pack(anchor="w", padx=16, pady=(4, 14))
        self.achievement_canvas = tk.Canvas(root, bg=BG, highlightthickness=0, height=590)
        self.achievement_canvas.pack(fill="both", expand=True)

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
            self.refresh_all()

    def refresh_all(self) -> None:
        self.codex_path = Path(self.path_var.get()).expanduser()
        try:
            self.scan = scan_codex(self.codex_path)
            self.skills = list_skills(self.codex_path)
            self.memories = list_memories(self.codex_path)
        except Exception as exc:
            self.status_text.delete("1.0", "end")
            self.status_text.insert("end", f"Scan failed: {exc}")
            return
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

    def create_backup_action(self) -> None:
        try:
            path = create_backup(self.codex_path, BACKUP_DIR, reason="manual")
            self.bump_metric("backups")
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Backup failed: {exc}")
            return
        messagebox.showinfo(APP_NAME, f"Backup created:\n{path}")

    def export_action(self) -> Path | None:
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        default_name = f"codex-vault-{datetime.now().strftime('%Y%m%d-%H%M%S')}.codexvault.zip"
        output = filedialog.asksaveasfilename(title="Export Codex Vault Pack", initialdir=str(EXPORT_DIR), initialfile=default_name, defaultextension=".zip", filetypes=[("Codex Vault Pack", "*.zip"), ("All files", "*.*")])
        if not output:
            return None
        try:
            export_pack(self.codex_path, output, author=self.current_user or getpass.getuser(), name="Codex Vault Local Pack")
            self.bump_metric("exports")
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Export failed: {exc}")
            return None
        messagebox.showinfo(APP_NAME, f"Pack exported:\n{output}")
        return Path(output)

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
            return
        try:
            manifest = load_manifest_from_pack(pack_path)
            if not messagebox.askyesno(APP_NAME, f"Import {len(manifest.get('items', []))} files?\nA backup will be created first."):
                return
            create_backup(self.codex_path, BACKUP_DIR, reason="before-import")
            result = import_pack(pack_path, self.codex_path)
            self.bump_metric("imports")
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Import failed: {exc}")
            return
        self.refresh_all()
        messagebox.showinfo(APP_NAME, f"Imported {result['imported']} files, skipped {result['skipped']}.")

    def create_share_code_action(self) -> None:
        try:
            pack = self.latest_export()
            if not pack:
                return
            code = self.share_store.create_code(pack, owner=self.current_user or "local")
            self.share_code_var.set(code)
            self.bump_metric("share_codes")
            self.update_sync_view()
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Share code failed: {exc}")
            return
        messagebox.showinfo(APP_NAME, f"Share code created: {code}")

    def import_share_code_action(self) -> None:
        code = self.share_code_var.get().strip().upper()
        if not code:
            messagebox.showwarning(APP_NAME, "Enter a share code first.")
            return
        try:
            create_backup(self.codex_path, BACKUP_DIR, reason="before-share-code-import")
            result = self.share_store.import_code(code, self.codex_path)
            self.bump_metric("imports")
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Share import failed: {exc}")
            return
        self.refresh_all()
        messagebox.showinfo(APP_NAME, f"Code {code} imported {result['imported']} files.")

    def register_action(self) -> None:
        try:
            profile = self.auth.register(self.username_var.get(), self.password_var.get())
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Register failed: {exc}")
            return
        self.account_text.insert("end", f"Registered {profile['username']} at {profile['createdAt']}\n")

    def login_action(self) -> None:
        try:
            session = self.auth.login(self.username_var.get(), self.password_var.get())
            self.auth.register_device(session["sessionToken"], "Windows Dev Box")
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Login failed: {exc}")
            return
        self.current_user = session["username"]
        devices = self.auth.devices(self.current_user)
        self.account_text.delete("1.0", "end")
        self.account_text.insert("end", f"Logged in as {self.current_user}\nSession: {session['sessionToken'][:10]}...\n\nDevices:\n")
        for item in devices:
            self.account_text.insert("end", f"- {item['name']} ({item['platform']}) {item['lastSeenAt']}\n")

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
        save_state(STATE_FILE, {"unlocked": sorted(self.engine.unlocked_ids), "metrics": self.metrics})

    def render_achievements(self) -> None:
        if not hasattr(self, "achievement_canvas"):
            return
        canvas = self.achievement_canvas
        canvas.delete("all")
        self.achievement_rects = {}
        width = max(canvas.winfo_width(), 960)
        card_w = max(170, min(220, (width - 80) // 5))
        card_h = 104
        gap = 12
        for idx, ach in enumerate(default_achievements()[:25]):
            col, row = idx % 5, idx // 5
            x = 18 + col * (card_w + gap)
            y = 12 + row * (card_h + gap)
            unlocked = ach.id in self.engine.unlocked_ids
            border = self.rarity_color(ach.rarity) if unlocked else "#293348"
            fill = "#142033" if unlocked else "#0d1320"
            rect = canvas.create_rectangle(x, y, x + card_w, y + card_h, fill=fill, outline=border, width=2, tags=(f"ach-{idx}", "achievement"))
            self.achievement_rects[idx] = rect
            self.draw_icon(canvas, x + 14, y + 18, unlocked, border)
            canvas.create_text(x + 72, y + 20, text=ach.name, fill=TEXT if unlocked else MUTED, anchor="nw", font=("Segoe UI Semibold", 11), width=card_w - 82, tags=(f"ach-{idx}",))
            canvas.create_text(x + 72, y + 56, text=ach.rarity, fill=border, anchor="nw", font=("Consolas", 9), tags=(f"ach-{idx}",))
            canvas.create_rectangle(x + 72, y + 78, x + card_w - 14, y + 84, fill="#0a0f1c", outline="")
            progress = self.achievement_progress(ach)
            canvas.create_rectangle(x + 72, y + 78, x + 72 + int((card_w - 86) * progress), y + 84, fill=border, outline="", tags=(f"ach-{idx}",))
            canvas.tag_bind(f"ach-{idx}", "<Button-1>", lambda _e, i=idx: self.show_achievement_detail(i))
            canvas.tag_bind(f"ach-{idx}", "<Enter>", lambda _e, i=idx: self.highlight_achievement(i, True))
            canvas.tag_bind(f"ach-{idx}", "<Leave>", lambda _e, i=idx: self.highlight_achievement(i, False))

    def achievement_progress(self, achievement) -> float:
        if achievement.id in self.engine.unlocked_ids:
            return 1.0
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
        value = int(metrics.get(achievement.metric, self.metrics.get(achievement.metric, 0)))
        return min(value / achievement.threshold, 1.0)

    def highlight_achievement(self, index: int, active: bool) -> None:
        rect = self.achievement_rects.get(index)
        if rect:
            self.achievement_canvas.itemconfigure(rect, width=3 if active else 2)

    def show_achievement_detail(self, index: int) -> None:
        achievement = default_achievements()[index]
        progress = self.achievement_progress(achievement)
        current = int(round(progress * achievement.threshold))
        modal = tk.Toplevel(self)
        modal.title(achievement.name)
        modal.geometry("460x300")
        modal.configure(bg=BG)
        modal.transient(self)
        modal.grab_set()
        card = VaultCard(modal, "Achievement Detail", self.rarity_color(achievement.rarity))
        card.pack(fill="both", expand=True, padx=18, pady=18)
        tk.Label(card, text=achievement.name, fg=TEXT, bg=PANEL, font=("Segoe UI Black", 22)).pack(anchor="w", padx=18, pady=(12, 4))
        tk.Label(card, text=achievement.description, fg=MUTED, bg=PANEL, font=("Segoe UI", 11), wraplength=390, justify="left").pack(anchor="w", padx=18, pady=(0, 14))
        tk.Label(card, text=f"Requirement: {achievement.metric} >= {achievement.threshold}", fg=TEXT, bg=PANEL, font=("Consolas", 10)).pack(anchor="w", padx=18)
        tk.Label(card, text=f"Progress: {min(current, achievement.threshold)} / {achievement.threshold}", fg=MUTED, bg=PANEL, font=("Consolas", 10)).pack(anchor="w", padx=18, pady=(4, 8))
        bar = tk.Canvas(card, height=18, bg=PANEL, highlightthickness=0)
        bar.pack(fill="x", padx=18, pady=(0, 18))
        bar.update_idletasks()
        width = max(bar.winfo_width(), 360)
        color = self.rarity_color(achievement.rarity)
        bar.create_rectangle(0, 4, width, 14, fill="#0a0f1c", outline="")
        bar.create_rectangle(0, 4, int(width * progress), 14, fill=color, outline="")
        self.ghost_button(card, "Close", modal.destroy).pack(anchor="e", padx=18, pady=(0, 16))

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

    def show_achievement_popup(self, achievement: dict) -> None:
        if show_native_toast(achievement.get("name", "Achievement"), "Achievement unlocked"):
            return
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
    for path in [DATA_DIR, BACKUP_DIR, EXPORT_DIR]:
        path.mkdir(parents=True, exist_ok=True)
    app = CodexVaultApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
