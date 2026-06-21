# Codex Vault 后端与交互升级验收清单

生成时间：2026-06-21

## 本轮完成

| 状态 | 项目 | 结果 |
| --- | --- | --- |
| ✅ | Memory 改为只读 | UI 不再提供保存按钮，memory markdown 只展示不修改。 |
| ✅ | 成就可交互 | 成就卡支持点击打开详情弹窗。 |
| ✅ | 成就实现要求 | 详情弹窗显示 `metric >= threshold` 的实现要求。 |
| ✅ | 成就进度条 | 未完成成就按当前 metric 显示进度条，完成后满格。 |
| ✅ | 成就 hover 反馈 | 鼠标悬停成就卡会强化边框。 |
| ✅ | 原生 Toast 尝试 | 优先尝试 PowerShell/BurntToast；不可用时回落 Tk 弹窗。 |
| ✅ | 后端 API | 新增 `codexvault.backend`，基于标准库 HTTP server。 |
| ✅ | 数据库 | 后端使用 SQLite 存储 users、sessions、devices、packs、share_codes。 |
| ✅ | 账号权限 | 后端 API 使用 Bearer token 保护设备登记和 pack 下载。 |
| ✅ | 跨设备接口形态 | 后端可绑定 `127.0.0.1` 或局域网地址，支持另一台设备通过 API 获取 pack。 |
| ✅ | 公网分享码雏形 | 分享码 API 已有公开 metadata 查询和授权下载接口；部署到公网即可变成公网分享码。 |
| ✅ | 后端启动脚本 | `run_backend.bat` 启动本地 API。 |
| ✅ | exe launcher 构建脚本 | `build_portable_exe.bat` 使用 PowerShell Add-Type 生成 `CodexVault.exe` 轻量 launcher。 |
| ✅ | 自动交互测试 | 13 个测试覆盖核心、后端、分享码、UI smoke、成就详情模型。 |

## 仍有限制

| 状态 | 项目 | 说明 |
| --- | --- | --- |
| ⚠️ | 真正公网部署 | 代码已具备 API/SQLite/权限，但还没有实际云服务器、域名、HTTPS、反向代理。 |
| ⚠️ | 对象存储 | 当前 pack 存在后端本地磁盘；公网版建议换 S3/R2/OSS。 |
| ⚠️ | Tauri/Electron 壳 | 本机没有 Rust/Cargo，npm 全局环境也不完整；当前仍保留低依赖 Tkinter。 |
| ⚠️ | Native Toast | 依赖系统是否安装 BurntToast；未安装时自动回落 Tk 弹窗。 |
| ⚠️ | PyInstaller exe | 当前环境没有 PyInstaller；已生成 C# launcher，不打包 Python runtime。 |

## 启动方式

桌面端：

```powershell
cd "D:\Codex Vault"
.\run_codex_vault.bat
```

本地后端：

```powershell
cd "D:\Codex Vault"
.\run_backend.bat
```

生成轻量 exe launcher：

```powershell
cd "D:\Codex Vault"
.\build_portable_exe.bat
```

## API 概览

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 健康检查 |
| POST | `/api/register` | 注册用户 |
| POST | `/api/login` | 登录并返回 token |
| POST | `/api/devices` | 登记设备，需要 Bearer token |
| POST | `/api/packs` | 上传 base64 pack，需要 Bearer token，返回分享码 |
| GET | `/api/share-codes/{code}` | 查询分享码公开信息 |
| GET | `/api/packs/{code}/download` | 下载 pack，需要 Bearer token |

## 自动测试结果

```text
python -B -m unittest discover -s tests -v
Ran 13 tests
OK
```

覆盖：

- 后端注册、登录、设备绑定、上传 pack、生成分享码、下载 pack。
- Memory 只读 UI smoke。
- 成就详情 metadata 与进度条模型。
- Pack 导出/导入/分享码导入闭环。
- 隐藏 UI 创建和页面切换。
