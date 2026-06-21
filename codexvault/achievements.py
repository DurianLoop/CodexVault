from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Achievement:
    id: str
    name: str
    description: str
    rarity: str
    icon: str
    metric: str
    threshold: int


def default_achievements() -> list[Achievement]:
    return [
        Achievement("hello_world", "Hello World", "完成第一次 .codex 扫描", "普通", "terminal", "scan_completed", 1),
        Achievement("prompt_engineer", "Prompt 工程师", "保存或导入至少 1 个 prompt", "普通", "scroll", "prompts", 1),
        Achievement("memory_curator", "记忆管理员", "管理 10 条 memory 文件", "普通", "archive", "memories", 10),
        Achievement("skill_collector", "技能收藏家", "安装或导入 5 个 skills", "稀有", "toolbox", "skills", 5),
        Achievement("coffee_dev", "咖啡驱动开发", "在深夜整理过配置资产", "稀有", "coffee", "late_night_events", 1),
        Achievement("binary_alchemist", "二进制炼金术", "完成一次导出再导入闭环", "史诗", "chip", "round_trips", 1),
        Achievement("rollback_survivor", "回滚幸存者", "从备份点恢复过配置", "史诗", "restore", "restores", 1),
        Achievement("migration_master", "迁移大师", "导入过一个 Codex Vault 分享包", "稀有", "portal", "imports", 1),
        Achievement("backup_believer", "备份信徒", "创建过 3 个本地备份点", "普通", "backup", "backups", 3),
        Achievement("safety_gatekeeper", "安全守门人", "拦截过敏感文件导出", "普通", "shield", "sensitive_blocks", 1),
        Achievement("project_presetter", "项目预设师", "拥有 3 个项目预设或规则文件", "普通", "preset", "project_presets", 3),
        Achievement("config_cleaner", "配置洁癖", "修复或发现 5 个健康问题", "普通", "broom", "health_issues_fixed", 5),
        Achievement("share_preacher", "分享布道者", "生成过一个可分享包", "稀有", "share", "exports", 1),
        Achievement("pure_vibe_player", "纯 Vibe 玩家", "完成一次无代码依赖的配置迁移", "稀有", "vibe", "no_code_migrations", 1),
        Achievement("codex_ascension", "配置飞升", "核心资产类型全部出现", "传说", "orbit", "asset_categories_ready", 1),
        Achievement("rule_keeper", "规则守夜人", "拥有至少 3 个 rules 文件", "普通", "rules", "rules", 3),
        Achievement("plugin_scout", "插件侦察兵", "检测到至少 1 个 plugin", "普通", "plugin", "plugins", 1),
        Achievement("hook_tamer", "Hook 驯化师", "检测到至少 1 个 hook", "稀有", "hook", "hooks", 1),
        Achievement("zip_smith", "压缩包铁匠", "生成过 3 个导出包", "普通", "zip", "exports", 3),
        Achievement("binary_gardener", "二进制园丁", "管理文件总数超过 50", "普通", "binary", "total_files", 50),
        Achievement("vault_archivist", "Vault 档案员", "管理文件总量超过 1MB", "普通", "vault", "megabytes", 1),
        Achievement("night_operator", "夜航操作员", "深夜事件达到 3 次", "史诗", "moon", "late_night_events", 3),
        Achievement("safe_importer", "谨慎导入者", "导入前创建过备份", "普通", "safe", "safe_imports", 1),
        Achievement("skill_librarian", "技能图书管理员", "skills 数量达到 10", "史诗", "library", "skills", 10),
        Achievement("vault_legend", "Vault 传说", "解锁至少 15 个成就", "传说", "legend", "unlocked_count", 15),
    ]


class AchievementEngine:
    def __init__(self, achievements: list[Achievement], unlocked_ids: set[str] | None = None):
        self.achievements = achievements
        self.unlocked_ids = unlocked_ids or set()

    def evaluate(self, event: dict[str, Any]) -> list[dict[str, Any]]:
        metrics = self.metrics_from_event(event)
        unlocked: list[dict[str, Any]] = []
        for achievement in self.achievements:
            if achievement.id in self.unlocked_ids:
                continue
            value = int(metrics.get(achievement.metric, 0))
            if value >= achievement.threshold:
                self.unlocked_ids.add(achievement.id)
                unlocked.append(asdict(achievement))

        if len(self.unlocked_ids) >= 15 and "vault_legend" not in self.unlocked_ids:
            legend = next(item for item in self.achievements if item.id == "vault_legend")
            self.unlocked_ids.add(legend.id)
            unlocked.append(asdict(legend))
        return unlocked

    @staticmethod
    def metrics_from_event(event: dict[str, Any]) -> dict[str, int]:
        counts = event.get("counts", {})
        metrics = {
            "scan_completed": 1 if event.get("event") == "scan.completed" else 0,
            "memories": int(counts.get("memories", 0)),
            "skills": int(counts.get("skills", 0)),
            "prompts": int(counts.get("prompts", 0)),
            "rules": int(counts.get("rules", 0)),
            "plugins": int(counts.get("plugins", 0)),
            "hooks": int(counts.get("hooks", 0)),
            "project_presets": int(counts.get("project_presets", 0)) + int(counts.get("rules", 0)),
            "backups": int(counts.get("backups", 0)),
            "total_files": int(event.get("total_files", 0)),
            "megabytes": int(event.get("total_size", 0)) // (1024 * 1024),
            "sensitive_blocks": int(event.get("sensitive_blocks", 0)),
            "health_issues_fixed": int(event.get("health_issues_fixed", 0)),
            "exports": int(event.get("exports", 0)),
            "imports": int(event.get("imports", 0)),
            "restores": int(event.get("restores", 0)),
            "round_trips": int(event.get("round_trips", 0)),
            "safe_imports": int(event.get("safe_imports", 0)),
            "no_code_migrations": int(event.get("no_code_migrations", 0)),
            "late_night_events": int(event.get("late_night_events", 0)),
        }
        asset_categories = ["memories", "skills", "prompts", "project_presets", "backups"]
        metrics["asset_categories_ready"] = 1 if all(metrics.get(key, 0) > 0 for key in asset_categories) else 0
        metrics["unlocked_count"] = int(event.get("unlocked_count", 0))
        return metrics


def load_state(path: str | Path) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return {"unlocked": [], "metrics": {}}
    return json.loads(state_path.read_text(encoding="utf-8"))


def save_state(path: str | Path, state: dict[str, Any]) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
