# Codex Vault Phase 1 验收与 Phase 2 本地版完成清单

生成时间：2026-06-21

## Phase 1 本地 MVP 验收

| 状态 | 项目 | 验收结果 |
| --- | --- | --- |
| ✅ | Windows 本地桌面端 | `run_codex_vault.bat` 已切换到新版 `codexvault.ui_app`。 |
| ✅ | 深色科技/游戏平台风格 | 已改为左侧导航、暗色背景、高对比卡片、霓虹强调色和 5x5 成就墙。 |
| ✅ | `.codex` 扫描 | 支持扫描本机 `.codex`，并排除 cache/session/sqlite/.git 等运行时目录。 |
| ✅ | Skill 关键状态 | 只展示 skill 数量、有效/无效状态，并预览 `SKILL.md`。 |
| ✅ | Memory 查看 | 展示 memory markdown 文件列表和具体内容。 |
| ✅ | Memory 修改 | 支持直接编辑并保存 memory，保存前自动创建备份。 |
| ✅ | 本地备份 | `create_backup` 自动排除敏感/易变文件。 |
| ✅ | 导出 Pack | `.codexvault.zip` 包含 manifest 和安全资产。 |
| ✅ | 导入 Pack | 导入前自动备份，拒绝绝对路径和路径穿越。 |
| ✅ | 成就墙 | 固定 25 个成就卡，不需要拖动，不展示实现条件。 |
| ✅ | 成就弹窗 | 保留右下角 Steam-like 二进制风格弹窗。 |
| ✅ | 后台自动测试 | 10 个自动化测试覆盖核心逻辑、Phase2 workflow、隐藏 UI 页面切换。 |

## Phase 2 本地模拟版

| 状态 | 项目 | 验收结果 |
| --- | --- | --- |
| ✅ | 用户注册 | 本地用户名/密码注册，密码使用 PBKDF2 哈希存储。 |
| ✅ | 用户登录 | 本地 session token，不联网。 |
| ✅ | 设备绑定 | 登录后登记 Windows Dev Box 设备。 |
| ✅ | 分享码生成 | 从导出的 pack 生成 8 位分享码。 |
| ✅ | 分享码导入 | 输入分享码可导入对应 pack。 |
| ✅ | 本地分享码注册表 | 存储于 `data/share_codes/codes.json`。 |
| ✅ | 无云端依赖 | Phase 2 目前是本地实验室，不需要服务器、数据库或对象存储。 |

## 暂未完成

| 状态 | 项目 | 原因 |
| --- | --- | --- |
| ❌ | 真正云端账号 | 需要后端 API、数据库、部署和权限设计。 |
| ❌ | 跨设备真实同步 | 当前分享码只在本机 `data/share_codes` 内有效。 |
| ❌ | 公网分享码 | 需要对象存储和访问控制。 |
| ❌ | Tauri/Electron 壳 | 当前继续使用低依赖 Tkinter，优先稳定。 |
| ❌ | 原生 Windows Toast | 当前是 Tkinter 无边框窗口模拟。 |
| ❌ | PyInstaller exe | 可作为下一步打包任务。 |

## 自动测试结果

已在工作区通过：

```text
python -B -m unittest discover -s tests -v
Ran 10 tests in 0.438s
OK
```

覆盖范围：

- `.codex` 扫描与敏感文件排除。
- 备份、导出、导入。
- skill 有效性与 `SKILL.md` 预览。
- memory 读取与编辑。
- 本地注册、登录、设备绑定。
- 分享码生成与导入。
- workflow 无 GUI 点击闭环。
- 隐藏 UI 创建、扫描和所有页面切换。
