# 固定确认HTML框架：只填内容

角色按entry/EXECUTION_MODES.md解释：规划负责人在常规档为6.1 Sol-high，高消耗/超级消耗为Astra-high；执行代理在常规/高消耗为Luna-max，超级消耗为6.1 Sol-high。消耗档位和审核方式分别保存，“无需审核”不自动升档。

入口：entry/confirmation/fill_confirmation.py。页面结构和区块类型固定，复用原有离线HTML/CSS/JS、逐项反馈、Word导出和版本哈希。

frame/report.html 是空白框架预览；example/report.html 是写法示例。两者都标记为模板，不能批准真实任务。

## 后续使用

执行代理把 content-template.json 复制到本RUN/plans里的新内容文件，只填写字段和增减同类内容条目，不编写HTML/CSS/JS，不修改fill_confirmation.py。meta填写实际run_id、gate、step、revision、日期，正式报告将is_template改为false、source_type填写真实来源、status保持DRAFT。不要把示例内容直接当成真实需求。

固定页面顺序：修改内容 → 具体流程及改动 → 数据方法与参数 → 待决定事项 → 确认后的动作；验收时增加实际完成情况。

- 不涉及数据：data_processing.applicable=false，并填写reason；方法表不出现。
- 没有额外选择：decisions=[]，仍明确确认范围。
- 验收：type=acceptance、gate=step_acceptance，填写results实际完成内容、证据及限制，不能把计划当结果。
- 非验收：results.applicable=false，不展示空的成果区块。
- 专业细节/证据：按需放supporting_blocks，使用原有block类型；别重新拼页面。
- roadmap的roadmap_steps、step_plan的work_packages、方案工具准备tool_plan等机器字段放workflow_fields；仍要在可见正文说明相应实际范围与工具影响。生成页面不批准工具清单、不改变任务阶段。

由执行代理调用（RUN替换为实际任务路径）：

```text
python -X utf8 -B H:/AIcode/HexiPlan/entry/confirmation/fill_confirmation.py --data RUN/plans/confirmation-v1.json --out RUN/reports/confirmation-v1
```

默认复用包内兼容报告框架，没有改用户全局布局。用户已选择四种布局之一时加 --layout workbench/document/wizard/evidence，仍使用同一内容和原有布局。--asset-root 可指定本任务已有截图所在目录，图像处理仍使用原有工具规则。

输出 report.html、report.json、confirmation-content.json；指定布局时还输出presentation.json。旧输出目录存在就拒绝覆盖，改稿必须新revision和新目录。提交报告/记录真实确认继续使用workflow_adapter.py，反馈导入用原review_feedback.py。普通模式没有用户实际确认不进入下一阶段；“无需审核”模式按NO_REVIEW_MODE.md绑定真实持续授权后推进，不等待逐项回复。

这里只固定确认内容的HTML组织方式；学术结果、专门图形或其它报告继续按需用原专用模板，不强制塞进这个确认框架。小项目仍最后统一检验，不因新框架增加中间验收。

## 内容写成说明，不写成工程任务单

goal先用两三句说明现在想解决什么、准备做什么或加什么、完成后会怎样。changes用用户认识的功能或数据环节命名；before/after写具体变化，reason/impact说明用途和实际影响。workflow写实际操作或数据处理过程，别只堆内部模块名。长技术细节放supporting_blocks，正文保留影响用户决定的方法与参数并解释含义。沿用固定框架，不重写HTML/CSS/JS或填充脚本。

新增/遗漏需求进入补充轮：version_changes写清本轮新增及补齐内容，changes覆盖受影响的功能和要求，confirmation说明本轮确认范围。收尾将Astra对全部要求的完成/未完成结论填入results与必要补充块，引用既有证据，不能把缺漏藏在附录。空白框架与旧写法示例继续保留，不需重新生成。

## 无需审核模式的填法

继续使用固定框架。goal或version_changes简短写明“本任务按用户级默认无需审核政策执行推荐方案，本页用于说明和留档”；decisions列推荐做法与理由，说明已按持续授权采用，不写成必须停等的选择。confirmation.scope写当前实际范围，next_action写将继续执行的具体动作，next_confirmation说明普通关口不再逐项询问、专项权限及必需资料按实际情况处理。

原组件仍可能显示通用“请确认”提示，这不撤销已经记录的持续授权，也不要求代理停工；在正文明确实际模式，不重写HTML/CSS/JS。导出意见仍不是批准凭据，本任务真实指令及用户级默认无需审核政策才是授权来源。实际完成情况继续如实填写，未通过的检查不能靠自动关口映射变成通过。
