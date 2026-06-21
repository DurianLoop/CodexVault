# Codex Vault Phase 1 本地 MVP 完成清单

生成时间：2026-06-21

## 已完成

| 状态 | 项目 | 说明 |
| --- | --- | --- |
| ✅ | Windows 本地桌面应用 | 使用 Python 3.13 + Tkinter + 标准库实现，不依赖 npm、Rust、Tauri、Electron 或管理员权限。 |
| ✅ | 默认扫描真实 `.codex` | 默认路径为 `C:\Users\user\.codex`，也支持在界面里手动选择路径。 |
| ✅ | Dashboard 状态总览 | 展示总文件数、memory、skill、prompt、敏感文件、成就进度和健康说明。 |
| ✅ | 资产列表 | 展示 `.codex` 内文件路径、类型、大小、风险状态。 |
| ✅ | 内容预览 | 支持预览较小的文本文件；大文件和不可读文件会安全跳过。 |
| ✅ | 资产分类 | 支持 memory、skill、prompt、rule、plugin、hook、project preset、other。 |
| ✅ | 敏感文件检测 | 检测 `auth.json`、`api_key`、`token`、`secret`、`password`、私钥、`sk-*` 等内容。 |
| ✅ | 易变文件排除 | 默认识别并排除 sessions、cache、sqlite、tmp、logs 等运行时文件。 |
| ✅ | 本地备份点 | 在 `data/backups` 下生成安全备份，默认不包含敏感/易变文件。 |
| ✅ | 导出 `.codexvault.zip` | 生成带 `manifest.json` 的迁移包，默认排除敏感/易变文件。 |
| ✅ | 导入 Pack | 导入前展示确认信息，并自动创建 pre-import 备份。 |
| ✅ | 导入安全检查 | 拒绝绝对路径、`..` 路径穿越、manifest 外文件和敏感/易变条目。 |
| ✅ | 25 个成就 | 已内置 25 个 vibe coding / 配置资产 / 安全 / 迁移类成就。 |
| ✅ | 成就墙 | 有独立 Achievements 页面，显示解锁和未解锁状态。 |
| ✅ | 桌面角落成就弹窗 | 用 Tkinter `Toplevel` 模拟 Steam 风格桌面弹窗，带像素小图标和二进制元素。 |
| ✅ | 本地状态保存 | 成就解锁状态和计数保存在 `data/achievement_state.json`。 |
| ✅ | 低权限实现 | 不需要管理员权限，不联网，不写注册表，不安装依赖。 |
| ✅ | 核心测试 | `python -B -m unittest discover -s tests -v` 通过 4 个核心测试。 |
| ✅ | 语法检查 | 使用 AST 无写入检查通过 5 个 Python 文件。 |
| ✅ | 真实目录扫描验证 | 已扫描 `C:\Users\user\.codex`：7372 个文件、819.0 MB、敏感 1467、易变 7113。 |

## 暂未完成

| 状态 | 项目 | 原因 |
| --- | --- | --- |
| ❌ | 用户名密码登录 | Phase 1 聚焦本地 MVP；登录和云同步建议放到 Phase 2。 |
| ❌ | 云端同步 | 为了先满足低权限、低 bug 风险，当前版本不上传任何内容。 |
| ❌ | 分享码服务 | 需要后端、对象存储和账号体系，建议 Phase 2 实现。 |
| ❌ | GitHub 私有仓库同步 | 当前只做本地 zip 导入导出，Git 同步后续再接。 |
| ❌ | Tauri 原生桌面壳 | 为了避免 Rust/npm 依赖和网络安装风险，本版先用 Python/Tkinter。 |
| ❌ | exe 安装包 | 当前通过 `run_codex_vault.bat` 启动；可后续用 PyInstaller 打包。 |
| ❌ | 真正的 Windows 原生 Toast | 当前使用应用内无边框窗口模拟右下角弹窗。 |
| ❌ | 图像生成版成就图标 | 当前用 Canvas 绘制统一像素图标；后续可替换成 AI 生成 512x512 图标。 |
| ❌ | 复杂冲突合并 | 当前导入是覆盖式写入，但导入前会自动备份。 |
| ❌ | 团队空间和权限 | 属于 Phase 3 社区/团队方向。 |

## 启动方式

```powershell
cd "D:\Codex Vault"
.\run_codex_vault.bat
```

也可以直接运行：

```powershell
cd "D:\Codex Vault"
python -m codexvault.app
```

## 验证命令

```powershell
cd "D:\Codex Vault"
python -B -m unittest discover -s tests -v
python -B -c "import ast, pathlib; files=list(pathlib.Path('codexvault').glob('*.py'))+list(pathlib.Path('tests').glob('*.py')); [ast.parse(p.read_text(encoding='utf-8'), filename=str(p)) for p in files]; print('AST_OK', len(files))"
python -B -c "from codexvault.core import scan_codex, human_size; s=scan_codex(r'C:\Users\user\.codex'); print('SCAN_OK', s.total_files, human_size(s.total_size), s.counts, 'sensitive', len(s.sensitive_items), 'volatile', len(s.volatile_items))"
```

## 下一步建议

1. 先实际打开桌面应用，确认 Dashboard、Assets、Achievements 三个页面是否符合预期。
2. 选一个小型测试 `.codex` 目录做导出和导入，不建议一开始就向真实 `.codex` 导入未知 pack。
3. 下一轮优先做 UI 风格升级、真实成就图标、分享码后端或 PyInstaller 打包。
