# HexiPlan 5.1 · 针对性填写与导出意见

先打开 `REVIEW_DEMO.html` 试用新表单。四种UI结构都使用同一个反馈组件。

在章节、截图或检查项旁点击“提意见”，选择对象和意见类型，填写具体内容与期望调整，保存后导出JSON、Markdown、TXT或Word。把意见JSON交回Codex；导出/导入不会自动批准下一关。详见 `docs/针对性反馈.md`。

部署使用新空目录，提示词是 `prompts/INSTALL_CODEX.txt`。仍双击 `start-hexiplan.cmd` 新建/继续；意见回传提示词是 `prompts/RETURN_FEEDBACK.txt`。

下面保留原有功能说明；历史版本验证不是本机模型或Word联调。

---

# HexiPlan 5.0 独立版

先打开 **UI_OPTIONS.html**：四种结构化报告界面，统一淡绿色。工作台、连续文档、逐步向导、截图审阅台不是换色；选择在本任务确认后生效。

部署只使用新的空目录，具体方法见 prompts/INSTALL_CODEX.txt。之后双击 start-hexiplan.cmd，新建或继续任务。

用户已同意工具策略，但未批准任何具体MCP。部署本包离线；按 extensions/TOOL_POLICY.md 在任务正式方案中确认具体工具后，才允许在独立目录准备与使用。

V4模块、12套内容模板、Word导出与原有逐关状态保留。新结构调用 tools/render_layout.py，历史渲染器保留。详见 docs/5.0更新说明.md、docs/工具准备与预算.md。

---

# HexiPlan 5.0 · 独立目录、显式启用版

打开 **START_HERE.html** 查看原有12套模板和入口；打开 **MODULES.html** 查看新增规则、角色位置及用法。

部署：将 prompts/INSTALL_CODEX.txt 中两个路径替换后交给 Codex。必须使用新的空目录，保留旧版及旧任务，不覆盖、不注册全局 Skill、不改默认模型或现有项目配置。

后续：双击 start-hexiplan.cmd，选择新建/继续，指定实际项目目录，再输入需求。原有确认关口和3/6/2/1并发、两轮修复边界保持不变。Astra-high只理解、规划、确认与分发。

新增：中文 Humanizer-zh 适配版、英文 Humanizer 备用、5个科研模块、业务UI设计和系统化调试，另有科学含义/报告保护规则与路由索引。它们在 modules/，只由相应下层按需读取，不安装上游工具链，也不保证通过AI检测器。

报告 Sol 在渲染前一次润色，guard_report.py保护结构/数字等；语义仍需对照。原有HTML/CSS/JS、DOCX导出和截图总览功能不改。模块来源、许可和适配说明位于 third_party/。详细见 docs/使用说明.md 和 docs/模块与省上下文.md。

部署自检：已有Python 3.10+执行 `python -B tools/verify_package.py`。不联网、不调用模型。真实Codex账户/Windows环境仍需运行时预检。
