#!/usr/bin/env python3
"""Run an explicitly scoped SiteOne crawl using a locally installed trusted binary."""
import argparse, json, pathlib, re, shutil, subprocess, sys, tempfile
from urllib.parse import urlsplit

def main():
    p=argparse.ArgumentParser();p.add_argument('url');p.add_argument('--output',required=True);p.add_argument('--baseline');p.add_argument('--min-pages',type=int,default=1);p.add_argument('--gate',action='store_true');p.add_argument('--binary',default='siteone-crawler');a=p.parse_args()
    u=urlsplit(a.url)
    if u.scheme not in ('http','https') or not u.hostname or u.username or u.password or u.query or u.fragment or not u.path.endswith('/') or a.min_pages<1: p.error('Use an authorized site root ending in /, without credentials/query/fragment')
    binary=shutil.which(a.binary)
    if not binary: p.error('SiteOne binary not installed; install a verified upstream release first')
    flags=subprocess.run([binary,'--help'],capture_output=True,text=True,timeout=30)
    helptext=flags.stdout+flags.stderr
    scope='^'+re.escape(a.url)+r'(?:[^?#]*)?(?:\?[^#]*)?$'
    out=pathlib.Path(a.output).resolve();out.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        raw=pathlib.Path(tmp)/'crawl.json'
        cmd=[binary,'--url='+a.url,'--device=mobile','--workers=2','--max-reqs-per-sec=2','--max-visited-urls=300','--include-regex='+scope,'--remove-query-params','--output-json-file='+str(raw)]
        if a.gate:
            cmd+=['--ci','--ci-min-pages='+str(a.min_pages),'--ci-min-assets=0','--ci-max-404=0','--ci-max-5xx=0']
            if a.baseline: cmd+=['--ci-baseline='+str(pathlib.Path(a.baseline).resolve()),'--ci-max-score-drop=0']
        elif a.baseline: p.error('--baseline requires --gate')
        missing=[x.split('=')[0] for x in cmd[1:] if x.split('=')[0] not in helptext]
        if missing: p.error('Unsupported flags in installed release: '+', '.join(missing))
        result=subprocess.run(cmd,timeout=600)
        if not raw.is_file(): raise RuntimeError('Crawler produced no JSON; no SEO result available')
        data=json.loads(raw.read_text())
        if not isinstance(data,dict) or not data: raise RuntimeError('Invalid or empty crawler result')
        out.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
        return result.returncode
if __name__=='__main__': sys.exit(main())
