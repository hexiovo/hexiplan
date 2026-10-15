#!/usr/bin/env python3
"""Fill a reusable HexiPlan HTML frame from JSON; no external dependencies."""
from __future__ import annotations
import argparse,base64,copy,hashlib,json,mimetypes,os,sys
from pathlib import Path
from workflow import canonical,report_content_hash,WorkflowError
from review_ui import attach_review
ASSETS=Path(__file__).resolve().parent/'report_assets'
TYPES={'requirements','solution','roadmap','step_plan','acceptance','research','academic','ui_review','status','guide','change','delivery','catalog'}
BLOCKS={'text','callout','kv','table','metrics','timeline','list','checklist','gallery','figure','code','links','references'}

def prepare(data:dict,base:Path,asset_root:Path)->dict:
    d=copy.deepcopy(data)
    if not isinstance(d,dict) or d.get('type') not in TYPES: raise WorkflowError('Unknown report type.')
    if not isinstance(d.get('sections'),list) or not d.get('title'): raise WorkflowError('A title and section list are required.')
    if not isinstance(d.get('meta'),dict): raise WorkflowError('meta must be an object.')
    def image(im):
        if im.get('src'):
            p=Path(im.pop('src'))
            p=(base/p).resolve() if not p.is_absolute() else p.resolve()
            if not p.is_relative_to(asset_root.resolve()): raise WorkflowError('Image escapes asset root: '+str(p))
            raw=p.read_bytes()
            if len(raw)>15*1024*1024: raise WorkflowError('Image exceeds 15 MB; resize a display copy, keep the original evidence separately.')
            mime='image/png' if raw.startswith(b'\x89PNG\r\n\x1a\n') else 'image/jpeg' if raw.startswith(b'\xff\xd8') else None
            if not mime: raise WorkflowError('Use a PNG or JPEG image, not renamed SVG/HTML.')
            im['data_uri']='data:'+mime+';base64,'+base64.b64encode(raw).decode('ascii')
            im['source_name']=p.name;im['source_sha256']=hashlib.sha256(raw).hexdigest()
        if im.get('data_uri'):
            prefix,encoded=im['data_uri'].split(',',1)
            if prefix not in {'data:image/png;base64','data:image/jpeg;base64'}: raise WorkflowError('Unsafe image data URI.')
            raw=base64.b64decode(encoded,validate=True)
            if len(raw)>15*1024*1024: raise WorkflowError('Image exceeds 15 MB.')
            expected=b'\x89PNG\r\n\x1a\n' if 'png' in prefix else b'\xff\xd8'
            if not raw.startswith(expected): raise WorkflowError('Image header does not match its MIME type.')
    for s in d['sections']:
        if not s.get('title') or not isinstance(s.get('blocks'),list): raise WorkflowError('Each section needs title and blocks.')
        for b in s['blocks']:
            if b.get('type') not in BLOCKS: raise WorkflowError('Unknown block type: '+str(b.get('type')))
            if b['type']=='table':
                n=len(b.get('columns',[]))
                if not n or any(len(r)!=n for r in b.get('rows',[])): raise WorkflowError('Table row width does not match columns.')
            if b['type']=='figure':image(b)
            if b['type']=='gallery':
                for im in b.get('images',[]):image(im)
    d['content_sha256']=report_content_hash(d)
    return d

def html_for(data:dict)->str:
    shell=(ASSETS/'shell.html').read_text(encoding='utf-8')
    encoded=json.dumps(data,ensure_ascii=False,allow_nan=False).replace('<','\\u003c').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
    # Replace placeholders in the shell only, never in user-provided content.
    import re
    pieces={'/*STYLE*/':(ASSETS/'report.css').read_text(encoding='utf-8'),'/*DATA*/':encoded,'/*SCRIPT*/':(ASSETS/'report.js').read_text(encoding='utf-8')}
    return attach_review(re.sub(r'/\*(?:STYLE|DATA|SCRIPT)\*/',lambda m:pieces[m.group(0)],shell))

def render(data_file:Path,out:Path,asset_root:Path|None=None):
    if out.exists():raise WorkflowError('Output already exists. Use a NEW version directory; submitted reports are immutable.')
    data=json.loads(data_file.read_text(encoding='utf-8-sig'))
    d=prepare(data,data_file.parent,asset_root or data_file.parent)
    text=html_for(d)
    out.mkdir(parents=True)
    (out/'report.json').write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    (out/'report.html').write_text(text,encoding='utf-8')
    return {'html':str((out/'report.html').resolve()),'data':str((out/'report.json').resolve()),'content_sha256':d['content_sha256']}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--asset-root',type=Path)
    a=p.parse_args()
    try:print(json.dumps(render(a.data,a.out,a.asset_root),ensure_ascii=False,indent=2));return 0
    except (OSError,ValueError,KeyError,TypeError) as e:print('HexiPlan render: '+str(e),file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())
