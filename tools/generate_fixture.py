#!/usr/bin/env python3
"""Generate actual SYNTHETIC_ONLY data files for verification, never research findings."""
from __future__ import annotations
import argparse,csv,hashlib,json,math,random,sys
from pathlib import Path

def generate(out:Path,kind='tabular',seed=20260927):
    if out.exists():raise ValueError('Output exists; do not overwrite verification data.')
    out.mkdir(parents=True);r=random.Random(seed);expected={}
    if kind=='tabular':
        # Independent known-answer column; noisy column is for parser robustness only.
        rows=[['id','known_value','noisy_value']]+[[i,i,round(r.gauss(0,1),8)] for i in range(1,101)]
        expected={'known_value_n':100,'known_value_mean':50.5,'known_value_sum':5050,'known_value_sample_variance':100*101/12,'notes':'Analytical identities for integers 1..100; noisy column has no claimed true sample statistic.'}
    else:
        fs=128;n=1024;freq=8
        rows=[['time_s','clean_sine','signal_with_marked_jump']]
        for i in range(n):
            x=math.sin(2*math.pi*freq*i/fs)
            rows.append([i/fs,x,x+(5 if 384<=i<448 else 0)])
        expected={'sample_rate_hz':fs,'n_samples':n,'frequency_hz':freq,'clean_mean':0,'clean_rms':math.sqrt(.5),'rms_tolerance':1e-10,'jump_start_index0':384,'jump_stop_exclusive_index0':448,'notes':'Integer-cycle discrete sine and a known deterministic step; not a model of real physiological data.'}
    path=out/('SYNTHETIC_ONLY_'+kind+'.csv')
    with path.open('w',encoding='utf-8',newline='') as f:csv.writer(f).writerows(rows)
    manifest={'source_type':'SYNTHETIC_ONLY','purpose':'Software verification only; no empirical or participant claim.','generator':'tools/generate_fixture.py','seed':seed,'kind':kind,'file':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'expected':expected,'limitations':'Does not validate real-data accuracy, realistic noise, clinical/scientific effects or deployment performance. Never modify production parameters just to pass this fixture.'}
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return manifest

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--kind',choices=['tabular','timeseries'],default='tabular');p.add_argument('--seed',type=int,default=20260927);a=p.parse_args()
    try:print(json.dumps(generate(a.out,a.kind,a.seed),ensure_ascii=False,indent=2));return 0
    except (OSError,ValueError) as e:print(str(e),file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())
