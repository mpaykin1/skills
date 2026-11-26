#!/usr/bin/env python3
"""Experimental single HTML packer for UNCOMPRESSED Unity WebGL builds.

Makes Blob URLs from embedded base64 for .loader.js/.framework.js/.wasm/.data.
Unity file:// browser security, threads, special plugins and StreamingAssets may still fail.
Does not claim full offline support until browser verification.
"""
from __future__ import annotations
import argparse
import base64
import html
import json
from pathlib import Path
import re
import sys


def pack(index:Path,out:Path,max_mb=256):
    index=index.expanduser().resolve(strict=True)
    base=index.parent
    build=base/'Build'
    if not build.is_dir():raise ValueError('Unity WebGL Build/ directory missing')
    matched={}
    for label,suffix in [('loader','.loader.js'),('framework','.framework.js'),('wasm','.wasm'),('data','.data')]:
        found=list(build.glob('*'+suffix))
        if len(found)!=1:raise ValueError(f'Expected exactly one Build/*{suffix}; found {len(found)}. Require uncompressed Unity WebGL build.')
        matched[label]=found[0]
    # Forbid multi-thread worker and compressed builds that Blob URLs cannot transparently serve.
    extras=[p.name for p in build.iterdir() if p.is_file() and ('.worker.' in p.name.lower() or p.suffix.lower() in {'.br','.gz','.unityweb'})]
    if extras:raise ValueError('Unity worker or compressed resources unsupported: '+', '.join(extras[:5]))
    streaming=base/'StreamingAssets'
    if streaming.exists() and any(streaming.rglob('*')):raise ValueError('StreamingAssets require URL fetch; single HTML unsupported for this build')
    if any(p.is_file() and p.name not in {q.name for q in matched.values()} and p.suffix.lower() in {'.wasm','.data','.js'} for p in build.iterdir()):
        raise ValueError('Additional runtime files detected; do not silently omit Unity resources')
    size=sum(p.stat().st_size for p in matched.values())
    if size>max_mb*1024*1024:raise ValueError(f'Unity payload exceeds {max_mb} MB')
    # Use the original runtime bytes, only the bootstrap page is replaced.
    payload={k:base64.b64encode(p.read_bytes()).decode('ascii') for k,p in matched.items()}
    original=index.read_text(encoding='utf-8-sig')
    title=re.search(r'(?is)<title[^>]*>(.*?)</title>',original)
    title=html.escape(re.sub('<[^>]*>','',title.group(1)).strip() if title else 'Unity game')
    # Original WebGL loader might rely on HTTP headers; blob URLs are an experimental fallback.
    template='''<!doctype html><html lang="en"><head><meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no" />
<title>__TITLE__</title><style>
html,body{margin:0;width:100%;height:100%;background:#10151b;overflow:hidden}
#unity-canvas{display:block;width:100vw;height:100dvh;background:#10151b;touch-action:none}
#indicator{position:fixed;left:1.5rem;bottom:1.25rem;color:#b4becb;font:13px system-ui;pointer-events:none}
</style></head><body><canvas id="unity-canvas" tabindex="-1"></canvas>
<div id="indicator">Loading game…</div><script>
(async()=>{
'use strict';
const encoded=__PAYLOAD__;
const bytes=b64=>{const s=atob(b64),b=new Uint8Array(s.length);for(let i=0;i<s.length;i++)b[i]=s.charCodeAt(i);return b};
const types={loader:'application/javascript',framework:'application/javascript',wasm:'application/wasm',data:'application/octet-stream'};
const links={};
for(const k of Object.keys(encoded))links[k]=URL.createObjectURL(new Blob([bytes(encoded[k])],{type:types[k]}));
const status=document.getElementById('indicator');
const canvas=document.getElementById('unity-canvas');
const config={dataUrl:links.data,frameworkUrl:links.framework,codeUrl:links.wasm,
streamingAssetsUrl:'',companyName:'Original',productName:document.title,productVersion:'1.0',
webglContextAttributes:{preserveDrawingBuffer:false}};
try {
 await new Promise((resolve,reject)=>{const script=document.createElement('script');script.src=links.loader;
 script.onload=resolve;script.onerror=()=>reject(new Error('Unity loader unavailable'));document.body.appendChild(script)});
 if(typeof createUnityInstance!=='function')throw new Error('Unity loader did not expose createUnityInstance');
 await createUnityInstance(canvas,config,p=>{status.textContent='Loading '+Math.round(p*100)+'%'});
 status.remove();canvas.focus();
} catch(err){status.textContent='Unity WebGL cannot start in this browser: '+(err?.message||err);console.error(err)}
})();
</script></body></html>'''
    document=template.replace('__TITLE__',title).replace('__PAYLOAD__',json.dumps(payload,separators=(',',':')).replace('<','\\u003c'))
    if out.resolve()==index:raise ValueError('Refusing to overwrite original Unity WebGL index')
    out=out.expanduser().resolve();out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(document,encoding='utf-8')
    print('EXPERIMENTAL Unity single HTML:',out)
    print('Original Unity WebGL build remains the preferred verified output.')
    return out


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('index',type=Path)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--max-mb',type=int,default=256)
    a=ap.parse_args();pack(a.index,a.out,a.max_mb)

if __name__=='__main__':
    try:main()
    except (OSError,ValueError) as e:sys.exit('ERROR: '+str(e))
