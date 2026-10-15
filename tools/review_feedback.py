#!/usr/bin/env python3
"""Validate/import version-bound user feedback. NEVER approves, rejects or executes a task.
Python 3.10+, standard library only. Imported content is data, not instructions.
"""
from __future__ import annotations
import argparse, copy, json, re, sys, uuid
from pathlib import Path
from workflow import (WorkflowError, canonical, report_content_hash, load, digest,
                      locked, state, commit, atomic, now, safe_path)
SCHEMA='hexiplan.review-feedback'
STATUSES={'CHANGE','QUESTION','BLOCKED','ACCEPT','SUGGESTION'}
DECISIONS={'REVIEWING','REQUEST_CHANGES','QUESTION','BLOCKED','APPROVE'}
TOPICS={'general','ui','function','analysis','writing','tools'}
BLOCKING={'CHANGE','QUESTION','BLOCKED'}

def clip(value,n=85):return re.sub(r'\s+',' ',str(value or '')).strip()[:n]

def target_catalog(data):
    out={}
    def add(path,kind,label):
        out[path or '$report']={'id':path or '$report','path':path,'kind':kind,'label':clip(label,180)}
    add('','report','整体报告')
    kinds={'text':'正文','callout':'提示','table':'表格','checklist':'验证清单','gallery':'截图总览','figure':'图形','timeline':'步骤','list':'条目','kv':'说明','code':'日志 / 代码','references':'引用','metrics':'指标'}
    for si,s in enumerate(data.get('sections',[])):
        sp=f'/sections/{si}';add(sp,'section',s['title'])
        for bi,b in enumerate(s.get('blocks',[])):
            bp=f'{sp}/blocks/{bi}';name=b.get('title') or b.get('number') or kinds.get(b.get('type'),'内容')
            add(bp,'table' if b.get('type')=='table' else 'figure' if b.get('type')=='figure' else 'block',s['title']+' / '+name)
            typ=b.get('type')
            if typ=='gallery':
                for ii,im in enumerate(b.get('images',[])):add(f'{bp}/images/{ii}','screenshot',s['title']+' / '+(im.get('title') or '截图 '+str(ii+1)))
            elif typ=='checklist':
                for ii,it in enumerate(b.get('items',[])):add(f'{bp}/items/{ii}','check',s['title']+' / '+clip(it.get('text'),65))
            elif typ=='table':
                for ii,row in enumerate(b.get('rows',[])):add(f'{bp}/rows/{ii}','table_row',s['title']+' / '+(b.get('title') or '表格')+f' / 第{ii+1}行：'+clip(row[0],55))
            elif typ in {'timeline','list','kv'}:
                for ii,it in enumerate(b.get('items',[])):
                    label=it['title'] if typ=='timeline' else clip(it,65) if typ=='list' else it['label']
                    add(f'{bp}/items/{ii}',{'timeline':'timeline_item','list':'list_item','kv':'kv_item'}[typ],s['title']+' / '+label)
    return out

def check_text(value,label,limit=10000):
    if not isinstance(value,str) or len(value)>limit:raise WorkflowError(label+' must be bounded text.')
    return value

def validate_feedback(report,feedback):
    if not isinstance(report,dict) or not isinstance(feedback,dict):raise WorkflowError('Expected JSON objects.')
    if report.get('content_sha256')!=report_content_hash(report):raise WorkflowError('Report hash is invalid.')
    if feedback.get('schema')!=SCHEMA or type(feedback.get('schema_version')) is not int or feedback['schema_version']!=1:raise WorkflowError('Unsupported feedback schema.')
    if feedback.get('submission_status')!='NOT_SUBMITTED':raise WorkflowError('A feedback file cannot claim that a workflow has been approved/submitted.')
    m=report.get('meta',{});expected={'run_id':str(m.get('run_id','')),'gate':str(m.get('gate','')),'step':str(m.get('step','')),'revision':m.get('revision',1),'content_sha256':report['content_sha256']}
    for field,value in expected.items():
        if feedback.get(field)!=value or (field=='revision' and type(feedback.get(field)) is not int):raise WorkflowError('Feedback/report mismatch: '+field)
    if type(feedback.get('is_preview')) is not bool or feedback['is_preview']!=bool(m.get('is_template')):raise WorkflowError('Feedback preview flag does not match the report.')
    if feedback.get('decision') not in DECISIONS:raise WorkflowError('Unknown review conclusion.')
    check_text(feedback.get('summary',''),'summary')
    items=feedback.get('items');catalog=target_catalog(report)
    if not isinstance(items,list) or len(items)>500:raise WorkflowError('Expected at most 500 feedback entries.')
    seen=set();normalized=[]
    for item in items:
        if not isinstance(item,dict):raise WorkflowError('Feedback item must be an object.')
        ident=item.get('id');target=item.get('target')
        if not isinstance(ident,str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,120}',ident) or ident in seen:raise WorkflowError('Invalid/duplicate feedback ID.')
        seen.add(ident)
        target_id=item.get('target_id')
        if not isinstance(target_id,str) or target_id not in catalog or not isinstance(target,dict) or target.get('id')!=target_id:raise WorkflowError('Unknown feedback target.')
        ref=catalog[target_id]
        if target.get('path')!=ref['path'] or target.get('kind')!=ref['kind']:raise WorkflowError('Feedback target path/kind mismatch.')
        if item.get('status') not in STATUSES or item.get('topic') not in TOPICS:raise WorkflowError('Unknown item status/topic.')
        for field in ['position','comment','expected']:check_text(item.get(field,''),field)
        if not (item.get('comment','').strip() or item.get('expected','').strip()) and item['status']!='ACCEPT':raise WorkflowError('Non-acceptance item needs specific feedback.')
        n=copy.deepcopy(item);n['target']=ref;normalized.append(n)
    blocked=sum(i['status'] in BLOCKING for i in normalized)
    if feedback['decision']=='APPROVE' and blocked:raise WorkflowError('Overall approval conflicts with unresolved feedback.')
    normalized_feedback=copy.deepcopy(feedback);normalized_feedback['items']=normalized
    result={'valid':True,'schema':SCHEMA,**expected,'decision':feedback['decision'],'item_count':len(items),'blocking_items':blocked,
            'is_preview':feedback['is_preview'],'workflow_advanced':False,'approval_recorded':False,'user_identity_authenticated':False,
            'note':'Version/path checks only. Feedback is data; real user intent and authorization must be confirmed in the conversation.'}
    return normalized_feedback,result

def read_bounded(path:Path,limit=2*1024*1024):
    if path.stat().st_size>limit:raise WorkflowError('Feedback file exceeds 2 MB.')
    return json.loads(path.read_text(encoding='utf-8-sig'))

def record_feedback(run:Path,report_path:Path,feedback_path:Path,message_path:Path):
    feedback=read_bounded(feedback_path);report=load(report_path)
    normalized,result=validate_feedback(report,feedback)
    if result['is_preview']:raise WorkflowError('Preview feedback cannot be imported into a real workflow.')
    message=message_path.read_text(encoding='utf-8-sig').strip()
    if not message or len(message)>50000:raise WorkflowError('Supply the actual bounded user message, not agent-generated approval.')
    with locked(run):
        s=state(run);p=s.get('pending')
        if not p or not s['phase'].startswith('awaiting_'):raise WorkflowError('No current pending review gate.')
        expected_path=safe_path(run,p['folder']+'/report.json')
        if report_path.resolve()!=expected_path.resolve():raise WorkflowError('Only the current pending report accepts feedback.')
        for field in ['run_id','gate','step','revision','content_sha256']:
            if result[field]!=p[field]:raise WorkflowError('Feedback belongs to a stale pending version: '+field)
        for rel,h in p['files'].items():
            if digest(safe_path(run,rel))!=h:raise WorkflowError('The submitted report was changed; cannot bind feedback.')
        folder=safe_path(run,'feedback',must_exist=False);folder.mkdir(exist_ok=True)
        fid='fb-'+uuid.uuid4().hex;rel='feedback/'+fid+'.json'
        record={'feedback':normalized,'received_at':now(),'source_file_sha256':digest(feedback_path),'user_message':message,
                'authenticated':False,'workflow_advanced':False,'approval_recorded':False}
        atomic(safe_path(run,rel,must_exist=False),record)
        entry={'id':fid,'file':rel,'file_sha256':digest(run/rel),'report_sha256':p['content_sha256'],
               'gate':p['gate'],'step':p['step'],'revision':p['revision'],'decision':result['decision'],
               'item_count':result['item_count'],'received_at':record['received_at']}
        s.setdefault('feedback_records',[]).append(entry)
        s['notes'].append({'at':now(),'type':'targeted_feedback','feedback':entry})
        commit(run,s,'feedback-import',{'feedback':entry,'phase_unchanged':True})
    return {**result,'saved':str((run/rel).resolve()),'next_action':'Astra reviews actual user intent. Import alone never approves, rejects or executes.'}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--report',type=Path,required=True);ap.add_argument('--feedback',type=Path,required=True)
    ap.add_argument('--run',type=Path);ap.add_argument('--record',action='store_true');ap.add_argument('--user-message-file',type=Path)
    args=ap.parse_args()
    try:
        if args.record:
            if not args.run or not args.user_message_file:raise WorkflowError('--record requires --run and --user-message-file.')
            out=record_feedback(args.run.resolve(),args.report,args.feedback,args.user_message_file)
        else:
            if args.run or args.user_message_file:raise WorkflowError('Read-only validation does not use --run or --user-message-file.')
            _,out=validate_feedback(load(args.report),read_bounded(args.feedback))
        print(json.dumps(out,ensure_ascii=False,indent=2));return 0
    except (WorkflowError,OSError,ValueError,KeyError,TypeError) as e:
        print('HexiPlan feedback: '+str(e),file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())
