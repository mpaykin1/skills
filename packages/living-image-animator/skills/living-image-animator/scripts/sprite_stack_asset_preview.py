#!/usr/bin/env python3
"""Open a single genuine Grunge Horror stack.json as true 360-degree Three.js volume.
This is an ASSET PREVIEW, never a replacement for approved full-cel character/game gates.
"""
from __future__ import annotations
import argparse,base64,hashlib,json,re
from pathlib import Path
from sprite_stack_bridge import stack, StackError, fail
from sprite_stack_vendor import vendor

# Tiny transparent background used ONLY for a 3D asset inspection canvas.
BG='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4//8/AwAI/AL+uPUwSAAAAABJRU5ErkJggg=='

def preview(stack_manifest,three_module,out,azimuth=40,elevation=25):
    manifest=Path(stack_manifest).resolve()
    if not manifest.is_file() or manifest.name!='stack.json':fail('Select genuine author-created stack.json')
    source,memory=stack(manifest.parent,manifest.name)
    engine=Path(three_module).resolve()
    if not engine.is_file():fail('Official real Three.js ESM is missing; use --fetch-three')
    raw=engine.read_bytes()
    if not 200_000<len(raw)<5_000_000 or b'Data3DTexture' not in raw or b'export {' not in raw:
        fail('Unrecognized real Three.js ESM module')
    js=raw.decode('utf8');runner=Path(__file__).with_name('sprite_stack_runtime.js').read_text('utf8')
    if re.search(r'^\s*import\s',js,re.M):fail('Three.js runtime has unbundled imports')
    span=max(source['size']*source['spacing'][0],source['depth']*source['spacing'][2])
    data={'engine':'Three.js WebGL2 true sprite stack volume asset preview','version':'0.187.0',
          'objects':[{'id':'original_asset','kind':'prop','position':[0,0,0],'yaw':0,'parent':None,'motion':None,'stack':source}],
          'actors':[],'camera':{'azimuth':azimuth,'elevation':elevation,'distance':span*4,'target':[0,0,0]},
          'coverage_min':1,'coverage_actual':1,'background':BG,'fog':False,'source_actor_count':0,
          'original_source_unchanged':True,'raymarch_3d':True,'asset_preview_only':True}
    payload=json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
    page=("<!doctype html><html lang='ru'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
          "<title>Оригинальный Sprite Stack — 3D осмотр</title>"
          "<style>html,body{margin:0;width:100%;height:100%;overflow:hidden;background:#080c12;touch-action:none;font-family:system-ui}canvas{display:block}"
          "#hint{position:fixed;top:10px;left:12px;color:#cfd8d9;background:#0c1018af;padding:8px 10px;border-radius:7px;font-size:12px;pointer-events:none}"
          "#err{display:none;position:fixed;inset:0;background:#140c12;color:#f1e8d6;padding:20px;align-items:center;justify-content:center;z-index:8}"
          "</style></head><body><div id='hint'>Исходный 3D-ассет · 360° перетаскивание · масштаб: колесо/щипок</div><div id='err'></div>"
          "<script type='module'>"+js.replace('</script','<\\/script')+"\nconst LIA_STACK="+payload+";\n"+
          runner.replace('</script','<\\/script')+"</script></body></html>")
    out=Path(out).resolve();out.parent.mkdir(parents=True,exist_ok=True)
    if out.exists():fail('Use a fresh output HTML filename')
    if len(page)>170*1024*1024:fail('HTML exceeds offline budget')
    out.write_text(page,'utf8')
    return out,{'source_stack_sha256':source['sha256'],'volume_depth_slices':source['depth'],
                'volume_XY_resolution':source['size'],'gpu_bytes':memory,'asset_preview_only':True,
                'offline':True,'fullbody_character_gate_not_asserted':True}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stack',required=True,type=Path);p.add_argument('--out',required=True,type=Path)
    p.add_argument('--three-js',type=Path);p.add_argument('--fetch-three',action='store_true')
    a=p.parse_args();mod=a.three_js
    if mod is None and a.fetch_three:mod=vendor(a.out.resolve().parent/'vendor/three.module.js')
    if mod is None:p.error('Provide genuine --three-js or --fetch-three')
    print(json.dumps(preview(a.stack,mod,a.out)[1],ensure_ascii=False))
