from __future__ import annotations

import json
import tkinter as tk
import getpass
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .achievements import AchievementEngine, default_achievements, load_state, save_state
from .core import (
    CodexScan,
    AssetItem,
    create_backup,
    export_pack,
    human_size,
    import_pack,
    load_manifest_from_pack,
    scan_codex,
)
from .paths import BACKUP_DIR, DATA_DIR, EXPORT_DIR, STATE_FILE, ensure_runtime_dirs, project_root


APP_NAME = "Codex Vault"
ROOT_DIR = project_root()

BG = "#101114"
PANEL = "#17191f"
PANEL_2 = "#20242c"
TEXT = "#f2efe6"
MUTED = "#9a9aa3"
GOLD = "#d6ad4d"
BLUE = "#67b7ff"
PURPLE = "#b68cff"
RED = "#ff6b6b"
GREEN = "#6dd17c"


def default_codex_path() -> Path:
    home_path = Path.home() / ".codex"
    if home_path.exists():
        return home_path
    workspace_path = Path("D:/AI_cpt/.codex")
    if workspace_path.exists():
        return workspace_path
    return home_path


class CodexVaultApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_NAME} - Local MVP")
        self.geometry("1240x780")
        self.minsize(1100, 700)
        self.configure(bg=BG)
        self.codex_path = default_codex_path()
        self.scan: CodexScan | None = None
        self.selected_item: AssetItem | None = None
        self.state = load_state(STATE_FILE)
        self.engine = AchievementEngine(default_achievements(), set(self.state.get("unlocked", [])))
        self.metrics = dict(self.state.get("metrics", {}))
        self._build_style()
        self._build_ui()
        self.after(200, self.refresh_scan)

    def _build_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("Title.TLabel", background=BG, foreground=TEXT, font=("Segoe UI Semibold", 20))
        style.configure("Metric.TLabel", background=PANEL, foreground=TEXT, font=("Segoe UI Semibold", 18))
        style.configure("MetricSmall.TLabel", background=PANEL, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("TButton", font=("Segoe UI Semibold", 10), padding=(12, 8), borderwidth=0)
        style.map("TButton", background=[("active", "#2b303a")], foreground=[("active", TEXT)])
        style.configure("Treeview", background=PANEL, foreground=TEXT, fieldbackground=PANEL, rowheight=28, borderwidth=0)
        style.configure("Treeview.Heading", background=PANEL_2, foreground=TEXT, font=("Segoe UI Semibold", 10))
        style.map("Treeview", background=[("selected", "#2e3b4e")], foreground=[("selected", TEXT)])
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=PANEL, foreground=MUTED, padding=(16, 9), borderwidth=0)
        style.map("TNotebook.Tab", background=[("selected", PANEL_2)], foreground=[("selected", TEXT)])

    def _build_ui(self) -> None:
        header = ttk.Frame(self, style="TFrame")
        header.pack(fill="x", padx=24, pady=(20, 12))
        ttk.Label(header, text="Codex Vault", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="Local Windows MVP", style="Muted.TLabel").pack(side="left", padx=(12, 0), pady=(8, 0))
        ttk.Button(header, text="选择 .codex 路径", command=self.choose_path).pack(side="right", padx=(8, 0))
        ttk.Button(header, text="重新扫描", command=self.refresh_scan).pack(side="right", padx=(8, 0))

        path_bar = ttk.Frame(self, style="Panel.TFrame")
        path_bar.pack(fill="x", padx=24, pady=(0, 14))
        self.path_var = tk.StringVar(value=str(self.codex_path))
        path_entry = tk.Entry(
            path_bar,
            textvariable=self.path_var,
            bg=PANEL,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            font=("Consolas", 10),
        )
        path_entry.pack(fill="x", padx=14, pady=12)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=24, pady=(0, 24))
        self.dashboard_tab = ttk.Frame(self.notebook, style="TFrame")
        self.assets_tab = ttk.Frame(self.notebook, style="TFrame")
        self.achievements_tab = ttk.Frame(self.notebook, style="TFrame")
        self.notebook.add(self.dashboard_tab, text="Dashboard")
        self.notebook.add(self.assets_tab, text="Assets")
        self.notebook.add(self.achievements_tab, text="Achievements")
        self._build_dashboard()
        self._build_assets()
        self._build_achievements()

    def _build_dashboard(self) -> None:
        metric_row = ttk.Frame(self.dashboard_tab, style="TFrame")
        metric_row.pack(fill="x", pady=(0, 16))
        self.metric_labels: dict[str, tuple[ttk.Label, ttk.Label]] = {}
        for key, label in [
            ("total_files", "Total Files"),
            ("memories", "Memories"),
            ("skills", "Skills"),
            ("prompts", "Prompts"),
            ("sensitive", "Sensitive"),
            ("achievements", "Achievements"),
        ]:
            card = ttk.Frame(metric_row, style="Panel.TFrame")
            card.pack(side="left", fill="x", expand=True, padx=(0, 10))
            value_label = ttk.Label(card, text="--", style="Metric.TLabel")
            value_label.pack(anchor="w", padx=16, pady=(14, 0))
            name_label = ttk.Label(card, text=label, style="MetricSmall.TLabel")
            name_label.pack(anchor="w", padx=16, pady=(2, 14))
            self.metric_labels[key] = (value_label, name_label)

        action_panel = ttk.Frame(self.dashboard_tab, style="Panel.TFrame")
        action_panel.pack(fill="x", pady=(0, 16))
        ttk.Button(action_panel, text="创建本地备份", command=self.create_backup_action).pack(side="left", padx=12, pady=12)
        ttk.Button(action_panel, text="导出 .codexvault.zip", command=self.export_action).pack(side="left", padx=6, pady=12)
        ttk.Button(action_panel, text="导入 Pack", command=self.import_action).pack(side="left", padx=6, pady=12)
        ttk.Button(action_panel, text="测试成就弹窗", command=self.demo_achievement).pack(side="left", padx=6, pady=12)

        self.health_text = tk.Text(
            self.dashboard_tab,
            height=15,
            bg=PANEL,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            wrap="word",
            font=("Segoe UI", 10),
        )
        self.health_text.pack(fill="both", expand=True)

    def _build_assets(self) -> None:
        container = ttk.Frame(self.assets_tab, style="TFrame")
        container.pack(fill="both", expand=True)
        left = ttk.Frame(container, style="Panel.TFrame")
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        right = ttk.Frame(container, style="Panel.TFrame")
        right.pack(side="left", fill="both", expand=True)

        columns = ("type", "size", "risk")
        self.asset_tree = ttk.Treeview(left, columns=columns, show="tree headings")
        self.asset_tree.heading("#0", text="Path")
        self.asset_tree.heading("type", text="Type")
        self.asset_tree.heading("size", text="Size")
        self.asset_tree.heading("risk", text="Risk")
        self.asset_tree.column("#0", width=360)
        self.asset_tree.column("type", width=110)
        self.asset_tree.column("size", width=90)
        self.asset_tree.column("risk", width=120)
        self.asset_tree.pack(fill="both", expand=True, padx=10, pady=10)
        self.asset_tree.bind("<<TreeviewSelect>>", self.preview_selected)

        ttk.Label(right, text="Content Preview", style="TLabel").pack(anchor="w", padx=12, pady=(12, 4))
        self.preview = tk.Text(
            right,
            bg="#0d0f13",
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            wrap="none",
            font=("Consolas", 10),
        )
        self.preview.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    def _build_achievements(self) -> None:
        self.achievement_canvas = tk.Canvas(self.achievements_tab, bg=BG, highlightthickness=0)
        self.achievement_canvas.pack(fill="both", expand=True)

    def choose_path(self) -> None:
        path = filedialog.askdirectory(title="选择 .codex 目录", initialdir=str(self.codex_path.parent if self.codex_path.exists() else Path.home()))
        if path:
            self.codex_path = Path(path)
            self.path_var.set(str(self.codex_path))
            self.refresh_scan()

    def refresh_scan(self) -> None:
        self.codex_path = Path(self.path_var.get()).expanduser()
        try:
            self.scan = scan_codex(self.codex_path)
        except Exception as exc:
            self.scan = None
            self.health_text.delete("1.0", "end")
            self.health_text.insert("end", f"扫描失败：{exc}\n\n请选择一个存在的 .codex 目录。")
            return
        self.update_dashboard()
        self.update_assets()
        self.evaluate_achievements(
            {
                "event": "scan.completed",
                "counts": self.scan.counts,
                "total_files": self.scan.total_files,
                "total_size": self.scan.total_size,
                "sensitive_blocks": len(self.scan.sensitive_items),
                "health_issues_fixed": len(self.scan.sensitive_items) + len(self.scan.volatile_items),
                "backups": self.metrics.get("backups", 0),
                "exports": self.metrics.get("exports", 0),
                "imports": self.metrics.get("imports", 0),
            }
        )

    def update_dashboard(self) -> None:
        if not self.scan:
            return
        values = {
            "total_files": str(self.scan.total_files),
            "memories": str(self.scan.counts.get("memories", 0)),
            "skills": str(self.scan.counts.get("skills", 0)),
            "prompts": str(self.scan.counts.get("prompts", 0)),
            "sensitive": str(len(self.scan.sensitive_items)),
            "achievements": f"{len(self.engine.unlocked_ids)}/25",
        }
        for key, value in values.items():
            self.metric_labels[key][0].configure(text=value)

        lines = [
            f"扫描路径: {self.scan.root}",
            f"扫描时间: {self.scan.scanned_at}",
            f"总大小: {human_size(self.scan.total_size)}",
            "",
            "健康状态",
            f"- 可管理资产: {len([item for item in self.scan.items if not item.sensitive and not item.volatile])}",
            f"- 敏感文件: {len(self.scan.sensitive_items)}，默认不会导出或备份。",
            f"- 易变文件: {len(self.scan.volatile_items)}，例如 sessions/cache/sqlite，默认不会导出或备份。",
            "",
            "隐私默认策略",
            "- auth.json、token、api_key、secret、password、私钥不会进入分享包。",
            "- 导入 pack 前会先创建本地备份点。",
            "- 所有数据默认留在本机，本 MVP 不做云端上传。",
        ]
        if self.scan.sensitive_items:
            lines.append("")
            lines.append("敏感文件预览")
            lines.extend(f"- {item.relative_path}" for item in self.scan.sensitive_items[:12])
        self.health_text.delete("1.0", "end")
        self.health_text.insert("end", "\n".join(lines))

    def update_assets(self) -> None:
        self.asset_tree.delete(*self.asset_tree.get_children())
        if not self.scan:
            return
        for item in self.scan.items:
            risk = "sensitive" if item.sensitive else "volatile" if item.volatile else "safe"
            self.asset_tree.insert(
                "",
                "end",
                iid=item.relative_path,
                text=item.relative_path,
                values=(item.type, human_size(item.size), risk),
            )

    def preview_selected(self, _event: object | None = None) -> None:
        if not self.scan:
            return
        selection = self.asset_tree.selection()
        if not selection:
            return
        rel = selection[0]
        self.selected_item = next((item for item in self.scan.items if item.relative_path == rel), None)
        path = self.scan.root / rel
        self.preview.delete("1.0", "end")
        if not self.selected_item:
            return
        header = [
            f"Path: {self.selected_item.relative_path}",
            f"Type: {self.selected_item.type}",
            f"Size: {human_size(self.selected_item.size)}",
            f"SHA-256: {self.selected_item.sha256}",
            f"Risk: {'sensitive' if self.selected_item.sensitive else 'volatile' if self.selected_item.volatile else 'safe'}",
            "",
        ]
        self.preview.insert("end", "\n".join(header))
        if self.selected_item.size > 256 * 1024:
            self.preview.insert("end", "文件较大，预览已跳过。")
            return
        try:
            self.preview.insert("end", path.read_text(encoding="utf-8", errors="ignore"))
        except Exception as exc:
            self.preview.insert("end", f"无法预览：{exc}")

    def create_backup_action(self) -> None:
        if not self.scan:
            self.refresh_scan()
        if not self.scan:
            return
        try:
            backup_path = create_backup(self.scan.root, BACKUP_DIR, reason="manual")
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"备份失败：{exc}")
            return
        self.bump_metric("backups")
        self.evaluate_achievements({"event": "backup.created", "counts": self.scan.counts, "backups": self.metrics.get("backups", 0)})
        messagebox.showinfo(APP_NAME, f"备份已创建：\n{backup_path}")

    def export_action(self) -> None:
        if not self.scan:
            self.refresh_scan()
        if not self.scan:
            return
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        default_name = f"codex-vault-{datetime.now().strftime('%Y%m%d-%H%M%S')}.codexvault.zip"
        output = filedialog.asksaveasfilename(
            title="导出 Codex Vault Pack",
            initialdir=str(EXPORT_DIR),
            initialfile=default_name,
            defaultextension=".zip",
            filetypes=[("Codex Vault Pack", "*.zip"), ("All files", "*.*")],
        )
        if not output:
            return
        try:
            manifest = export_pack(self.scan.root, output, author=getpass.getuser(), name="Codex Vault Local Pack")
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"导出失败：{exc}")
            return
        self.bump_metric("exports")
        self.evaluate_achievements(
            {
                "event": "pack.exported",
                "counts": self.scan.counts,
                "exports": self.metrics.get("exports", 0),
                "sensitive_blocks": len(manifest.get("excluded", {}).get("sensitive", [])),
            }
        )
        messagebox.showinfo(APP_NAME, f"导出完成：\n{output}\n\n已排除敏感/易变文件。")

    def import_action(self) -> None:
        if not self.scan:
            self.refresh_scan()
        if not self.scan:
            return
        pack_path = filedialog.askopenfilename(
            title="选择 Codex Vault Pack",
            initialdir=str(EXPORT_DIR if EXPORT_DIR.exists() else ROOT_DIR),
            filetypes=[("Codex Vault Pack", "*.zip"), ("All files", "*.*")],
        )
        if not pack_path:
            return
        try:
            manifest = load_manifest_from_pack(pack_path)
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"无法读取 pack：{exc}")
            return
        item_count = len(manifest.get("items", []))
        confirm = messagebox.askyesno(
            APP_NAME,
            "导入前会先创建本地备份点。\n\n"
            f"Pack: {manifest.get('name', 'Unnamed')}\n"
            f"作者: {manifest.get('author', 'unknown')}\n"
            f"文件数: {item_count}\n"
            f"目标: {self.scan.root}\n\n"
            "继续导入吗？",
        )
        if not confirm:
            return
        try:
            create_backup(self.scan.root, BACKUP_DIR, reason="before-import")
            result = import_pack(pack_path, self.scan.root)
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"导入失败：{exc}")
            return
        self.bump_metric("imports")
        self.bump_metric("safe_imports")
        self.evaluate_achievements(
            {
                "event": "pack.imported",
                "counts": self.scan.counts,
                "imports": self.metrics.get("imports", 0),
                "safe_imports": self.metrics.get("safe_imports", 0),
                "no_code_migrations": 1,
            }
        )
        self.refresh_scan()
        messagebox.showinfo(APP_NAME, f"导入完成：{result['imported']} 个文件，跳过 {result['skipped']} 个文件。")

    def bump_metric(self, key: str, amount: int = 1) -> None:
        self.metrics[key] = int(self.metrics.get(key, 0)) + amount
        self.persist_state()

    def evaluate_achievements(self, event: dict) -> None:
        event = dict(event)
        event.update(self.metrics)
        event["unlocked_count"] = len(self.engine.unlocked_ids)
        new_items = self.engine.evaluate(event)
        if new_items:
            self.persist_state()
            self.update_dashboard()
            self.render_achievements()
            for index, achievement in enumerate(new_items[:3]):
                self.after(250 + index * 900, lambda item=achievement: self.show_achievement_popup(item))
        else:
            self.render_achievements()

    def persist_state(self) -> None:
        self.state = {"unlocked": sorted(self.engine.unlocked_ids), "metrics": self.metrics}
        save_state(STATE_FILE, self.state)

    def render_achievements(self) -> None:
        canvas = self.achievement_canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), 1100)
        x, y = 24, 24
        card_w, card_h = 350, 112
        gap = 16
        for idx, ach in enumerate(default_achievements()):
            unlocked = ach.id in self.engine.unlocked_ids
            col = idx % 3
            row = idx // 3
            x = 24 + col * (card_w + gap)
            y = 24 + row * (card_h + gap)
            fill = PANEL_2 if unlocked else "#15161a"
            outline = self.rarity_color(ach.rarity) if unlocked else "#2a2d34"
            canvas.create_rectangle(x, y, x + card_w, y + card_h, fill=fill, outline=outline, width=2)
            self.draw_pixel_icon(canvas, x + 16, y + 18, unlocked, ach.rarity)
            canvas.create_text(x + 92, y + 22, text=ach.name, fill=TEXT if unlocked else MUTED, anchor="nw", font=("Segoe UI Semibold", 13))
            canvas.create_text(x + 92, y + 50, text=ach.description, fill=MUTED, anchor="nw", font=("Segoe UI", 9), width=230)
            canvas.create_text(x + 92, y + 82, text=ach.rarity, fill=outline, anchor="nw", font=("Consolas", 9))
        canvas.configure(scrollregion=(0, 0, width, y + card_h + 24))

    def rarity_color(self, rarity: str) -> str:
        return {"普通": GOLD, "稀有": BLUE, "史诗": PURPLE, "传说": "#f7e27b"}.get(rarity, GOLD)

    def draw_pixel_icon(self, canvas: tk.Canvas, x: int, y: int, unlocked: bool, rarity: str) -> None:
        border = self.rarity_color(rarity) if unlocked else "#454851"
        fill = "#101114" if unlocked else "#1c1d22"
        canvas.create_rectangle(x, y, x + 58, y + 58, fill=fill, outline=border, width=2)
        color = "#f08a72" if unlocked else "#4a4d57"
        canvas.create_rectangle(x + 20, y + 24, x + 42, y + 44, fill=color, outline="")
        canvas.create_rectangle(x + 16, y + 18, x + 46, y + 28, fill=color, outline="")
        canvas.create_rectangle(x + 24, y + 14, x + 28, y + 18, fill=border, outline="")
        canvas.create_rectangle(x + 34, y + 14, x + 38, y + 18, fill=border, outline="")
        canvas.create_rectangle(x + 24, y + 28, x + 28, y + 32, fill="#0a0a0a", outline="")
        canvas.create_rectangle(x + 36, y + 28, x + 40, y + 32, fill="#0a0a0a", outline="")
        for i, bit in enumerate("0101"):
            canvas.create_text(x + 10 + i * 10, y + 50, text=bit, fill=border, font=("Consolas", 7))

    def show_achievement_popup(self, achievement: dict) -> None:
        popup = tk.Toplevel(self)
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        popup.configure(bg="#050608")
        w, h = 360, 112
        screen_w = popup.winfo_screenwidth()
        screen_h = popup.winfo_screenheight()
        popup.geometry(f"{w}x{h}+{screen_w - w - 24}+{screen_h - h - 64}")
        canvas = tk.Canvas(popup, width=w, height=h, bg="#050608", highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        color = self.rarity_color(achievement.get("rarity", "普通"))
        canvas.create_rectangle(2, 2, w - 2, h - 2, outline=color, width=2, fill="#111318")
        self.draw_pixel_icon(canvas, 18, 26, True, achievement.get("rarity", "普通"))
        canvas.create_text(92, 18, text="成就解锁", fill=color, anchor="nw", font=("Segoe UI", 9))
        canvas.create_text(92, 40, text=achievement.get("name", "Achievement"), fill=TEXT, anchor="nw", font=("Segoe UI Semibold", 16))
        canvas.create_text(92, 70, text=achievement.get("description", ""), fill=MUTED, anchor="nw", font=("Segoe UI", 9), width=240)
        canvas.create_text(300, 18, text="0101", fill=color, anchor="nw", font=("Consolas", 8))
        popup.after(4200, popup.destroy)

    def demo_achievement(self) -> None:
        self.show_achievement_popup(
            {
                "name": "二进制炼金术",
                "description": "AI 写了，测试炸了，AI 又修好了。",
                "rarity": "史诗",
            }
        )


def main() -> int:
    ensure_runtime_dirs()
    app = CodexVaultApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
