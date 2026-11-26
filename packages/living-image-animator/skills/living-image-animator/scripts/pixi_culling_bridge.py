#!/usr/bin/env python3
"""Source-faithful PixiJS v8 CullerPlugin spatial batching for approved Tiled GPU scene.

Additional offline variant, never replaces existing playable or GIF outputs.
Only terrain chunks are culled; avatars, physics, actor cels & timing unchanged.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import zipfile

class CullingBridgeError(ValueError):
    pass


def fail(message):
    raise CullingBridgeError('PixiJS 8 culling blocked: '+str(message))


def config_from_approved(approved_zip:Path):
    with zipfile.ZipFile(approved_zip) as z:
        if z.testzip() is not None:fail('Corrupted approved animation ZIP')
        try:
            cfg=json.loads(z.read('scene.json'))
            approved=json.loads(z.read('motion_gate.json'))
            tiled=json.loads(z.read('project/tiled/original_map.json'))
        except (KeyError,ValueError) as exc:fail('Missing original scene, motion gate or Tiled map: '+str(exc))
    if approved.get('all_actors_pass') is not True:
        fail('Full-body frame and identity gates did not pass')
    pixi=cfg.get('pixi',{})
    if not isinstance(pixi,dict):fail('Invalid original pixi scene settings')
    culling=pixi.get('culling',{})
    if not isinstance(culling,dict) or set(culling)-{'chunk_tiles','enabled'}:
        fail('pixi.culling supports only chunk_tiles and enabled')
    if culling.get('enabled',True) is not True:
        fail('Culling disabled in source; use original tilemap HTML instead')
    chunks=culling.get('chunk_tiles',32)
    if type(chunks) is not int or not 16<=chunks<=64:
        fail('chunk_tiles must be integer in range 16..64')
    if tiled.get('orientation')!='orthogonal' or tiled.get('infinite'):
        fail('Only source-registered finite orthogonal maps supported')
    w=tiled.get('tilewidth');h=tiled.get('tileheight')
    if not all(type(v) is int and 4<=v<=256 for v in (w,h)):
        fail('Missing exact original Tiled tile dimensions')
    return {'tiles_per_chunk':chunks,'grid_width':w,'grid_height':h,
            'viewport_margin':0,'dynamic_actor_culling':False,
            'tile_renderer':'original @pixi/tilemap 5.0.2',
            'culler':'native PixiJS 8.23.0 CullerPlugin'}


def once(src,needle,replacement,label):
    qty=src.count(needle)
    if qty!=1:fail(f'Changed upstream HTML at {label}: found {qty} markers (expected 1)')
    return src.replace(needle,replacement,1)


def patch_html(upstream_html:Path,out_html:Path,approved_zip:Path):
    """Convert arbitrary 4096-tile streams into camera-culled spatial chunks.

    The original source tiles & drawn actor atlas remain literal, unmodified
    embedded HTML data. Only tile placement and renderer culling are changed.
    """
    config=config_from_approved(approved_zip)
    src=Path(upstream_html).read_text('utf8')
    if src.count('<script>const LIVING_SCENE=')!=1:
        fail('Input is not the original approved offline PixiJS HTML')
    if not all(s in src for s in ('const LIA_TILEMAP=','window.__livingTilemap=',
                                  'window.pixi_viewport','const LIA_FILTERS=',
                                  'const avatars=[];')):
        fail('Real tilemap, camera, filters and original full-cel avatars are mandatory')
    if 'PIXI.extensions.add(PIXI.CullerPlugin)' in src:fail('Already culled input; supply original tilemap HTML')
    init='    const app = new PIXI.Application();'
    injected='''    // Real PixiJS v8 CullerPlugin from the ALREADY bundled official PixiJS engine.
    if(!PIXI.CullerPlugin || !PIXI.extensions || !PIXI.Rectangle)
      throw new Error('Official PixiJS 8 CullerPlugin missing; no fake visibility fallback');
    PIXI.extensions.add(PIXI.CullerPlugin);
    const app = new PIXI.Application();'''
    src=once(src,init,injected,'application construction')
    # Must account for CURRENT camera world transforms, no 1-frame missing tiles.
    old='    await app.init({resizeTo: window, backgroundColor: 0x080e17,'
    new='    await app.init({resizeTo: window, culler:{updateTransform:true}, backgroundColor: 0x080e17,'
    src=once(src,old,new,'application initialization')
    mark='    // Genuine @pixi/tilemap: source-only Tiled tile GIDs, source pixels, source camera.'
    pos=src.find(mark)
    end=src.find('    const avatars=[];',pos)
    if pos<0 or end<0 or src.count(mark)!=1:
        fail('Tilemap original block markers missing; original character animation preserved')
    existing=src[pos:end]
    if ('const LIA_TILEMAP=' not in existing or 'world.addChild(tiles)' not in existing or
         'window.__livingTilemap=' not in existing):
        fail('Original GPU tilemap changed; refusing unsafe replacement')
    cfg=json.dumps(config,separators=(',',':'),ensure_ascii=False).replace('<','\\u003c')
    replacement=r'''    // Native PixiJS 8 CullerPlugin spatially batches ONLY terrain; all actors stay live.
    const LIA_CULL_CONFIG=__SETTINGS__;
    const LIA_TILEMAP=__TILEMAP__;
    const TilemapNS=(window.PIXI && PIXI.tilemap && PIXI.tilemap.CompositeTilemap)
      ? PIXI.tilemap : (window.pixi_tilemap && window.pixi_tilemap.CompositeTilemap)
      ? window.pixi_tilemap : (window.PixiTilemap && window.PixiTilemap.CompositeTilemap)
      ? window.PixiTilemap : null;
    if(!TilemapNS)throw new Error('Original genuine @pixi/tilemap 5 UMD missing');
    const tileSheets=[];
    for(const source of LIA_TILEMAP.sheets){
      tileSheets.push(new PIXI.Texture({source:await sourceFromData(source.png)}));
    }
    const realTileLayers=[];
    let chunkCount=0;
    const spanX=LIA_CULL_CONFIG.tiles_per_chunk*LIA_CULL_CONFIG.grid_width;
    const spanY=LIA_CULL_CONFIG.tiles_per_chunk*LIA_CULL_CONFIG.grid_height;
    for(const layer of LIA_TILEMAP.layers){
      // A source-authored tile is NEVER copied or distorted: same UV and tile coordinates.
      const chunks=new Map();
      for(const cell of layer.cells){
        const [sheet,u,v,x,y,w,h]=cell;
        const key=Math.floor(x/spanX)+','+Math.floor(y/spanY);
        let chunk=chunks.get(key);
        if(!chunk){chunk={cells:[],minX:Infinity,minY:Infinity,maxX:-Infinity,maxY:-Infinity};chunks.set(key,chunk);}
        chunk.cells.push(cell);
        chunk.minX=Math.min(chunk.minX,x);chunk.minY=Math.min(chunk.minY,y);
        chunk.maxX=Math.max(chunk.maxX,x+w);chunk.maxY=Math.max(chunk.maxY,y+h);
      }
      for(const chunk of chunks.values()){
        // Bound this one spatial region, not the entire world or animated inhabitants.
        const mesh=new TilemapNS.CompositeTilemap();
        mesh.zIndex=layer.z;mesh.alpha=layer.opacity;
        mesh.cullable=true;
        mesh.cullableChildren=false;
        mesh.cullArea=new PIXI.Rectangle(chunk.minX,chunk.minY,
          Math.max(1,chunk.maxX-chunk.minX),Math.max(1,chunk.maxY-chunk.minY));
        for(const cell of chunk.cells){
          const [sheet,u,v,x,y,w,h]=cell;
          mesh.tile(tileSheets[sheet],x,y,{u,v,tileWidth:w,tileHeight:h});
        }
        world.addChild(mesh);realTileLayers.push(mesh);
        chunkCount++;
        if(chunkCount>4096)throw new Error('Source map too sparse for bounded chunk culling; increase chunk_tiles');
      }
    }
    window.__livingTilemap={engine:'@pixi/tilemap 5.0.2',layers:LIA_TILEMAP.layers.length,
      tileCount:LIA_TILEMAP.tileCount,actorPixelsModified:0,
      originalTilesetHashes:LIA_TILEMAP.sheets.map(x=>x.sha256)};
    window.__livingCulling={engine:'PixiJS 8.23.0 CullerPlugin',tileChunks:chunkCount,
      actorVisibilityCulled:false,sourceTilesUnchanged:true};
'''
    # Source Tiled map data is part of verified upstream HTML: extract expression
    # verbatim to prevent any possibility of rewriting/touching original UVs/PNGs.
    matched=re.search(r'    const LIA_TILEMAP=(\{[^\n]*\});\n',existing)
    if not matched:fail('Expected original JSON Tiled tile data embedded on exactly one line')
    payload=matched.group(1)
    replacement=replacement.replace('__SETTINGS__',cfg).replace('__TILEMAP__',payload)
    src=src[:pos]+replacement+src[end:]
    if src.count('    const avatars=[];')!=1 or src.count('const LIVING_SCENE=')!=1:
        fail('Original actor timeline unexpectedly altered')
    if len(src.encode('utf8'))>150*1024*1024:fail('Offline HTML >150MiB')
    out_html=Path(out_html).resolve();out_html.parent.mkdir(parents=True,exist_ok=True)
    tmp=out_html.with_suffix('.tmp');tmp.write_text(src,'utf8');os.replace(tmp,out_html)
    return out_html,{'engine':'PixiJS 8.23.0 native CullerPlugin',
        'source_tiles_unchanged':True,'actor_cels_untouched':True,'chunk_tiles':config['tiles_per_chunk'],
        'native_runtime_already_pinned':True,'offline':True,
        'sha256':hashlib.sha256(out_html.read_bytes()).hexdigest()}

if __name__=='__main__':
    a=argparse.ArgumentParser()
    a.add_argument('--upstream-html',type=Path,required=True)
    a.add_argument('--approved-zip',type=Path,required=True)
    a.add_argument('--out',type=Path,required=True)
    q=a.parse_args()
    print(json.dumps(patch_html(q.upstream_html,q.out,q.approved_zip)[1],ensure_ascii=False))
