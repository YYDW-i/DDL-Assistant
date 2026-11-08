# DDL Assistant 差距修复与验收

日期：2026-11-08（Asia/Shanghai）。在原项目上增量修复，未覆盖用户数据库。

## 原项目差距及处理

| 原缺陷 | 本次处理 |
|---|---|
| 只有打包脚本，没有 EXE；包入口相对导入会失效 | 根目录绝对导入启动器，实际生成主程序及独立提醒 EXE，失败退出码检查及 ZIP、SHA256 |
| windows-toasts 调用了不存在的 ToastText1/2 | 使用真实 Toast(text_fields=...) 接口，并核对 Windows 通知历史确认系统存储 |
| 无应用身份/开始菜单快捷方式，脚本只支持源码 | 原生 COM 写 AUMID 快捷方式、当前用户注册信息；支持 EXE 安装与更新 |
| 任务计划 XML 路径错误，用户身份不明确 | SID 绑定的 InteractiveToken，登录与独立15分钟触发，路径转义及安装日志 |
| 没有自定义多个提醒；并发可能重复 | 编辑器支持多个本地时刻；独立去重；数据库锁串行发送；失败后重试 |
| 修改标题也清空通知；重复定义 delete 导致遗留 | 仅计划变化时重置；删除原子清理提醒记录 |
| “全部”看不到已完成；今日等搜索无效 | 全部含已完成，所有列表搜索生效；本周按自然周，逾期精确到时刻 |
| 迁移仅改版本号，没有实际迁移 | 添加列及数据库约束，升级前快照，未来版本拒绝，初始化跨进程互斥 |
| 只有导出；备份复制了错误路径且没有自动执行 | 事务导入与预览，按实际引擎在线备份、完整性检查及每日自动执行 |
| AI 未传 JSON Schema；日期在模块导入时固定 | 调用时生成日期，Pydantic Schema传入Ollama，真实模型验收 |
| AI 缺日期自动填今天，按钮写选中实际全写 | 日期缺失阻止提交，歧义显式勾选，逐条选择，整批原子写入 |
| 只有查询函数，无界面和确认执行 | AI 查询/建议对话框，字段前后预览、二次确认及过期快照拒绝 |
| Ctrl+V 未接截图事件，调用时关闭有线程风险 | 截图事件过滤、唯一临时文件、工作线程超时、运行时保护关闭 |
| 设置缺失、日历保留旧标记、工作量只能整数 | 设置界面、主题持久化、日历清理刷新、支持小数小时 |
| 日志无限增长，长期开启不备份 | 轮转日志和后台维护线程 |
| WinRT与Qt携带不同版本的C++运行库，旧库预载会导致Qt崩溃 | PyInstaller启动钩子预载Qt配套运行库；崩溃复现后加入回归测试；保留冻结版启动日志 |
| 打包器从外部Poppler PATH捕获同名ICU，缺少Qt依赖的Windows API | 固定spec排除外来icuuc.dll，使用Windows11系统库；EXE验收脚本检查归档中不存在错误库 |

## 验证范围

- 原始基线：27通过、1失败；备份端到端测试误用真实数据目录。
- 最终自动化：61项，涵盖CRUD、搜索、验证、导入原子性、在线备份完整性、v2迁移和未来版本拒绝、并发首次初始化、双进程提醒去重、延迟通知失败、极早日期、AI Schema/预览/歧义/逐条选择、修改快照、日历刷新、Windows原生快捷方式、XML转义和冻结运行库兼容。
- 真实 Ollama：本机已安装的 qwen3.5:4b；文字中两个任务（一个日期未定）、中文截图中两个带日期时间任务，以及针对指定ID的完成任务建议。输入与结构化结果位于 `.pytest-tmp/ollama-check/`；复查命令 `python scripts/check_ollama.py`。
- 计划任务定义：使用 Windows Schedule.Service 原生 TaskDefinition.XmlText 成功解析最终XML；此检查没有注册任务。交互式用户、15分钟间隔和特殊路径另有自动化测试。
- 原生快捷方式：实际调用 Windows COM，在隔离目录生成LNK并核查嵌入的 AUMID，未写真实开始菜单。
- EXE 冒烟：运行 `python scripts/check_executables.py`；主GUI显示、自检后退出，独立提醒加载WinRT库并执行dry-run，数据均隔离于 `.pytest-tmp/frozen-smoke/`。
- 打包脚本在生成ZIP前强制运行EXE启动验收；固定spec排除外来ICU及系统API兼容桩，SSL库使用与当前Python配套的版本。

## 验证边界

- 当前环境 Python 3.13.16 / Windows x64；没有安装3.11，因此本次EXE随带3.13运行时，源码3.11兼容性未实机验证。
- 没有替用户持久安装计划任务、修改真实开始菜单或发送真实任务通知。原生XML通过不等于已经实测重启/登录/休眠唤醒。请运行发行包 install.cmd 后用 `install_reminder.ps1 -TestToast` 验证本机通知显示。
- 自动化中的模型返回值和通知失败注入是合同/故障回归测试，未冒称它们替代真实 Ollama 验收或 Windows 可见通知验收。
- 系统通知历史确认只表示Windows已存储，无法证明用户已看见；勿扰模式、通知权限和关机影响由Windows决定。
- GUI缩放由Qt6支持；没有逐台测试不同DPI和所有屏幕。EXE无代码签名，首次运行可能出现SmartScreen发布者提示。

## 复查命令

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe scripts\check_ollama.py
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\build.ps1
.\.venv\Scripts\python.exe scripts\check_executables.py
```

接口核对依据：[Ollama结构化输出官方示例](https://github.com/ollama/ollama-python/blob/main/examples/structured-outputs.py)、[Windows-Toasts Toast接口](https://windows-toasts.readthedocs.io/en/latest/user/toast.html)、[Microsoft桌面通知应用身份说明](https://learn.microsoft.com/en-us/windows/win32/shell/enable-desktop-toast-with-appusermodelid)。
