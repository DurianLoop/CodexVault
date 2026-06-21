from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .core import create_backup, export_pack, import_pack, scan_codex
from .phase2 import ShareCodeStore


@dataclass(frozen=True)
class SkillSummary:
    name: str
    path: str
    valid: bool
    size: int
    modified_at: str
    preview: str


@dataclass(frozen=True)
class MemorySummary:
    path: str
    size: int
    modified_at: str
    content: str
    editable: bool


def read_text_preview(path: Path, limit: int = 12_000) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        return f"Unable to read: {exc}"
    return text[:limit]


def list_skills(codex_root: str | Path) -> list[SkillSummary]:
    root = Path(codex_root)
    skills_root = root / "skills"
    if not skills_root.exists():
        return []
    summaries: list[SkillSummary] = []
    for child in sorted([item for item in skills_root.iterdir() if item.is_dir()], key=lambda p: p.name.lower()):
        skill_file = child / "SKILL.md"
        valid = skill_file.exists()
        stat_path = skill_file if valid else child
        stat = stat_path.stat()
        summaries.append(
            SkillSummary(
                name=child.name,
                path=str(child.relative_to(root)),
                valid=valid,
                size=stat.st_size,
                modified_at=str(int(stat.st_mtime)),
                preview=read_text_preview(skill_file) if valid else "Missing SKILL.md",
            )
        )
    return summaries


def list_memories(codex_root: str | Path) -> list[MemorySummary]:
    root = Path(codex_root)
    memories_root = root / "memories"
    if not memories_root.exists():
        return []
    summaries: list[MemorySummary] = []
    for path in sorted(memories_root.rglob("*.md"), key=lambda p: str(p).lower()):
        if ".git" in path.parts:
            continue
        stat = path.stat()
        summaries.append(
            MemorySummary(
                path=path.relative_to(root).as_posix(),
                size=stat.st_size,
                modified_at=str(int(stat.st_mtime)),
                content=read_text_preview(path, limit=50_000),
                editable=True,
            )
        )
    return summaries


def edit_memory_file(codex_root: str | Path, relative_path: str, content: str) -> None:
    root = Path(codex_root).resolve()
    target = (root / relative_path).resolve()
    if root not in target.parents:
        raise ValueError("Memory path escapes codex root")
    if not relative_path.replace("\\", "/").startswith("memories/"):
        raise ValueError("Only memories can be edited")
    if target.suffix.lower() != ".md":
        raise ValueError("Only markdown memory files can be edited")
    target.write_text(content, encoding="utf-8")


class CodexVaultWorkflow:
    def __init__(self, codex_root: str | Path, app_data: str | Path):
        self.codex_root = Path(codex_root)
        self.app_data = Path(app_data)
        self.backups_dir = self.app_data / "backups"
        self.exports_dir = self.app_data / "exports"
        self.share_store = ShareCodeStore(self.app_data / "share_codes")

    def scan(self):
        return scan_codex(self.codex_root)

    def skills(self) -> list[SkillSummary]:
        return list_skills(self.codex_root)

    def memories(self) -> list[MemorySummary]:
        return list_memories(self.codex_root)

    def create_backup(self) -> Path:
        return create_backup(self.codex_root, self.backups_dir, reason="workflow")

    def export_pack(self) -> Path:
        self.exports_dir.mkdir(parents=True, exist_ok=True)
        pack = self.exports_dir / "workflow.codexvault.zip"
        export_pack(self.codex_root, pack, author="workflow")
        return pack

    def import_pack(self, pack_path: str | Path, target_root: str | Path):
        return import_pack(pack_path, target_root)

    def create_share_code(self, pack_path: str | Path, owner: str = "local") -> str:
        return self.share_store.create_code(pack_path, owner=owner)

    def import_share_code(self, code: str, target_root: str | Path):
        return self.share_store.import_code(code, target_root)
