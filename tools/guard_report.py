#!/usr/bin/env python3
"""Mechanical pre-render protection for prose editing, NOT semantic/AI detection."""
from __future__ import annotations
import argparse, collections, json, re, sys
from pathlib import Path
sys.dont_write_bytecode = True
NUMBER = re.compile(r'(?<![\w.])[-+−]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?%?')
PROTECTED = re.compile(
    r'`[^`]*`|https?://[^\s<>"\)]+|[A-Za-z]:[\\/][^\s<>"，。；]+|'
    r'(?<!\w)(?:SYNTHETIC_ONLY|PUBLIC_BENCHMARK|REAL|DESIGN_MOCKUP|NOT_RUN|PASS|FAILED|FAIL|BLOCKED|DRAFT|APPROVED)(?!\w)|'
    r'\b(?:n|N|M|SD|SE|CI|p|r|t|F|df|beta|alpha)\s*[=<>≤≥]\s*[-+−]?(?:\d+(?:\.\d*)?|\.\d+)|'
    r'\[(?:S|E|REF|CITE)[-_]?\d+\]'
)
def ptr(parts) -> str:
    return '/'+ '/'.join(str(x).replace('~','~0').replace('/','~1') for x in parts)

def allowed_fields(data: dict) -> set[tuple]:
    result = set()
    for key in ('subtitle','summary'):
        if isinstance(data.get(key),str): result.add((key,))
    for i,s in enumerate(data.get('sections',[])):
        if not isinstance(s,dict): continue
        for j,b in enumerate(s.get('blocks',[])):
            if not isinstance(b,dict): continue
            base = ('sections',i,'blocks',j)
            typ = b.get('type')
            keys = ('text',) if typ in ('text','callout') else ('caption','note') if typ in ('figure','table') else ()
            for k in keys:
                if isinstance(b.get(k),str): result.add(base+(k,))
            if typ == 'gallery':
                for q,im in enumerate(b.get('images',[])):
                    if isinstance(im,dict):
                        for k in ('caption','note'):
                            if isinstance(im.get(k),str): result.add(base+('images',q,k))
    return result

def check(before: dict, after: dict) -> dict:
    if not isinstance(before,dict) or not isinstance(after,dict): raise ValueError('Report JSON must be an object.')
    permitted = allowed_fields(before); issues=[]; changes=[]
    def walk(a,b,path=()):
        if type(a) is not type(b):
            issues.append({'path':ptr(path),'reason':'value type changed'});return
        if isinstance(a,dict):
            if a.keys() != b.keys():
                issues.append({'path':ptr(path),'reason':'keys added or removed'});return
            for k in a: walk(a[k],b[k],path+(k,))
        elif isinstance(a,list):
            if len(a) != len(b):
                issues.append({'path':ptr(path),'reason':'list length changed'});return
            for i,(aa,bb) in enumerate(zip(a,b)): walk(aa,bb,path+(i,))
        elif a != b:
            if path not in permitted or not isinstance(a,str):
                issues.append({'path':ptr(path),'reason':'protected structure or non-prose data changed'});return
            changes.append(ptr(path))
            if NUMBER.findall(a) != NUMBER.findall(b):
                issues.append({'path':ptr(path),'reason':'numeric sequence changed'})
            norm = lambda s: re.sub(r'\s+','',s)
            if collections.Counter(map(norm,PROTECTED.findall(a))) != collections.Counter(map(norm,PROTECTED.findall(b))):
                issues.append({'path':ptr(path),'reason':'protected status, identifier, code, URL, path or statistic changed'})
    walk(before,after)
    return {'mechanical_pass':not issues,'changed_prose_fields':changes,'violations':issues,
            'semantic_equivalence_verified':False,'scientific_validity_verified':False,
            'ai_authorship_detected':None,
            'limitations':['Only configured prose fields may change. Structure, table data and metadata remain fixed.',
                           'Numeric/protected-token checks are conservative and cannot understand meaning.',
                           'The report Sol must still compare claims, uncertainty, units, direction and attribution.',
                           'A pass does not authorize modifying an already submitted or approved report.']}

def read_json(path: Path):
    def fail_constant(value): raise ValueError('Non-finite JSON constant: '+value)
    return json.loads(path.read_text(encoding='utf-8-sig'),parse_constant=fail_constant)

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--before',type=Path,required=True);p.add_argument('--after',type=Path,required=True)
    a=p.parse_args(argv)
    try:
        result=check(read_json(a.before),read_json(a.after))
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0 if result['mechanical_pass'] else 2
    except (OSError,ValueError,TypeError,KeyError) as e:
        print('HexiPlan prose guard: '+str(e),file=sys.stderr);return 2
if __name__=='__main__': raise SystemExit(main())
