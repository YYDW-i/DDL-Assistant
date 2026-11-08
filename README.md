# DDL Assistant

面向大学生的 Windows 本地任务管理器。普通任务管理完全离线；AI 使用本机 Ollama，默认模型 `qwen3.5:4b`。

## 直接运行 EXE

本次新版实际构建文件在 `dist/DDLAssistant-1.1.0`（旧版运行中，不覆盖被占用的文件）：

- `DDLAssistant.exe`：主程序，双击运行，不需要安装 Python。
- `DDLAssistantReminder.exe`：独立后台提醒，不加载 GUI 或 Ollama。
- `DDLAssistant-Windows-x64.zip`：两个 EXE、安装脚本、说明及 SHA256 校验文件。

建议解压 ZIP 后双击 **install.cmd**。安装到当前用户的 `%LOCALAPPDATA%\DDLAssistant\bin`，创建带应用身份的开始菜单快捷方式，启用登录检查及每15分钟检查的后台计划任务。无需管理员权限。升级前先从托盘退出程序，再运行新版安装脚本；任务数据库保留。

单独运行主 EXE 也可用：窗口打开或驻留托盘时每分钟检查提醒。**完全退出 GUI 后，必须已启用计划任务才能继续提醒**。提醒 EXE 和安装脚本应保存在固定目录，移动后重新配置。

发行文件为 Windows x64，使用当前机器已有的 **Python 3.13.16** 构建。源码使用 Python 3.11 兼容语法；本次没有可用的 3.11 解释器，未声称已经在 3.11 上测试。EXE 未购买代码签名证书，Windows SmartScreen 可能显示未识别的发布者。

## 从创建虚拟环境到启动（PowerShell）

```powershell
cd E:\DDL-Assistant

# 使用已安装的 Python 3.11 创建环境；若已有其他版本的 .venv，先另取环境名称
py -3.11 -m venv .venv

# 无需激活环境，也无需永久修改执行策略
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m app.main

# 运行自动化测试（隔离数据库与 LOCALAPPDATA）
.\.venv\Scripts\python.exe -m pytest tests -q

# 真正生成两个 EXE 和发行 ZIP；任何测试或打包失败都会停止
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\build.ps1 -OutputDirectory dist\DDLAssistant-1.1.0
```

如果 `py -3.11` 提示未安装，请先安装 Python 3.11 x64。已有环境可直接使用其 `python.exe`。打包脚本支持 `-PythonPath 其他环境\Scripts\python.exe`。`requirements-lock.txt` 记录此次 Windows / Python 3.13 构建的精确依赖，用于复现该环境；跨 Python 版本优先使用 `requirements.txt`。

## 已实现功能

- 新增、编辑、完成、重新打开、删除和搜索；标题、说明、分类、截止日期/时间、全天、重要程度、预计小时数、来源、创建时间。
- 今日、本周（周一至周日）、全部（包含已完成）、精确到时刻的逾期列表、24小时内 DDL 标识及月历。
- 独立「今日计划」：勾选导入已有当日任务、手动添加、AI根据描述拟订计划、安排开始时间、同步完成状态；移出计划不删除原任务，可查看其他日期和历史计划。
- SQLite 持久化，WAL、忙等待、数据库约束、原子批量操作和版本化迁移。旧库升级前先快照，未知未来版本拒绝打开。
- JSON / CSV 导入导出，导入预览确认且整批成功或整批回滚；重复导入会新增副本，不覆盖原任务。
- 每日自动在线备份；GUI 长期开启或计划任务执行时检查。普通备份保留最近14份，迁移备份独立保留；数据菜单可手动备份。
- 本地 AI 文字及 PNG/JPG 图片识别、在输入框 Ctrl+V 粘贴截图，支持多个任务。调用使用工作线程、超时和 Pydantic JSON Schema。
- AI 预览可编辑和逐条勾选。无明确日期时保留空白，须手填；歧义日期须勾选确认；错误行不会导致部分入库。
- AI 菜单支持查询以及修改、删除、完成、重新打开建议。显示任务名称及字段前后变化，再次确认后原子执行；预览期间任务变化则拒绝旧操作。
- 设置中更改模型；亮暗主题持久化；系统托盘、关闭到托盘选项和快捷键。

## 提醒规则与配置

默认在截止前 **72小时、24小时、3小时** 各提醒一次；全天事项以23:59作为截止时刻。新建/编辑窗口会显示三个默认时刻，修改截止日期时自动更新。取消默认选项后可每行填写一个自定义本地时间，例如：

```text
2030-01-05 09:00
2030-01-06 18:30
```

多个提醒分别去重。错过多个默认时点时合并为一次补发，之后的时点继续提醒；原有自定义提醒和发送记录保留。修改截止时间或提醒计划时更新记录；只修改标题不重发。已完成或删除的任务不通知，重新打开后重新检查。错过计划提醒但尚未截止时补发；已经截止时合并为一条逾期通知。电脑关机时不能发送，登录后或恢复运行后的下一轮补查。

```powershell
# 源码配置
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\install_reminder.ps1

# 发行文件配置（也可在安装后的 GUI 设置中启用）
powershell.exe -NoProfile -ExecutionPolicy Bypass -File dist\DDLAssistant-1.1.0\install_reminder.ps1 -ExeDirectory E:\DDL-Assistant\dist\DDLAssistant-1.1.0

# 只检查，不发通知也不写提醒记录，结果见 reminder.log
powershell.exe -NoProfile -ExecutionPolicy Bypass -File dist\DDLAssistant-1.1.0\install_reminder.ps1 -Test

# 发送一条真实诊断通知（请先配置应用身份）
powershell.exe -NoProfile -ExecutionPolicy Bypass -File dist\DDLAssistant-1.1.0\install_reminder.ps1 -TestToast

# 仅移除当前用户的后台计划，不删除任务数据
powershell.exe -NoProfile -ExecutionPolicy Bypass -File dist\DDLAssistant-1.1.0\install_reminder.ps1 -Uninstall
```

任务名包含当前用户 SID，采用 **InteractiveToken / LeastPrivilege**；不使用 SYSTEM 或“无论用户是否登录都运行”发送桌面通知。XML 路径会转义，两个进程通过数据库写锁串行发送并用唯一索引去重。发送失败不记为已发送，下一轮重试；稳定通知 tag 减少异常重试产生的重复卡片。

Windows 接受通知不代表用户已看到：勿扰模式、锁屏、系统通知权限及进程异常退出仍可能影响显示。请在设置→系统→通知中允许 DDL Assistant，并手工使用 `-TestToast` 确认本机显示。本次测试范围见 [验收记录](docs/acceptance.md)。

## 今日计划使用方法

左侧点击「今日计划」，用日期控件选择要安排的一天（默认今天）。

1. **导入当日任务**：勾选该日截止的已有待办，确认后加入计划。重复导入不复制任务，也不修改截止时间。
2. **手动添加计划任务**：填写与普通任务相同的属性，新任务和计划引用一同保存。
3. **AI生成计划**：描述目标、可用时间或安排，AI建议多个任务、开始时间和预计小时数。可编辑预览中的日期、时间、重要程度、描述、工作量、提醒，并逐条选择；确认前不写数据库。
4. **安排开始时间**：选中任务后输入HH:MM，留空取消安排；计划开始时间与任务DDL独立。
5. **编辑/完成/重新打开**：与全部任务同步；「移出计划」只移除当日引用，保留任务及其他日期的计划。

计划通过独立数据表保存，升级到v4前自动快照，原有任务、提醒、时间戳不变。CSV/JSON导入导出仍以任务为单位，完整计划数据由SQLite备份保留。AI建议属于可编辑草稿，确认后才创建任务。

## Ollama

```powershell
ollama serve                       # 已有后台服务时无需重复启动
ollama pull qwen3.5:4b              # 仅首次安装模型时需要
ollama list
```

应用只连接 `http://localhost:11434`。模型可在「设置」中更改；图片识别需要支持视觉输入的模型。换成纯文本模型后不能识图。AI 调用中请等待完成或超时再关闭对话框，防止销毁运行中的线程；普通任务和后台提醒不依赖 Ollama。

可主动运行真实模型验收脚本（不下载模型，不写入任务）：

```powershell
.\.venv\Scripts\python.exe scripts\check_ollama.py
```

## 数据、日志和恢复

所有运行数据位于 `%LOCALAPPDATA%\DDLAssistant\`：

| 路径 | 用途 |
|---|---|
| `ddl_assistant.db` | 任务、提醒记录、schema版本 |
| `ddl_assistant.db-wal / -shm` | SQLite 运行时文件，运行中勿单独删除 |
| `settings.json` | 模型、主题、托盘选项；兼容旧 settings.txt |
| `backups\ddl_*.db` | 在线一致性备份，每份做完整性检查 |
| `backups\migration_*.db` | 升级前备份 |
| `logs\app.log / reminder.log` | 每个文件上限约2MB，保留3个轮转文件 |
| `logs\install.log` | 计划任务配置结果 |
| `screenshots` | 粘贴截图临时文件，正常关闭 AI 对话框时清理 |

恢复：先退出 GUI 并停用后台计划任务，保留当前数据库及 `-wal/-shm` 文件的副本，把选定备份复制成 `ddl_assistant.db`，移走旧的同名 WAL/SHM 后启动应用；确认数据后重新启用计划任务。不要在运行中直接覆盖数据库。

## 快捷键与操作

- `Ctrl+N` 新建，`Ctrl+Shift+A` AI 添加，`Ctrl+K` 搜索，Ctrl+反引号 隐藏到托盘。
- 双击任务编辑；右键完成、重新打开、删除。
- 数据菜单导入/导出/备份；AI 菜单查询与修改；设置菜单更改模型和关闭行为。
- Qt 6 默认启用高 DPI 支持。启动窗口适配当前可用屏幕；日历颜色在修改任务后刷新。

## 项目结构

```text
launcher.py / reminder.py      PyInstaller绝对导入入口
app/main.py                   GUI初始化、单实例及自检
app/db/                       模型、仓储、版本迁移
app/services/                 验证及事务
app/reminder/                 收集、独立运行、通知封装
app/ai/                       本地调用、Schema、提取、确认后操作
app/ui/                       主窗口、今日计划、任务、AI、查询、设置、日历
app/data_io.py                 导入导出和在线备份
app/windows_identity.py        通知快捷方式及应用身份
scripts/                      打包、用户安装、计划任务、真实AI检查
tests/                        自动化回归与Windows专项测试
docs/acceptance.md             差距核对及实际验收范围
```

## 故障排查

| 现象 | 检查方式 |
|---|---|
| EXE启动慢 | 单文件首次需解压 Qt；稍候并查看 app.log |
| 提示已运行 | 从通知区域打开，或退出原程序再启动；不要删除运行中的锁文件 |
| 找不到 Python 3.11 | 安装 x64 版本后重新执行 `py -3.11` |
| AI连接失败 | `ollama list`，确认服务已开、模型名正确；手动任务可继续使用 |
| AI图片失败 | 确认模型支持视觉，输入为PNG/JPG，查看对话框错误 |
| 退出后没有提醒 | 确认已配置计划任务且 EXE 未移动；查看 install.log |
| 计划任务配置失败 | 查看 install.log；受单位策略限制时请管理员允许当前用户任务计划 |
| 通知不出现 | 运行 `-TestToast`，检查勿扰模式、通知权限及开始菜单快捷方式 |
| 数据导入失败 | 对话框会指出错误行；确认日期格式和重要程度1–4，整批不会部分写入 |
| 升级后数据库版本过高 | 使用更新版程序，程序不会静默降级或覆盖数据 |
