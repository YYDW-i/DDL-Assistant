# DDL Assistant completion plan

**Goal:** 补齐用户给定规格，在现有项目上交付可启动的 Windows EXE。
**Architecture:** 保留 PySide6 / SQLAlchemy 分层；业务层统一验证和事务；提醒只读取任务数据，不导入 AI；根目录独立启动器供 PyInstaller 使用。
**Tech stack:** Python 3.11-compatible source, PySide6, SQLite, Ollama, Pydantic, Windows-Toasts, PyInstaller, pytest.
**Spec:** 本次用户提供的十节完整规格。

## Global constraints
- 提醒可靠性 > 数据安全性 > 操作便利性 > AI 能力 > 界面美观度。
- 无日期不猜测；AI 修改必须显示预览并得到确认。
- 所有用户数据位于 LOCALAPPDATA/DDLAssistant，升级不得删数据。
- 不声称未实际测试的集成已正常。

## Review focus
- 旧数据库升级、未来版本拒绝、非法输入和导入原子性。
- GUI 与计划任务并发提醒、通知失败后重试、关机后补推。
- AI 缺日期、截图粘贴、预览取消、调用期间关闭窗口。
- 打包入口、用户安装路径含空格和 XML 字符、交互式登录身份。
- 长期开启时每日备份、日志上限、关闭到托盘。

## Tasks
1. [x] 普通任务和数据安全：回归测试先复现；修复查询、验证、迁移、事务、导入和 SQLite 在线备份；运行任务/数据测试。
2. [x] 独立提醒：自定义多时刻、原子去重、通知真实接口和身份、登录及15分钟计划配置；运行提醒测试。
3. [x] AI：JSON Schema、动态日期、严格预览与批量原子提交、查询及修改建议确认；运行 AI 测试。
4. [x] 界面：设置、导入导出、快速输入、日历刷新、线程生命周期和主题持久化；运行 GUI 冒烟测试。
5. [x] 实际打包：根目录启动器，打包脚本检查退出码，用户级安装脚本；全量测试，生成两个 EXE、发行 ZIP 和校验值；隔离数据目录启动 EXE。

## Execution ledger
- Baseline: 27 passed, 1 failed (backup_database ignores active temporary database). No EXE artifacts exist.
- Ruling: 用户明确要求简短方案后立即补齐，直接沿用已指定架构执行，不增加设计确认轮次。
- Ruling: 当前只有 Python 3.13.16 环境；源码保持 3.11 兼容，发行文件使用现有解释器构建，并明确说明未在 3.11 上执行。

- Phases 1–4: passed targeted checks; final suite 61 passed. Real qwen3.5:4b text, image and completion-suggestion acceptance passed.
- Review: fixed cross-process initialization race, asynchronous notification confirmation and minimum-date overflow; each reproduced before repair.
- Frozen runtime: reproduced QtCore load failure caused by incompatible WinRT MSVC preload; runtime-hook regression RED→GREEN. Final EXE rebuild and process smoke pending.

- Final: 61 passed; both final frozen EXEs passed isolated process startup (GUI + backup, WinRT import, reminder dry-run). ZIP CRC, executable contents and SHA256 manifest verified.
- Final: excluded foreign Poppler ICU, removed Windows API-set compatibility stubs and pinned SSL binaries to the building Python runtime. No persistent scheduler registration or actual-user toast was performed.
