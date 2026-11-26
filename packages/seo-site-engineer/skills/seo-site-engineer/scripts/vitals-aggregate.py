#!/usr/bin/env python3
"""Offline p75 aggregation of explicitly authorized, final real-user observations."""
import argparse, collections, json, math, pathlib, re
THRESHOLDS={'LCP':2500,'INP':200,'CLS':0.1}
FIELDS={'schema','source','route','device','release','metric','value','id'}
TOKEN=re.compile(r'[A-Za-z0-9._-]{1,80}\Z')
def valid(r):
    return (isinstance(r,dict) and set(r)==FIELDS and type(r['schema']) is int and r['schema']==1 and r['source']=='field'
        and all(isinstance(r[k],str) and TOKEN.fullmatch(r[k]) for k in ('route','release','id'))
        and r['device'] in ('mobile','desktop','unknown') and r['metric'] in THRESHOLDS
        and type(r['value']) in (int,float) and math.isfinite(r['value']) and r['value']>=0)
def main():
    p=argparse.ArgumentParser();p.add_argument('input');p.add_argument('--release',required=True);p.add_argument('--output',required=True);p.add_argument('--baseline');a=p.parse_args()
    if not TOKEN.fullmatch(a.release):p.error('Invalid release')
    groups=collections.defaultdict(dict); count=0
    with open(a.input,encoding='utf-8') as f:
        for i,line in enumerate(f,1):
            if len(line)>4096:raise ValueError(f'oversized row {i}')
            if not line.strip():continue
            r=json.loads(line)
            if not valid(r) or r['release']!=a.release:raise ValueError(f'invalid or mixed-release row {i}')
            k=(r['route'],r['device'],r['metric']);groups[k][r['id']]=r['value'];count+=1
    out={'schema':1,'source':'field','release':a.release,'min_samples':75,'rows':[],'status':'insufficient'}
    old={}
    if a.baseline:
        b=json.loads(pathlib.Path(a.baseline).read_text());
        if b.get('schema')!=1 or b.get('source')!='field' or b.get('min_samples')!=75 or b.get('release')==a.release:raise ValueError('incompatible baseline')
        old={(r['route'],r['device'],r['metric']):r for r in b['rows'] if r['n']>=75 and r.get('p75') is not None}
    for k,ids in sorted(groups.items()):
        route,device,metric=k;v=sorted(ids.values());n=len(v);p75=v[math.ceil(.75*n)-1] if n>=75 else None
        row={'route':route,'device':device,'metric':metric,'n':n,'p75':p75,'status':'insufficient' if p75 is None else ('good' if p75<=THRESHOLDS[metric] else 'above-target')}
        if p75 is not None and k in old:row['delta_p75']=round(p75-old[k]['p75'],6)
        out['rows'].append(row)
    if out['rows'] and all(r['p75'] is not None for r in out['rows']):out['status']='observations-available'
    pathlib.Path(a.output).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(out['status'],count,'observations received; no ranking conclusion')
if __name__=='__main__':main()
