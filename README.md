# DDL Assistant

一个面向大学生的 **Windows 桌面端 AI 任务管理器**，解决课程作业、考试、竞赛、活动、个人计划等 DDL 繁多易忘的问题。

- **离线可用**：普通任务管理（增删改查、搜索、今日/本周/逾期/月历视图）完全离线。
- **本地 AI**：需要时调用本机 Ollama（默认 `qwen3.5:4b`，可在数据目录改模型名），支持自然语言与截图提取任务。
- **可靠提醒**：独立 `reminder.py` + Windows 任务计划程序 + 系统通知，关机错过的开机补推。

技术栈：Python 3.11+（开发环境 3.13）、PySide6、SQLite + SQLAlchemy 2、Pydantic、Ollama、windows-toasts、PyInstaller。

---

## 当前进度

| 阶段 | 内容 | 状态 |
|---|---|---|
| 一 | 普通任务管理 + SQLite 持久化 + 基础界面 | ✅ |
| 二 | Windows 通知与后台提醒（独立 reminder） | ✅ |
| 三 | Ollama 自然语言/图片识别 | ✅ |
| 四 | 月历、系统托盘、快捷键、亮暗主题 | ✅ |
| 五 | EXE 打包脚本、端到端测试、数据导出备份 | ✅ |

## 目录结构

```
DDL-Assistant/
├── app/
│   ├── main.py              # GUI 入口
│   ├── config.py            # 路径与常量
│   ├── data_io.py           # CSV/JSON 导出、数据库备份
│   ├── db/
│   │   ├── models.py        # Task / NotificationLog / SchemaMeta
│   │   ├── session.py        # 引擎、建表、版本化迁移
│   │   └── repository.py     # 仓储查询
│   ├── services/
│   │   └── task_service.py   # 业务逻辑
│   ├── reminder/            # 独立提醒模块（不调用 AI）
│   │   ├── core.py          # 提醒时间计算、去重
│   │   ├── notifier.py       # Windows 通知
│   │   └── __main__.py       # 任务计划程序入口
│   ├── ai/                  # Ollama 客户端与结构化提取
│   │   ├── client.py
│   │   ├── schema.py         # Pydantic 模型
│   │   └── extractor.py
│   └── ui/
│       ├── main_window.py    # 主窗口（侧边导航/托盘/主题）
│       ├── dialogs.py       # 新建/编辑对话框
│       ├── ai_dialog.py      # AI 智能添加（支持粘贴截图）
│       └── calendar_view.py  # 月历视图
├── scripts/
│   ├── install_reminder.ps1  # 注册/卸载/测试后台提醒任务
│   └── build.ps1             # PyInstaller 打包
├── tests/                    # pytest（28 项）
└── requirements.txt
```

## 从源码运行（PowerShell）

```powershell
cd E:\DDL-Assistant

# 1. 创建虚拟环境（项目内 .venv，路径短避免 Windows 长路径报错）
python -m venv .venv

# 2. 安装依赖
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 3. 启动程序
.\.venv\Scripts\python.exe -m app.main
```

> 若 PowerShell 禁止运行脚本：`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

## 运行测试

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -v
```

测试使用临时 SQLite，**不会**读写你真实的 `%LOCALAPPDATA%\DDLAssistant\ddl_assistant.db`。

## 启用后台提醒（推荐）

```powershell
# 注册 Windows 任务计划（登录时触发 + 每 15 分钟检查一次）
powershell -ExecutionPolicy Bypass -File scripts\install_reminder.ps1

# 立即测试一次
powershell -ExecutionPolicy Bypass -File scripts\install_reminder.ps1 -Test

# 卸载
powershell -ExecutionPolicy Bypass -File scripts\install_reminder.ps1 -Uninstall
```

提醒规则：默认在截止前一天 20:00 推送；已过截止时间未完成的任务，下次检查时补推（覆盖关机/休眠错过的通知）。每条提醒只推一次，任务修改或删除时自动更新。

## 打包成 EXE

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build.ps1
# 产物：dist\DDLAssistant.exe（主程序）、dist\DDLAssistantReminder.exe（后台提醒）
```

打包后把 `DDLAssistant.exe` 放到任意位置即可运行；后台提醒脚本建议用 `install_reminder.ps1` 重新指向打包后的 exe。

## 数据位置与备份

所有运行时数据在 `%LOCALAPPDATA%\DDLAssistant\`：
- `ddl_assistant.db` — SQLite 数据库
- `logs\app.log`、`logs\reminder.log` — 日志
- `backups\ddl_YYYYMMDD_HHMMSS.db` — 自动备份（保留最近 14 份）
- `settings.txt` — 可改 `model=你的模型名`

升级程序**不会删除**已有数据；数据库 schema 版本记录在 `schema_meta` 表，迁移只增列不删数据。

## 使用说明

- **新建任务**：点右上角「+ 新建任务」，填标题、截止日期/时间、分类、优先级。
- **AI 添加**：点「✨ AI 智能添加」，输入一段话，或 Ctrl+V 粘贴课程表/作业截图，AI 识别后在表格里核对，确认才入库。
- **视图切换**：左侧 今日 / 本周 / 全部 / 逾期 / 月历。
- **完成/删除**：在任务上右键。
- **快捷键**：`Ctrl+N` 新建，`Ctrl+Shift+A` AI 添加，`Ctrl+K` 搜索，`Ctrl+`` 最小化到托盘。
- **关闭窗口**：默认最小化到托盘，后台继续提醒；右键托盘图标选「退出」才真正退出。

## 故障排查

| 现象 | 解决 |
|---|---|
| `python -m app.main` 报 `ModuleNotFoundError` | 确认激活了 `.venv`，或用 `.\.venv\Scripts\python.exe -m app.main` |
| 安装 PySide6 报长路径错误 | 必须在项目目录建 `.venv`，不要用全局 Python 直接装 |
| AI 添加一直转圈/失败 | 确认本地 Ollama 已启动（`ollama serve`），且已 `ollama pull qwen3.5:4b`；手动添加不受影响 |
| 收不到 Windows 通知 | 设置 → 系统 → 通知 中允许「DDL Assistant」；首次运行会弹权限请求 |
| 提醒没弹 | 先跑 `scripts\install_reminder.ps1 -Test` 看日志；日志在 `%LOCALAPPDATA%\DDLAssistant\logs\` |
| 改了截止时间但没再提醒 | 正常：修改任务会清空旧提醒记录，按新时间重新计时 |
| 测试临时目录权限错 | conftest 已自动把 pytest 临时目录重定向到项目内 `.pytest-tmp/` |
