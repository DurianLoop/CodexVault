from __future__ import annotations

import hashlib
import json
import re
import shutil
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


MANIFEST_NAME = "manifest.json"
SCHEMA_VERSION = "1.0.0"

SENSITIVE_PATTERNS = (
    re.compile(r"api[_-]?key", re.IGNORECASE),
    re.compile(r"token", re.IGNORECASE),
    re.compile(r"secret", re.IGNORECASE),
    re.compile(r"password", re.IGNORECASE),
    re.compile(r"-----BEGIN .*PRIVATE KEY-----", re.IGNORECASE),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
)

SENSITIVE_NAMES = {
    ".env",
    "auth.json",
    "cap_sid",
    "installation_id",
}

VOLATILE_PARTS = {
    ".sandbox",
    ".sandbox-bin",
    ".tmp",
    ".git",
    "__pycache__",
    "tmp",
    "sessions",
    "archived_sessions",
    "cache",
    "node_repl",
    "sqlite",
    "data",
    "backups",
    "exports",
    "share_codes",
}

VOLATILE_SUFFIXES = {
    ".sqlite",
    ".sqlite-shm",
    ".sqlite-wal",
    ".log",
}

TYPE_BY_TOP_LEVEL = {
    "memories": "memory",
    "memory": "memory",
    "skills": "skill",
    "prompts": "prompt",
    "rules": "rule",
    "templates": "template",
    "snippets": "snippet",
    "plugins": "plugin",
    "hooks": "hook",
    "projects": "project_preset",
    "project-presets": "project_preset",
    "presets": "project_preset",
}

COUNT_KEYS = (
    "memories",
    "skills",
    "prompts",
    "rules",
    "plugins",
    "hooks",
    "project_presets",
    "backups",
    "other",
)


@dataclass(frozen=True)
class AssetItem:
    relative_path: str
    type: str
    size: int
    sha256: str
    modified_at: str
    sensitive: bool = False
    volatile: bool = False


@dataclass(frozen=True)
class CodexScan:
    root: Path
    total_files: int
    total_size: int
    counts: dict[str, int]
    items: list[AssetItem]
    sensitive_items: list[AssetItem]
    volatile_items: list[AssetItem]
    scanned_at: str

    def to_manifest(self, *, name: str = "Codex Vault Pack", author: str = "local") -> dict:
        return {
            "schemaVersion": SCHEMA_VERSION,
            "name": name,
            "author": author,
            "createdAt": utc_now(),
            "root": str(self.root),
            "counts": self.counts,
            "totalFiles": self.total_files,
            "totalSize": self.total_size,
            "items": [asdict(item) for item in self.items],
        }


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_relative(path: Path) -> str:
    return path.as_posix()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        return f"unreadable:{exc.__class__.__name__}"
    return digest.hexdigest()


def read_small_text(path: Path, limit: int = 256 * 1024) -> str:
    try:
        if path.stat().st_size > limit:
            return ""
    except OSError:
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def is_sensitive(path: Path, relative: Path) -> bool:
    if path.name.lower() in SENSITIVE_NAMES:
        return True
    rel_text = normalize_relative(relative)
    if any(pattern.search(rel_text) for pattern in SENSITIVE_PATTERNS):
        return True
    content = read_small_text(path)
    return any(pattern.search(content) for pattern in SENSITIVE_PATTERNS)


def is_volatile(relative: Path) -> bool:
    parts = {part.lower() for part in relative.parts}
    if parts & VOLATILE_PARTS:
        return True
    return any(str(relative).lower().endswith(suffix) for suffix in VOLATILE_SUFFIXES)


def classify(relative: Path) -> str:
    if not relative.parts:
        return "other"
    top = relative.parts[0].lower()
    if top in TYPE_BY_TOP_LEVEL:
        return TYPE_BY_TOP_LEVEL[top]
    if relative.name.lower() in {"config.toml", "agents.md", "settings.json"}:
        return "project_preset"
    return "other"


def count_key(asset_type: str) -> str:
    mapping = {
        "memory": "memories",
        "skill": "skills",
        "prompt": "prompts",
        "rule": "rules",
        "plugin": "plugins",
        "hook": "hooks",
        "project_preset": "project_presets",
    }
    return mapping.get(asset_type, "other")


def iter_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if path.is_file():
            yield path


def scan_codex(root: str | Path) -> CodexScan:
    root_path = Path(root).expanduser().resolve()
    if not root_path.exists() or not root_path.is_dir():
        raise FileNotFoundError(f"Codex path does not exist: {root_path}")

    counts = {key: 0 for key in COUNT_KEYS}
    items: list[AssetItem] = []
    sensitive_items: list[AssetItem] = []
    volatile_items: list[AssetItem] = []
    total_size = 0

    for path in sorted(iter_files(root_path), key=lambda item: str(item).lower()):
        relative = path.relative_to(root_path)
        asset_type = classify(relative)
        try:
            stat = path.stat()
            size = stat.st_size
            modified_at = datetime.fromtimestamp(stat.st_mtime, timezone.utc).replace(microsecond=0).isoformat()
        except OSError:
            size = 0
            modified_at = utc_now()
        sensitive = is_sensitive(path, relative)
        volatile = is_volatile(relative)
        file_hash = "volatile:not-hashed" if volatile else sha256_file(path)
        item = AssetItem(
            relative_path=normalize_relative(relative),
            type=asset_type,
            size=size,
            sha256=file_hash,
            modified_at=modified_at,
            sensitive=sensitive,
            volatile=volatile,
        )
        if item.sha256.startswith("unreadable:"):
            item = AssetItem(
                relative_path=item.relative_path,
                type=item.type,
                size=item.size,
                sha256=item.sha256,
                modified_at=item.modified_at,
                sensitive=True,
                volatile=item.volatile,
            )
        items.append(item)
        total_size += size
        counts[count_key(asset_type)] += 1
        if item.sensitive:
            sensitive_items.append(item)
        if item.volatile:
            volatile_items.append(item)

    return CodexScan(
        root=root_path,
        total_files=len(items),
        total_size=total_size,
        counts=counts,
        items=items,
        sensitive_items=sensitive_items,
        volatile_items=volatile_items,
        scanned_at=utc_now(),
    )


def safe_items(scan: CodexScan) -> list[AssetItem]:
    return [item for item in scan.items if not item.sensitive and not item.volatile]


def manifest_for_items(scan: CodexScan, items: list[AssetItem], *, name: str, author: str) -> dict:
    manifest = scan.to_manifest(name=name, author=author)
    manifest["items"] = [asdict(item) for item in items]
    manifest["excluded"] = {
        "sensitive": [asdict(item) for item in scan.sensitive_items],
        "volatile": [asdict(item) for item in scan.volatile_items],
    }
    return manifest


def export_pack(
    codex_root: str | Path,
    output_zip: str | Path,
    *,
    author: str = "local",
    name: str = "Codex Vault Pack",
) -> dict:
    scan = scan_codex(codex_root)
    export_items = safe_items(scan)
    manifest = manifest_for_items(scan, export_items, name=name, author=author)
    output_path = Path(output_zip).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as pack:
        pack.writestr(MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False, indent=2))
        for item in export_items:
            pack.write(scan.root / item.relative_path, item.relative_path)
    return manifest


def create_backup(codex_root: str | Path, backups_dir: str | Path, *, reason: str = "manual") -> Path:
    scan = scan_codex(codex_root)
    export_items = safe_items(scan)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = Path(backups_dir).expanduser().resolve() / f"backup-{timestamp}-{reason}"
    backup_path.mkdir(parents=True, exist_ok=True)
    manifest = manifest_for_items(scan, export_items, name="Codex Vault Local Backup", author="local")
    manifest["reason"] = reason
    (backup_path / MANIFEST_NAME).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    for item in export_items:
        source = scan.root / item.relative_path
        target = backup_path / item.relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return backup_path


def _is_safe_manifest_item(item: dict, names: set[str]) -> tuple[bool, Path | None, str | None]:
    try:
        relative = Path(item["relative_path"])
    except (KeyError, TypeError):
        return False, None, "missing relative_path"
    if item.get("sensitive") or item.get("volatile"):
        return False, relative, "sensitive or volatile"
    if relative.is_absolute() or ".." in relative.parts:
        return False, relative, "unsafe path"
    source_name = normalize_relative(relative)
    if source_name not in names:
        return False, relative, "missing from pack"
    return True, relative, None


def preview_import_pack(pack_path: str | Path, target_root: str | Path) -> dict:
    pack_file = Path(pack_path).expanduser().resolve()
    target = Path(target_root).expanduser().resolve()
    if not pack_file.exists():
        raise FileNotFoundError(f"Pack not found: {pack_file}")

    added: list[str] = []
    replaced: list[str] = []
    skipped: list[dict[str, str]] = []
    total_size = 0
    manifest: dict = {}
    with zipfile.ZipFile(pack_file) as pack:
        names = set(pack.namelist())
        if MANIFEST_NAME not in names:
            raise ValueError("Pack is missing manifest.json")
        manifest = json.loads(pack.read(MANIFEST_NAME).decode("utf-8"))
        for item in manifest.get("items", []):
            safe, relative, reason = _is_safe_manifest_item(item, names)
            if not safe:
                skipped.append({"path": normalize_relative(relative) if relative else "(unknown)", "reason": reason or "skipped"})
                continue
            assert relative is not None
            total_size += int(item.get("size", 0))
            rel_text = normalize_relative(relative)
            if (target / relative).exists():
                replaced.append(rel_text)
            else:
                added.append(rel_text)

    return {
        "pack": str(pack_file),
        "target": str(target),
        "manifest": {
            "name": manifest.get("name", "Codex Vault Pack"),
            "author": manifest.get("author", "unknown"),
            "createdAt": manifest.get("createdAt", ""),
            "schemaVersion": manifest.get("schemaVersion", ""),
        },
        "added": added,
        "replaced": replaced,
        "skipped": skipped,
        "totalSize": total_size,
    }


def import_pack(pack_path: str | Path, target_root: str | Path) -> dict:
    pack_file = Path(pack_path).expanduser().resolve()
    target = Path(target_root).expanduser().resolve()
    if not pack_file.exists():
        raise FileNotFoundError(f"Pack not found: {pack_file}")
    target.mkdir(parents=True, exist_ok=True)

    imported = 0
    skipped = 0
    with zipfile.ZipFile(pack_file) as pack:
        names = set(pack.namelist())
        if MANIFEST_NAME not in names:
            raise ValueError("Pack is missing manifest.json")
        manifest = json.loads(pack.read(MANIFEST_NAME).decode("utf-8"))
        for item in manifest.get("items", []):
            safe, relative, _reason = _is_safe_manifest_item(item, names)
            if not safe or relative is None:
                skipped += 1
                continue
            source_name = normalize_relative(relative)
            target_file = target / relative
            target_file.parent.mkdir(parents=True, exist_ok=True)
            with pack.open(source_name) as source, target_file.open("wb") as dest:
                shutil.copyfileobj(source, dest)
            imported += 1
    return {"imported": imported, "skipped": skipped, "target": str(target)}


def restore_backup(backup_path: str | Path, target_root: str | Path) -> dict:
    backup = Path(backup_path).expanduser().resolve()
    target = Path(target_root).expanduser().resolve()
    manifest_path = backup / MANIFEST_NAME
    if not manifest_path.exists():
        raise FileNotFoundError(f"Backup manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    restored = 0
    skipped = 0
    for item in manifest.get("items", []):
        relative = Path(item["relative_path"])
        if item.get("sensitive") or item.get("volatile") or relative.is_absolute() or ".." in relative.parts:
            skipped += 1
            continue
        source = backup / relative
        if not source.exists():
            skipped += 1
            continue
        target_file = target / relative
        target_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target_file)
        restored += 1
    return {"restored": restored, "skipped": skipped, "target": str(target), "backup": str(backup)}


def load_manifest_from_pack(pack_path: str | Path) -> dict:
    with zipfile.ZipFile(Path(pack_path).expanduser().resolve()) as pack:
        return json.loads(pack.read(MANIFEST_NAME).decode("utf-8"))


def human_size(size: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{size} B"
