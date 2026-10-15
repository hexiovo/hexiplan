#!/usr/bin/env python3
"""Render one approved structural UI from existing report JSON. No new UI generation."""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path
from render_report import prepare
from review_ui import attach_review, asset_manifest, VERSION as REVIEW_VERSION
from workflow import WorkflowError, report_content_hash
HOME=Path(__file__).resolve().parent.parent
LAYOUTS={'workbench':'分区工作台','document':'连续文档','wizard':'逐步向导','evidence':'截图审阅台'}
UI_VERSION='1.1.0'

def html_for(data:dict,layout:str,preview:bool=False)->str:
    if layout not in LAYOUTS:raise WorkflowError('Unknown layout: '+str(layout))
    shell=(HOME/'ui/layouts'/f'{layout}.html').read_text(encoding='utf-8')
    blob=json.dumps(data,ensure_ascii=False,allow_nan=False).replace('<','\\u003c').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
    banner=''
    if preview:
        banner='<div class="preview-banner no-print"><span>UI 结构样例 · 同一份演示内容，不是实际项目成果</span><span class="layout-badge">'+LAYOUTS[layout]+'</span><button id="copy-layout">复制此结构的选择文本</button></div>'
    # Assemble once: replacements must not interpret placeholder strings in user content.
    values={'/*STYLE*/':(HOME/'ui/assets/structure.css').read_text(encoding='utf-8'),
            '/*DATA*/':blob,'/*SCRIPT*/':(HOME/'tools/report_assets/report.js').read_text(encoding='utf-8'),
            '/*LAYOUT_SCRIPT*/':(HOME/'ui/assets/structure.js').read_text(encoding='utf-8'),
            '/*BANNER*/':banner}
    import re
    return attach_review(re.sub(r'/\*(?:STYLE|DATA|SCRIPT|LAYOUT_SCRIPT|BANNER)\*/',lambda m:values[m.group(0)],shell))

def render(data_file:Path,out:Path,layout:str,asset_root:Path|None=None,preview:bool=False)->dict:
    if out.exists():raise WorkflowError('Output exists. Submitted reports are immutable; use a NEW version directory.')
    if layout not in LAYOUTS:raise WorkflowError('Choose an explicit, user-confirmed layout.')
    data=json.loads(data_file.read_text(encoding='utf-8-sig'))
    if preview and not data.get('meta',{}).get('is_template'):raise WorkflowError('Preview must be explicitly marked is_template=true.')
    d=prepare(data,data_file.parent,asset_root or data_file.parent)
    ui_files=[HOME/'ui/layouts'/f'{layout}.html',HOME/'ui/assets/structure.css',HOME/'ui/assets/structure.js']
    presentation={'layout':layout,'palette':'pale-green','ui_version':UI_VERSION,
                  'assets':{p.relative_to(HOME).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in ui_files},
                  'preview':bool(preview),'feedback_ui_version':REVIEW_VERSION}
    presentation['assets'].update(asset_manifest())
    # Presentation version is included before the approval hash. Never mutate submitted HTML.
    d['presentation']=presentation;d['content_sha256']=report_content_hash(d)
    text=html_for(d,layout,preview)
    out.mkdir(parents=True)
    (out/'report.json').write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    (out/'report.html').write_text(text,encoding='utf-8')
    (out/'presentation.json').write_text(json.dumps(presentation,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return {'html':str((out/'report.html').resolve()),'data':str((out/'report.json').resolve()),'content_sha256':d['content_sha256'],'layout':layout,'live_tools_started':False}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--layout',choices=LAYOUTS,required=True);p.add_argument('--asset-root',type=Path);p.add_argument('--preview',action='store_true');a=p.parse_args()
    try:print(json.dumps(render(a.data,a.out,a.layout,a.asset_root,a.preview),ensure_ascii=False,indent=2));return 0
    except (OSError,ValueError,KeyError,TypeError) as e:print('HexiPlan UI:',e,file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())
