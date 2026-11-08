# DDL Assistant

一个面向大学生的 **Windows 桌面端 AI 任务管理器**，解决课程作业、考试、竞赛、活动、个人计划等 DDL 繁多易忘的问题。

- **离线可用**：普通任务管理（增删改查、搜索、今日/本周/逾期视图）完全离线。
- **本地 AI**：需要时调用本机 Ollama（默认 `qwen3.5:4b`，可在设置中改），支持自然语言与截图提取任务。
- **可靠提醒**：独立 `reminder.py` + Windows 任务计划程序 + 系统通知，关机错过的开机补推。

技术栈：Python 3.11+（开发环境 3.13）、PySide6、SQLite + SQLAlchemy 2、Pydantic、Ollama、windows-toasts、PyInstaller。

---

## 当前进度

| 阶段 | 内容 | 状态 |
|---|---|---|
| 一 | 普通任务管理 + SQLite 持久化 + 基础界面 | ✅ 完成 |
| 二 | Windows 通知与后台提醒（独立 reminder） | ⏳ 进行中 |
| 三 | Ollama 自然语言/图片识别 | ⬜ 待开始 |
| 四 | 日历、托盘、快捷键、主题 | ⬜ 待开始 |
| 五 | EXE 打包、端到端测试 | ⬜ 待开始 |

## 目录结构

```
DDL-Assistant/
├── app/
│   ├── main.py            # 程序入口
│   ├── config.py          # 路径与常量（数据在 %LOCALAPPDATA%\DDLAssistant）
│   ├── db/
│   │   ├── models.py      # SQLAlchemy 模型（Task / SchemaMeta）
│   │   ├── session.py     # 引擎、建表、版本化迁移
│   │   └── repository.py  # 仓储：CRUD、今日/本周/逾期查询
│   ├── services/
│   │   └── task_service.py# 业务逻辑
│   └── ui/
│       ├── main_window.py # 主窗口
│       └── dialogs.py     # 新建/编辑对话框
├── tests/                 # pytest 测试（用临时库，不碰真实数据）
├── requirements.txt
└── README.md
```

## 从源码运行（PowerShell）

```powershell
# 1. 进入项目目录
cd E:\DDL-Assistant

# 2. 创建虚拟环境（项目内 .venv，路径短避免 Windows 长路径报错）
python -m venv .venv

# 3. 激活并安装依赖
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

# 4. 启动程序
python -m app.main
```

> 若 PowerShell 禁止运行脚本：先执行 `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`。

## 运行测试

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -v
```

测试使用临时 SQLite 文件，**不会**读写你真实的 `%LOCALAPPDATA%\DDLAssistant\ddl_assistant.db`。

## 数据位置

所有运行时数据保存在 `%LOCALAPPDATA%\DDLAssistant\`：
- `ddl_assistant.db` — SQLite 数据库
- `logs\app.log` — 运行日志
- `backups\` — 自动备份（后续阶段）

升级程序时**不会删除**已有数据；数据库 schema 版本记录在 `schema_meta` 表，后续迁移只增列、不删数据。

## 任务字段

标题、描述、分类、截止日期、截止时间、是否全天、重要程度（低/中/高/紧急）、状态、创建时间、预计工作量（小时）、来源（manual/ai）。

任务按截止日期升序排列，未完成任务排在已完成之前；24 小时内到期的未完成任务会红色高亮，逾期任务单独成视图。
