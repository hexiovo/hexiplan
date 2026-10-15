# GitHub 静态发布说明

本仓库包含 HexiPlan 5.1 原始工具、角色、模块、模板、离线页面、第三方许可资料，以及截至对话适配 v1.11 的新增入口与规则。当前对话入口和分工规则以 `entry/CONVERSATION_ENTRY.md`、`entry/EXECUTION_MODES.md`、`entry/NO_REVIEW_MODE.md` 为准；原 README、角色文件和启动器说明保留为原包资料。

默认常规档：Astra-high 开始/收尾，6.1 Sol-high 规划，Luna-max 优先执行。明确指定高消耗档时全部规划交 Astra-high；超级消耗档全部规划交 Astra-high、全部执行交 6.1 Sol-high。显式启用 HexiPlan 后默认无需审核；最多三轮修复，第三轮仍失败则说明阻塞；鼠标接管仍须先申请。

当前状态命令使用 `entry/workflow_adapter.py`，原 `tools/workflow.py` 保留。HTML 使用既有框架，后续只填内容。仓库内 `entry/confirmation/frame` 和 `example` 都是模板预览，不是真实任务报告。

## 不包含运行数据

本仓库没有复制本机任务目录、部署报告、会话记录、全局 AGENTS 备份、工具批准记录、认证、缓存、日志、浏览器档案、下载的运行时或临时文件。`.gitignore` 同时排除后续生成的同类文件。

克隆代码不会自动登记用户级入口或迁移认证。现有入口文档使用原部署路径 `H:/AIcode/HexiPlan`；其它机器应根据实际位置和客户端能力安排入口登记，不能把原机器的授权或历史验证当成新的实测结果。

## 校验清单

`CHECKSUMS.sha256` 是原包清单，保持原样。本次静态发布刻意省略以下原包运行目录占位与可变批准文件，因此直接用原全包校验器会报告这些缺失项；不能据此宣称静态发布已通过原全包安装自检：

- `extensions/approved-tools.json`
- `extensions/cache/.keep`
- `extensions/logs/.keep`
- `extensions/profiles/.keep`
- `extensions/runtimes/.keep`
- `runs/.keep`

`PUBLISH_FILES.sha256` 单独记录本次静态发布文件的 SHA-256（不包含自身），没有替换原包清单。本次只核查上传文件范围和敏感信息，没有重复运行模型、浏览器或部署功能测试。默认无需审核完整业务链路仍以入口文档中的验证状态为准。
