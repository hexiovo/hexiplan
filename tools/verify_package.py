#!/usr/bin/env python3
"""Verify package integrity and run bounded, offline, standard-library local tests."""
from __future__ import annotations
import argparse,ast,hashlib,json,subprocess,sys
from pathlib import Path
sys.dont_write_bytecode=True
HOME=Path(__file__).resolve().parent.parent

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--skip-tests',action='store_true');a=ap.parse_args()
    if sys.version_info<(3,10):print('Python 3.10+ is required.',file=sys.stderr);return 2
    errors=[];count=0
    checksum=HOME/'CHECKSUMS.sha256'
    if not checksum.is_file():errors.append('CHECKSUMS.sha256 is missing.')
    else:
        for line in checksum.read_text(encoding='utf-8').splitlines():
            if not line.strip():continue
            try:
                expected,rel=line.split('  ',1);p=HOME/rel
                if Path(rel).is_absolute() or '..' in Path(rel).parts or p.is_symlink() or not p.resolve().is_relative_to(HOME):raise ValueError('unsafe manifest path')
                actual=hashlib.sha256(p.read_bytes()).hexdigest()
                if actual!=expected:errors.append('Hash mismatch: '+rel)
                count+=1
            except (OSError,ValueError) as e:errors.append(line+': '+str(e))
    for p in HOME.rglob('*.py'):
        if 'runs' in p.relative_to(HOME).parts:continue
        try:ast.parse(p.read_text(encoding='utf-8-sig'),filename=str(p))
        except (OSError,SyntaxError) as e:errors.append(str(e))
    toml_mode='simple required-fields check'
    try:
        import tomllib
        for p in (HOME/'agents').glob('*.toml'):
            d=tomllib.loads(p.read_text(encoding='utf-8-sig'))
            for k in ['name','description','model','model_reasoning_effort','developer_instructions']:
                if not d.get(k):errors.append(str(p)+': missing '+k)
        toml_mode='stdlib tomllib parsed'
    except ImportError:
        from launch import role_settings
        try:role_settings()
        except ValueError as e:errors.append(str(e))
    except (OSError,ValueError) as e:errors.append(str(e))
    print(json.dumps({'integrity_files_checked':count,'toml':toml_mode,'errors':errors,'network_used':False,'live_codex_models_verified':False},ensure_ascii=False,indent=2),flush=True)
    if errors:return 2
    if not a.skip_tests:
        result=subprocess.run([sys.executable,'-B','-m','unittest','discover','-s',str(HOME/'tests'),'-p','test_*.py','-v'],cwd=HOME)
        if result.returncode:return result.returncode
    print('Local package checks passed. This is not Windows/Word/Codex account integration verification.')
    return 0
if __name__=='__main__':raise SystemExit(main())
