#!/usr/bin/env python3
"""Scoped local Lighthouse CI collection and median regression gate."""
import argparse, json, math, pathlib, shutil, statistics, subprocess, tempfile, sys
from urllib.parse import urlsplit
PIN='0.15.1'
CATS=('seo','performance','accessibility')
METRICS=('largest-contentful-paint','cumulative-layout-shift','total-blocking-time')
LIMITS={'seo':.90,'performance':.80,'accessibility':.90,'largest-contentful-paint':2500,'cumulative-layout-shift':.1,'total-blocking-time':200}
def valid(url, root):
    u,r=urlsplit(url),urlsplit(root)
    return u.scheme in ('http','https') and bool(u.hostname) and not(u.username or u.password or u.query or u.fragment) and (u.scheme,u.netloc)==(r.scheme,r.netloc) and u.path.startswith(r.path) and not any(x in u.path.lower() for x in ('..','%','\\'))
def number(x):
    if not isinstance(x,(int,float)) or isinstance(x,bool) or not math.isfinite(x) or x<0: raise ValueError('Invalid metric')
    return x
def summarize(reports, urls):
    groups={u:[] for u in urls}; versions=set()
    for r in reports:
        if r.get('runtimeError'): raise ValueError('Lighthouse runtime error')
        url=r.get('requestedUrl'); final=r.get('finalDisplayedUrl') or r.get('finalUrl')
        if url not in groups or final!=url: raise ValueError('Unexpected URL or redirect: '+str(final))
        if r.get('configSettings',{}).get('formFactor')!='mobile': raise ValueError('Not a mobile run')
        version=r.get('lighthouseVersion'); browser=r.get('environment',{}).get('hostUserAgent')
        if not version or not browser: raise ValueError('Missing engine identity')
        versions.add((version,browser))
        vals={k:number(r['categories'][k]['score']) for k in CATS}
        if any(v>1 for v in vals.values()): raise ValueError('Invalid category score')
        vals.update({k:number(r['audits'][k]['numericValue']) for k in METRICS})
        groups[url].append(vals)
    if len(versions)!=1 or any(len(v)!=3 for v in groups.values()): raise ValueError('Incomplete or mixed-version runs')
    return {'lhci':PIN,'engine':list(next(iter(versions))),'profile':'mobile-default-3-runs','pages':{u:{k:statistics.median(x[k] for x in g) for k in CATS+METRICS} for u,g in groups.items()}}
def failures(data,baseline=None):
    issues=[]
    if baseline and (any(data[k]!=baseline[k] for k in ('lhci','engine','profile')) or set(data['pages'])!=set(baseline['pages'])): raise ValueError('Baseline environment or URLs differ')
    for u,vals in data['pages'].items():
        for k,v in vals.items():
            if (k in CATS and v<LIMITS[k]) or (k in METRICS and v>LIMITS[k]): issues.append(f'{u} {k}: {v} misses {LIMITS[k]}')
            if baseline:
                prev=number(baseline['pages'][u][k]); tol=.03 if k in CATS else (.02 if k=='cumulative-layout-shift' else max(50,prev*.1))
                if (k in CATS and v<prev-tol) or (k in METRICS and v>prev+tol): issues.append(f'{u} {k}: regression {prev} -> {v}')
    return issues
def main():
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('--url',action='append',required=True);p.add_argument('--output',required=True);p.add_argument('--binary',default='lhci');p.add_argument('--baseline');p.add_argument('--gate',action='store_true');a=p.parse_args()
    if not urlsplit(a.root).path.endswith('/') or not valid(a.root,a.root) or not all(valid(u,a.root) for u in a.url) or len(set(a.url))!=len(a.url) or len(a.url)>30: p.error('Require authorized root with trailing slash, 1-30 distinct in-scope URLs')
    b=shutil.which(a.binary)
    if not b: p.error('Lighthouse CI missing; install trusted pinned @lhci/cli first')
    version=subprocess.check_output([b,'--version'],text=True,timeout=30).strip().lstrip('v')
    if version!=PIN: p.error('Require verified LHCI '+PIN+'; found '+version)
    out=pathlib.Path(a.output).resolve()
    with tempfile.TemporaryDirectory() as tmp:
        config=pathlib.Path(tmp)/'lighthouserc.json';config.write_text(json.dumps({'ci':{'collect':{'url':a.url,'numberOfRuns':3,'settings':{'formFactor':'mobile','onlyCategories':list(CATS)}}}}))
        subprocess.run([b,'collect','--config='+str(config)],cwd=tmp,check=True,timeout=1800)
        reports=[json.loads(f.read_text()) for f in pathlib.Path(tmp,'.lighthouseci').glob('lhr-*.json')]
        data=summarize(reports,a.url)
        # Raw audit details stay local and are included in the output for diagnosis.
        data['reports']=reports
        baseline=json.loads(pathlib.Path(a.baseline).read_text()) if a.baseline else None
        data['issues']=failures(data,baseline)
        out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    return 1 if a.gate and data['issues'] else 0
if __name__=='__main__': sys.exit(main())
