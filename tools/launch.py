#!/usr/bin/env python3
"""Explicit, portable Codex launcher. No global/project config writes or installation."""
from __future__ import annotations
import argparse,json,os,re,shutil,subprocess,sys,time,uuid
from pathlib import Path
from workflow import init_run,state,summary,identifier,WorkflowError
HOME=Path(__file__).resolve().parent.parent

def field(text,key):
    found=re.findall(r'^\s*'+re.escape(key)+r'\s*=\s*"([^"\n]+)"\s*$',text,re.M)
    if len(found)!=1:raise WorkflowError('Invalid simple TOML field: '+key)
    return found[0]

def codex_command(explicit=None):
    resolved=shutil.which(explicit or 'codex')
    if not resolved and explicit and Path(explicit).is_file():resolved=str(Path(explicit).resolve())
    if not resolved:raise WorkflowError('Codex CLI was not found. Use a terminal where codex works, or --codex-path. Nothing will be installed.')
    p=Path(resolved)
    if os.name=='nt' and p.suffix.lower() in {'.cmd','.bat','.ps1'}:
        entry=p.parent/'node_modules/@openai/codex/bin/codex.js'
        node=shutil.which('node')
        if entry.is_file() and node:return [node,str(entry)]
        raise WorkflowError('Nonstandard Windows Codex shim: pass --codex-path pointing to a real codex.exe. No shell quoting workaround or installation is attempted.')
    return [str(p)]

def role_settings():
    roles=[]
    for f in sorted((HOME/'agents').glob('*.toml')):
        t=f.read_text(encoding='utf-8-sig')
        roles.append({'name':field(t,'name'),'model':field(t,'model'),'effort':field(t,'model_reasoning_effort'),'description':field(t,'description'),'path':str(f.resolve())})
    return roles

def arguments(project:Path,run:Path,roles):
    # All settings below apply to this invocation. Never call `features enable`.
    args=['--cd',str(project),'--model','gpt-6-astra','--sandbox','workspace-write','--ask-for-approval','on-request',
          '--add-dir',str(run),'--add-dir',str(HOME/'extensions'),'-c','model_reasoning_effort="high"','-c','agents.enabled=true',
          '-c','agents.max_concurrent_threads_per_session=9']
    for r in roles:
        args+=['-c',f'agents.{r["name"]}.config_file='+json.dumps(r['path'].replace('\\','/'),ensure_ascii=False)]
        args+=['-c',f'agents.{r["name"]}.description='+json.dumps(r['description'],ensure_ascii=False)]
    return args

def bootstrap(run,project,task,resuming):
    status=summary(state(run)) if resuming else {'run_id':run.name,'phase':'requirements','task':task}
    # Bootstrap only; delegate filesystem reads when the root has no direct read tool.
    return f'''用户明确为本任务启用 HexiPlan 5.1。你必须实际使用 gpt-6-astra / high；先核对运行时模型。
HOME={HOME}
PROJECT={project}
RUN={run}
当前摘要={json.dumps(status,ensure_ascii=False)}
用户任务={task or '尚未提供完整业务任务。请先等待用户输入，不扫描或修改业务项目。'}
新增规则：HOME/extensions/TOOL_POLICY.md 已获原则确认；具体工具须在G2工具清单批准后才可下载、隔离安装与按需启用。优先现有脚本/CLI，不自动装全部MCP；两个浏览器独立资料，固定版本，管理缓存预算，敏感外部操作另行确认。HOME/extensions 只写已批准工具产物，不改全局配置。
UI选择：HOME/UI_OPTIONS.html 提供四种结构，全部淡绿色，不是换色。只在用户选定后给正式报告调用 tools/render_layout.py --layout <workbench|document|wizard|evidence>，无需重写HTML。未选定时提交结构预览，不能替用户确认。报告先展示本次变化，再按需展开日志；内容与展示版本一并记录。
模块入口：HOME/modules/MODULE_ROUTER.md。你只读小索引并指定module_ids，下层按需读取；普通任务不隐式启用。报告Sol一次润色后运行guard_report.py，再使用已有模板和新版本哈希，不新增润色代理。第三方规则是本地适配版，无需联网安装。
你只负责需求理解/提问、规划、向用户请求确认和代理派工，不运行shell、不写文件、不实现、不测试、不截图。
立即通过直接文件读取工具读取 HOME/hexiplan.md 与 agents/astra.toml；如果当前没有直接文件读取工具，指派 hexiplan_sol_reporter 只读取并准确转述这两份规则，不由你运行cat/shell。随后让同一Sol记录代理按需读取 RUN/state.json 及最新journal，报告恢复情况。
规则摘要（不能省略正式协议）：需求理解可充分提问；需求HTML需用户确认；正式方案HTML需单独确认；整体步骤HTML需确认；Astra对当前步骤做中等粒度拆分并以HTML获批；多个Sol-high细化，Luna-max执行，重要任务可Sol-high执行；组内只局部把关；全部分组完成后由新的独立Sol-high整合校验；最多两轮定向修复，未解决即阻塞；另一个Sol生成验收HTML；清理登记临时文件；用户验收本步后才规划下一步，并再次确认。
全任务Sol总量3（包含管理/研究/校验/报告/重要执行/记录），Luna总量6，浏览器会话2，高内存任务1；不机械开满。默认主线程转发Sol的权威细节任务，Astra不代替细化或实现。所有代理必须登记/释放资源。
开始前尽早由下层检查必要浏览器及权限，优先独立自动化，不控制用户桌面。学术任务充分阅读原始文献、提供方法备选。允许制作标记明确的合成验证数据文件及必要公开下载，不改真实参数来通过测试。UI/分析方法由用户确认。
所有HTML用 HOME/templates/json 和 tools/render_report.py 复用框架，不重写CSS/JS；状态、审批、报告和证据只写RUN，业务文件只在当前步骤获批后按范围修改PROJECT。不能把阅读文档/下载/静态预览/按钮模拟点击当作用户批准。
{'这是恢复请求。不得把重开会话当作新批准；检查实际项目状态、遗留进程和占用，不重做已完成步骤。' if resuming else '这是新任务，停在需求理解阶段，后续每关等待用户确认。'}
不要更改既有Codex配置、AGENTS、Skills、PATH、全局环境或本工具包；不要静默换模型；不要在工具中另启交互式Codex。权限/工具不满足时准确报告。
'''

def choose_run():
    dirs=[]
    for p in (HOME/'runs').iterdir():
        if p.is_dir() and (p/'journal').is_dir():
            try:
                s=state(p)
                if s['phase']!='complete':dirs.append((p,s))
            except Exception:pass
    dirs.sort(key=lambda x:x[1]['updated_at'],reverse=True)
    if not dirs:return None
    print('\n0. 新建任务')
    for i,(p,s) in enumerate(dirs[:10],1):print(f'{i}. 继续 {p.name}  [{s["phase"]}]  {s["project"]}')
    choice=input('选择编号（回车新建）：').strip()
    if not choice or choice=='0':return None
    if not choice.isdigit() or not 1<=int(choice)<=min(10,len(dirs)):raise WorkflowError('Invalid selection.')
    return dirs[int(choice)-1][0]

def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--project',type=Path);ap.add_argument('--task',default='');ap.add_argument('--task-file',type=Path)
    ap.add_argument('--run-id');ap.add_argument('--resume',action='store_true');ap.add_argument('--check-only',action='store_true');ap.add_argument('--codex-path')
    a=ap.parse_args(argv)
    try:
        if sys.version_info<(3,10):raise WorkflowError('Python 3.10+ is required. No environment changes will be made.')
        run=None;resuming=a.resume or bool(a.run_id)
        if a.run_id:run=HOME/'runs'/identifier(a.run_id)
        elif a.resume or (not a.project and not a.check_only):run=choose_run();resuming=run is not None
        if run:
            s=state(run);project=Path(s['project'])
            if a.project and a.project.resolve()!=project.resolve():raise WorkflowError('Project differs from the saved run; do not silently redirect resumed edits.')
        else:
            project=a.project or Path(input('实际项目目录（不是HexiPlan目录）：').strip().strip('"'))
            run=HOME/'runs'/(time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6])
        project=project.expanduser().resolve()
        if not project.is_dir():raise WorkflowError('Project directory does not exist.')
        if project==HOME or project.is_relative_to(HOME):raise WorkflowError('Choose the real business project, not the HexiPlan toolkit or its runs.')
        task=a.task_file.read_text(encoding='utf-8-sig') if a.task_file else a.task
        roles=role_settings();cmd=codex_command(a.codex_path);args=arguments(project,run,roles)
        print('\nHexiPlan 5.1 / 仅本次会话启用')
        print('工具包：',HOME,'\n项目：',project,'\n记录：',run)
        print('Astra high | Sol high ×≤3 | Luna max ×≤6 | Browser≤2 | High-memory≤1')
        print('本次会话申请 PROJECT + RUN + HOME/extensions 的写权限；实际业务与工具安装仍须对应清单批准。')
        print('不安装、不改现有配置/默认模型、不使用yolo。')
        if a.check_only:
            try:
                v=subprocess.run(cmd+['--version'],capture_output=True,text=True,timeout=15)
                print('Codex version:',v.stdout.strip() or v.stderr.strip())
            except (OSError,subprocess.TimeoutExpired) as e:print('Version check not completed:',e)
            print(json.dumps({'command':cmd,'arguments':args,'roles':roles,'live_models_verified':False},ensure_ascii=False,indent=2))
            print('CHECK ONLY：未创建任务、未启动模型。真实权限与模型调用仍待实机预检。');return 0
        if not resuming:init_run(run,project,task)
        prompt=bootstrap(run,project,task,resuming)
        result=subprocess.run(cmd+args+[prompt],cwd=project)
        if result.returncode:print('Codex退出码：',result.returncode,'；未尝试换模型或改配置。')
        return result.returncode
    except (WorkflowError,OSError,ValueError,EOFError,KeyboardInterrupt) as e:
        print('HexiPlan:',e,file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())
