#!/usr/bin/env python3
"""Additional offline PixiJS v8 atlas player over the existing STRICT PixiJS exporter.

Reads the original already-approved full-cel source ZIP through the official
living-image pixijs_bridge.load_scene; never weakens original validation or
changes character pixels. Uses the *same genuine locally supplied* PixiJS v8
bundle that the existing offline standalone player requires.
"""
from __future__ import annotations
import base64
import hashlib
import io
import json
import math
import re
import zipfile
from pathlib import Path
from PIL import Image
from pixijs_bridge import load_scene, bundle_path, PIXILICENSE

class AtlasError(ValueError):pass

def decode_png(uri, width, height):
    if not isinstance(uri,str) or not uri.startswith('data:image/png;base64,'):
        raise AtlasError('Only original PNG pixel data from approved ZIP may be rendered')
    data=base64.b64decode(uri.split(',',1)[1],validate=True)
    with Image.open(io.BytesIO(data)) as im:
        if im.format!='PNG' or im.size!=(width,height):
            raise AtlasError('Authored sprite dimensions mismatch original actor box')
        rgba=im.convert('RGBA')
        lo,hi=rgba.getchannel('A').getextrema()
        if lo==255 or hi==0:raise AtlasError('Invalid opaque/empty character pose')
        return rgba

def pack_actor(a, originals, *, limit=4096):
    x,y,w,h=a['box']
    if w<8 or h<8 or w>limit or h>limit:raise AtlasError('Invalid character atlas dimensions')
    frames=[decode_png(originals[rel],w,h) for rel in a['frames']]
    cols=max(1,min(8,limit//w));rows=max(1,limit//h);limitcount=cols*rows
    if len(frames)>720:raise AtlasError('Too many cels in one actor')
    encoded=[];rects=[]
    for start in range(0,len(frames),limitcount):
        page=frames[start:start+limitcount]
        countcols=min(cols,len(page));countrows=math.ceil(len(page)/countcols)
        atlas=Image.new('RGBA',(countcols*w,countrows*h))
        for i,im in enumerate(page):
            left=(i%countcols)*w;top=(i//countcols)*h
            atlas.paste(im,(left,top))
            if atlas.crop((left,top,left+w,top+h)).tobytes()!=im.tobytes():
                raise AtlasError('Atlas packer changed original character RGB/alpha pixels')
            rects.append([len(encoded),left,top])
        stream=io.BytesIO();atlas.save(stream,'PNG',optimize=True)
        encoded.append('data:image/png;base64,'+base64.b64encode(stream.getvalue()).decode())
    return {'id':a['id'],'box':a['box'],'z':a['z'],'phase':a['phase'],
            'frames':rects,'sheets':encoded,
            'path':a['locomotion']['path'] if a['locomotion'] else None}

def build_atlas(approved_zip:Path,out:Path,pixi_js=None,*,fps=24,seconds=48):
    if type(fps) is not int or fps<24 or type(seconds) is not int or not 40<=seconds<=60:
        raise AtlasError('Unsupported frame rate or duration; preserve original 24+ fps / 40-60 sec gate')
    approved_zip=Path(approved_zip).resolve()
    original=load_scene(approved_zip) # same strict gate as existing offline HTML exporter
    with zipfile.ZipFile(approved_zip) as z:
        cfg=json.loads(z.read('scene.json'))
    px=cfg.get('pixi',{})
    if not isinstance(px,dict):raise AtlasError('Optional pixi configuration must be an object')
    weather=px.get('weather')
    if weather not in (None,'snow','rain'):raise AtlasError('Unrecognized source-defined PixiJS atmosphere')
    parallax=px.get('parallax',{})
    if not isinstance(parallax,dict):raise AtlasError('pixi.parallax must map source layer paths to factors')
    planes=[]
    for layer in original['layers']:
        path=layer['png'];factor=parallax.get(path,1)
        if type(factor) not in (int,float) or not math.isfinite(factor) or not 0<=factor<=2:
            raise AtlasError('Parallax factor outside physical 0..2 range')
        planes.append({'z':layer['z'],'parallax':factor,'data':original['planes'][path]})
    cast=[pack_actor(a,original['spriteData']) for a in original['actors']]
    if sum(len(a['frames'])*a['box'][2]*a['box'][3] for a in cast)>80_000_000:
        raise AtlasError('Browser full-cel sprite budget exceeded; keep original art but split scene')
    realpath,engine=bundle_path(pixi_js)
    # Browser JS is from the actual pinned official engine; never a Canvas substitute.
    engine=re.sub(r'</script',r'<\\/script',engine,flags=re.I)
    script=Path(__file__).resolve().with_name('pixi_runtime.js').read_text('utf8')
    script=re.sub(r'</script',r'<\\/script',script,flags=re.I)
    scene={'schema':'lia-pixijs-1','W':original['width'],'H':original['height'],
           'fps':fps,'seconds':seconds,'actors':cast,
           'background':original['background'],'layers':planes,
           'weather':weather,'valid_gate':True,'no_deformation':True,'version':'8.23.0'}
    payload=json.dumps(scene,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
    license_text=PIXILICENSE.replace('-->','--&gt;')
    html=("<!doctype html><html lang='ru'><head><meta charset='utf-8'>"
      "<meta name='viewport' content='width=device-width,initial-scale=1,user-scalable=no'>"
      "<title>Living Image Animator — PixiJS 2.5D Atlas</title>"
      "<style>html,body{margin:0;width:100%;height:100%;overflow:hidden;background:#080e17;touch-action:none}canvas{display:block}#err{display:none;position:fixed;inset:0;color:#eee;background:#080e17;font:15px system-ui;align-items:center;justify-content:center;text-align:center;padding:24px;box-sizing:border-box}</style>"
      "</head><body><div id='err'></div><!--"+license_text+"-->"
      "<script>"+engine+"</script><script>const LIVING_SCENE="+payload+";\n"+script+"</script></body></html>")
    out=Path(out).resolve();out.parent.mkdir(parents=True,exist_ok=True)
    if len(html.encode('utf8'))>150*1024*1024:
        raise AtlasError('Offline HTML too large for browser; source split required')
    out.write_text(html,'utf8')
    return out,{'characters':len(cast),'atlas_count':sum(len(c['sheets']) for c in cast),
                'original_frames':sum(len(c['frames']) for c in cast),
                'offline':True,'engine_from':str(realpath),'character_deformation':False}
