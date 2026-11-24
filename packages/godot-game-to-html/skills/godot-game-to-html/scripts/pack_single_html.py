#!/usr/bin/env python3
"""Experimental single-file HTML packer for a pre-built *single-threaded* Godot Web export.

Embeds local JS/CSS and binary assets; intercepts fetch of virtual paths.
Cannot promise compatibility with every Godot version, browser or file://.
"""
from __future__ import annotations
import argparse
import base64
import json
import mimetypes
from pathlib import Path
import re
import sys

SCRIPT_RE=re.compile(r'(?is)<script\b(?P<attrs>[^>]*)\bsrc=["\'](?P<src>[^"\']+)["\'](?P<rest>[^>]*)>\s*</script>')
CSS_RE=re.compile(r'(?is)<link\b(?P<attrs>[^>]*)>')
ATTR_RE=re.compile(r'(?i)\b([\w-]+)\s*=\s*(["\'])(.*?)\2')

def attributes(src):
    return {k.lower():v for k,_,v in ATTR_RE.findall(src)}

def local_path(base:Path, val:str) -> Path|None:
    if not val or val.startswith(('/', '//','#','data:','blob:','http:','https:')) or '?' in val or '#' in val:
        return None
    path=(base/val).resolve()
    try: path.relative_to(base.resolve())
    except ValueError: return None
    return path if path.is_file() else None

def safe_script(t:str)->str:
    return re.sub(r'(?i)</script',r'<\\/script',t)

def mime(p:Path)->str:
    if p.suffix.lower()=='.wasm': return 'application/wasm'
    if p.suffix.lower()=='.pck': return 'application/octet-stream'
    return mimetypes.guess_type(p.name)[0] or 'application/octet-stream'

def inline_scripts(html:str,base:Path):
    seen=set()
    def repl(m):
        at=attributes(m.group('attrs')+' '+m.group('rest'))
        src=m.group('src')
        if 'module' in at.get('type','') or 'integrity' in at:
            raise ValueError(f'Unsupported module/integrity script: {src}')
        p=local_path(base,src)
        if p is None: raise ValueError(f'External or missing script: {src}')
        seen.add(p.resolve())
        code=p.read_text(encoding='utf-8-sig')
        # Preserve original execution order. A classic script is synchronous if no async/defer attr.
        return '<script>'+safe_script(code)+'</script>'
    return SCRIPT_RE.sub(repl,html),seen

def inline_styles(html:str,base:Path):
    def repl(m):
        at=attributes(m.group('attrs'))
        if at.get('rel','').lower()!='stylesheet':return m.group(0)
        p=local_path(base,at.get('href',''))
        if p is None: raise ValueError(f'External/missing stylesheet: {at.get("href")}')
        css=p.read_text(encoding='utf-8-sig')
        if re.search(r'url\(\s*["\']?(?!data:)',css,re.I):
            raise ValueError('CSS uses external url(): cannot inline without loss')
        return '<style>'+css.replace('</style','<\\/style')+'</style>'
    return CSS_RE.sub(repl,html)

# Always synchronous asset resolver, before Godot runtime and inline boot code.
PATCH=r"""<script>
(()=>{
  "use strict";
  const files=__DATA_PLACEHOLDER__;
  const originalFetch=window.fetch.bind(window);
  const basenames=Object.keys(files);
  function choose(input){
    let url;
    try { url = new URL(typeof input==='string'||input instanceof URL ? input : input.url, document.baseURI); }
    catch(e) { return null; }
    const name=decodeURIComponent(url.pathname.split('/').pop() || '');
    // Godot's default exports put WASM, PCK, PNG next to index.html.
    return Object.prototype.hasOwnProperty.call(files,name) ? files[name] : null;
  }
  function decode(b64){
    const binary=atob(b64),n=binary.length,bytes=new Uint8Array(n);
    for(let i=0;i<n;i++)bytes[i]=binary.charCodeAt(i);
    return bytes;
  }
  window.fetch=function(resource,options){
    const entry=choose(resource);
    if(!entry)return originalFetch(resource,options);
    const headers=new Headers({'Content-Type':entry.mime,'Content-Length':String(entry.size)});
    if(options?.signal?.aborted)return Promise.reject(new DOMException('Aborted','AbortError'));
    return Promise.resolve(new Response(new Blob([decode(entry.base64)],{type:entry.mime}),{status:200,headers}));
  };
  // Expose only the asset names to diagnose incorrect Godot resource paths.
  window.__godotSingleFileAssets=basenames;
})();
</script>"""

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('html',type=Path,help='Godot exported index.html')
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--max-mb',type=int,default=256)
    args=ap.parse_args()
    source=args.html.resolve(); base=source.parent
    if not source.is_file():raise ValueError(f'No export HTML: {source}')
    if source.suffix.lower()!='.html':raise ValueError('Expected .html export file')
    html=source.read_text(encoding='utf-8-sig')
    if 'GODOT_CONFIG' not in html and 'new Engine' not in html:
        print('NOTE: no recognized Godot bootstrap token; verify this is Godot Web export',file=sys.stderr)
    if re.search(r'(?i)serviceworker|crossOriginIsolated',html):
        print('WARNING: service workers / isolation may not work on file://',file=sys.stderr)
    # Godot multithread builds require COOP/COEP and workers; fail loudly.
    siblings=[p for p in base.iterdir() if p.is_file() and p!=source]
    if any('.worker.' in p.name.lower() or p.name.endswith('.worker.js') for p in siblings):
        raise ValueError('Detected worker-based export. Re-export Godot without threads for single HTML.')
    html,used=inline_scripts(html,base)
    html=inline_styles(html,base)
    all_assets={}
    total=0
    for p in sorted(siblings):
        if p.resolve() in used or p.suffix.lower() in {'.html','.htm','.css'}:continue
        if p.suffix.lower() in {'.map','.md','.txt','.log'}:continue
        total+=p.stat().st_size
        if total>args.max_mb*1024*1024:
            raise ValueError(f'Embedded data exceed --max-mb={args.max_mb}; try native Web export.')
        if p.name in all_assets:raise ValueError('Duplicate asset basename: '+p.name)
        all_assets[p.name]={'base64':base64.b64encode(p.read_bytes()).decode('ascii'),
                            'mime':mime(p),'size':p.stat().st_size}
    if not all_assets:raise ValueError('No Web assets found. Godot export usually contains .wasm and .pck')
    if not any(n.endswith('.wasm') for n in all_assets):
        raise ValueError('Missing .wasm: this does not look like a complete Godot Web export')
    if not any(n.endswith('.pck') for n in all_assets):
        raise ValueError('Missing .pck: original game data was not found')
    # Keep image and icon links offline; local binary URLs become data URIs.
    def embed_tag(m):
        tag=m.group(0)
        def swap(a):
            k, quote, value = a.group(1), a.group(2), a.group(3)
            if k.lower() not in {'src','href','poster'}:
                return a.group(0)
            p=local_path(base,value)
            if not p or p.suffix.lower() in {'.js','.css','.html'}:
                return a.group(0)
            return f'{k}={quote}data:{mime(p)};base64,{base64.b64encode(p.read_bytes()).decode("ascii")}{quote}'
        return ATTR_RE.sub(swap,tag)
    html=re.sub(r'(?is)<(?:img|link|source|video)\b[^>]*>',embed_tag,html)
    patch=PATCH.replace('__DATA_PLACEHOLDER__',json.dumps(all_assets,ensure_ascii=True,separators=(',',':')).replace('<','\\u003c'))
    at=re.search(r'<head\b[^>]*>',html,re.I)
    if at: html=html[:at.end()]+patch+html[at.end():]
    else: html=patch+html
    out=args.out.resolve()
    if out==source:raise ValueError('Refusing to overwrite source index.html')
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(html,encoding='utf-8')
    print(f'SINGLE FILE (experimental): {out} ({out.stat().st_size:,} bytes, {len(all_assets)} embedded assets)')
    print('IMPORTANT: file:// execution is not guaranteed. Browser/WebGL/worker limitations remain.')

if __name__=='__main__':
    try:main()
    except (OSError,ValueError,UnicodeError) as e:sys.exit('ERROR: '+str(e))
