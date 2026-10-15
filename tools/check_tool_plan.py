#!/usr/bin/env python3
"""Offline tool-plan validation and approval matching. Never downloads or executes tools."""
from __future__ import annotations
import argparse, hashlib, json, re, sys
from pathlib import Path
from urllib.parse import urlsplit
import workflow as w
from route_modules import checked_run

KINDS={'cli','stdio_mcp','http_mcp'}
REQUIRED=('id','kind','source_url','version','license','purpose','allowed_domains','read_dirs','write_dirs','data_sent','credentials','cost','rollback','telemetry','external_writes')
PLACEHOLDER=re.compile(r'REPLACE_|OFFICIAL_SOURCE|待填写|<替换',re.I)

def validate(plan:dict)->dict:
    if not isinstance(plan,dict) or plan.get('schema_version')!=1:raise w.WorkflowError('Unsupported tool plan schema.')
    w.identifier(plan.get('plan_id',''))
    tools=plan.get('tools')
    if not isinstance(tools,list):raise w.WorkflowError('tools must be a list.')
    budget=plan.get('budget',{})
    for key in ('download_mb','cache_mb','paid_cost'):
        n=budget.get(key)
        if not isinstance(n,(int,float)) or isinstance(n,bool) or n<0:raise w.WorkflowError('A concrete nonnegative budget is required: '+key)
    seen=set();downloads=0;caches=0
    for t in tools:
        if not isinstance(t,dict):raise w.WorkflowError('Every tool must be an object.')
        for k in REQUIRED:
            if k not in t or t[k] in (None,''):raise w.WorkflowError('Missing tool field: '+k)
        ident=w.identifier(t['id'])
        if ident in seen:raise w.WorkflowError('Duplicate tool id.')
        seen.add(ident)
        if t['kind'] not in KINDS:raise w.WorkflowError('Unknown tool kind.')
        if PLACEHOLDER.search(json.dumps(t,ensure_ascii=False)):raise w.WorkflowError('Replace every example placeholder before proposing a tool.')
        ver=t['version']
        if not isinstance(ver,str) or re.search(r'\blatest\b|\*|^[~^><]',ver,re.I):raise w.WorkflowError('Pin an explicit version, commit, or hosted-service observation; never latest/range.')
        u=urlsplit(t['source_url'])
        if u.scheme!='https' or not u.netloc or u.username or u.password:raise w.WorkflowError('Use a credential-free HTTPS source.')
        for k in ('allowed_domains','read_dirs','write_dirs','data_sent'):
            if not isinstance(t[k],list) or any(not isinstance(x,str) or not x.strip() for x in t[k]):raise w.WorkflowError(k+' must list explicit nonempty strings.')
        if any('*' in x for x in t['allowed_domains']):raise w.WorkflowError('List exact allowed domains, not wildcards.')
        for k in ('estimated_download_mb','estimated_cache_mb'):
            n=t.get(k)
            if not isinstance(n,(int,float)) or isinstance(n,bool) or n<0:raise w.WorkflowError('Measured/estimated size is required; mark it as an estimate in the plan: '+k)
        downloads+=t['estimated_download_mb'];caches+=t['estimated_cache_mb']
        if t['kind'] in {'cli','stdio_mcp'}:
            for k in ('install_argv','start_argv'):
                if not isinstance(t.get(k),list) or not t[k] or any(not isinstance(a,str) or '\0' in a for a in t[k]):raise w.WorkflowError('Record exact argv (data only), not implicit install steps: '+k)
        else:
            endpoint=urlsplit(t.get('endpoint_url',''))
            if endpoint.scheme!='https' or not endpoint.netloc or endpoint.username or endpoint.password:raise w.WorkflowError('Remote MCP needs a credential-free HTTPS endpoint.')
    if downloads>budget['download_mb'] or caches>budget['cache_mb']:raise w.WorkflowError('Per-tool estimates exceed the declared budget.')
    return {'plan_sha256':hashlib.sha256(w.canonical(plan)).hexdigest(),'tool_count':len(tools),'estimated_download_mb':downloads,'estimated_cache_mb':caches,'structure_check':'PASS','commands_executed':False,'network_used':False,'security_verified':False,'runtime_permissions_verified':False}

def match_approval(run:Path,plan:dict)->dict:
    result=validate(plan);run=checked_run(run)
    # This only compares user-confirmed files already in the gate journal.
    with w.locked(run):
        s=w.state(run)
        for a in reversed(s.get('approvals',[])):
            if a.get('gate')!='solution':continue
            folder=w.safe_path(run,a['folder'])
            d=w.load(folder/'report.json')
            if d.get('tool_plan')!=plan:raise w.WorkflowError('The latest approved solution does not contain this exact tool plan. Old approval cannot override a newer scope.')
            for rel,expected in a.get('files',{}).items():
                if w.digest(w.safe_path(run,rel))!=expected:raise w.WorkflowError('Approved report was changed; it no longer authorizes this plan.')
            if not a.get('user_message') or d.get('content_sha256')!=w.report_content_hash(d):raise w.WorkflowError('Invalid recorded approval evidence.')
            return {**result,'recorded_approval_match':True,'approval_gate':a['gate'],'approval_revision':a['revision'],'run_id':s['run_id'],'note':'A matching record is not user authentication, OS sandboxing, safe-code analysis, approval of external writes, or proof that the plan was visibly explained. Verify visible disclosure and real user approval.'}
    raise w.WorkflowError('This exact tool plan has no matching unmodified approved gate in this task. Stop and ask Astra for user confirmation.')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--run',type=Path);a=p.parse_args()
    try:
        d=w.load(a.plan);d=d.get('tool_plan',d)
        v=match_approval(a.run,d) if a.run else {**validate(d),'recorded_approval_match':False,'approval_required':bool(d['tools'])}
        print(json.dumps(v,ensure_ascii=False,indent=2));return 0
    except (ValueError,OSError,KeyError,TypeError) as e:print('HexiPlan tools:',e,file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())
