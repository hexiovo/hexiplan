#!/usr/bin/env python3
"""Select task-scoped, local HexiPlan Markdown. No model calls, installs or network."""
from __future__ import annotations
import argparse, copy, hashlib, json, sys
from pathlib import Path
sys.dont_write_bytecode = True
import workflow as w
HOME = Path(__file__).resolve().parent.parent
ROLES = ('astra','sol-manager','sol-researcher','sol-reporter','sol-validator','sol-specialist','luna')
KINDS = ('plan','record','implementation','report','academic-report','literature','method-review','citation','visualization','ui-design','ui-implementation','debug')
ALLOWED = {
    'plan': set(ROLES), 'record': set(ROLES),
    'implementation': {'sol-manager','sol-specialist','luna'},
    'report': {'sol-reporter'}, 'academic-report': {'sol-reporter'},
    'literature': {'sol-researcher'},
    'method-review': {'sol-researcher','sol-validator','sol-manager','sol-specialist'},
    'citation': {'sol-researcher','sol-reporter'},
    'visualization': {'luna','sol-specialist'},
    'ui-design': {'sol-manager','sol-specialist','luna'},
    'ui-implementation': {'sol-specialist','luna'},
    'debug': {'sol-manager','sol-specialist','sol-validator','luna'},
}
def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def catalog(home: Path = HOME) -> dict:
    p = w.safe_path(home, 'modules/catalog.json')
    d = json.loads(p.read_text(encoding='utf-8-sig'))
    if not d.get('explicit_hexiplan_only') or d.get('register_as_skill'):
        raise w.WorkflowError('Module catalog must be explicit-only, without Skill registration.')
    ids = set()
    for m in d['modules']:
        if m['id'] in ids: raise w.WorkflowError('Duplicate module ID.')
        ids.add(m['id'])
        p = w.safe_path(home, m['path'])
        if not p.is_file() or p.suffix != '.md' or not p.is_relative_to((home/'modules').resolve()):
            raise w.WorkflowError('Module must be a local Markdown under modules/.')
        if sha(p.read_bytes()) != m['sha256']:
            raise w.WorkflowError('Module hash mismatch: '+m['id'])
    return d

def select(role: str, kind: str, language: str='zh', home: Path=HOME) -> dict:
    if role not in ROLES or kind not in KINDS or language not in ('zh','en'):
        raise w.WorkflowError('Unknown role, task kind or language.')
    if role not in ALLOWED[kind]:
        raise w.WorkflowError('This role must not perform that task. Delegate without changing role ownership.')
    humanizer = 'humanizer-zh' if language == 'zh' else 'humanizer-en'
    rules = {
        'plan': [], 'record': [], 'implementation': [],
        'report': ['report-style',humanizer],
        'academic-report': ['report-style','academic-fidelity','scientific-writing',humanizer],
        'literature': ['academic-fidelity','literature-review','citation-management'],
        'method-review': ['academic-fidelity','scientific-critical-thinking'],
        'citation': ['citation-management'],
        'visualization': ['academic-fidelity','scientific-visualization'],
        'ui-design': ['frontend-design'], 'ui-implementation': ['frontend-design'],
        'debug': ['systematic-debugging'],
    }
    data = catalog(home)
    byid = {m['id']:m for m in data['modules']}
    selected = [copy.deepcopy(byid[x]) for x in rules[kind]]
    return {'schema_version':1,'package_version':data['version'],'selection_only':True,
            'role':role,'kind':kind,'language':language,'modules':selected,
            'router':'modules/MODULE_ROUTER.md',
            'catalog_sha256':sha((home/'modules/catalog.json').read_bytes()),
            'network_used':False,'models_called':False,'installs_performed':False,
            'note':'Read only these task-relevant modules. Selection is not evidence of agent reading, compliance, model routing, or user approval.'}

def checked_run(run: Path) -> Path:
    absolute = run.expanduser().absolute()
    try: rel = absolute.relative_to(HOME)
    except ValueError as exc: raise w.WorkflowError('Records must stay inside this toolkit/runs.') from exc
    path = w.safe_path(HOME, rel.as_posix())
    if not path.is_relative_to((HOME/'runs').resolve()) or not (path/'journal').is_dir():
        raise w.WorkflowError('Use an initialized run in this toolkit/runs.')
    return path

def record_selection(run: Path, selection: dict, owner: str) -> dict:
    run = checked_run(run); w.identifier(owner)
    # Recompute rather than accepting arbitrary paths supplied by a caller.
    verified = select(selection['role'], selection['kind'], selection['language'])
    if selection != verified: raise w.WorkflowError('Selection no longer matches the current catalog.')
    with w.locked(run):
        s = w.state(run)
        record = copy.deepcopy(verified)
        record.update(owner=owner, selected_at=w.now(), phase=s['phase'], step=w.current_step(s))
        for m in record['modules']:
            source = w.safe_path(HOME, m['path']); content = source.read_bytes()
            rel = 'references/module-snapshots/'+m['sha256']+'.md'
            target = w.safe_path(run, rel, must_exist=False)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                if target.read_bytes() != content: raise w.WorkflowError('Existing module snapshot was changed.')
            else:
                with target.open('xb') as f: f.write(content)
            m['snapshot'] = rel
        # One last selection per owner; immutable events preserve earlier history.
        records = s.setdefault('module_selections', {})
        records[owner] = record
        w.commit(run, s, 'module-selection', {'owner':owner, 'selection':record})
    return record

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--role',choices=ROLES,required=True); p.add_argument('--kind',choices=KINDS,required=True)
    p.add_argument('--language',choices=['zh','en'],default='zh'); p.add_argument('--print-content',action='store_true')
    p.add_argument('--run',type=Path); p.add_argument('--owner'); p.add_argument('--record-selection',action='store_true')
    a = p.parse_args(argv)
    try:
        result = select(a.role,a.kind,a.language)
        if a.record_selection:
            if not a.run or not a.owner: raise w.WorkflowError('--record-selection requires --run and --owner.')
            result = record_selection(a.run,result,a.owner)
        elif a.run or a.owner:
            raise w.WorkflowError('Use --record-selection explicitly to write any record.')
        print(json.dumps(result,ensure_ascii=False,indent=2))
        if a.print_content:
            for m in result['modules']:
                print('\n--- '+m['path']+' ---\n')
                print(w.safe_path(HOME,m['path']).read_text(encoding='utf-8'))
        return 0
    except (w.WorkflowError,OSError,KeyError,TypeError,json.JSONDecodeError) as e:
        print('HexiPlan modules: '+str(e),file=sys.stderr);return 2
if __name__=='__main__': raise SystemExit(main())
