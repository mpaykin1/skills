#!/usr/bin/env python3
"""Original Tiled JSON tile layers -> genuine offline @pixi/tilemap v5.0.2 in PixiJS.

Additive to validated full-cel HTML. Never changes actors, source PNGs or motion gates.
"""
from __future__ import annotations
import argparse, base64, hashlib, io, json, math, os, re, zipfile
from pathlib import Path
from PIL import Image
from pixijs_bridge import load_scene

class TilemapError(ValueError):pass

def reject(message):raise TilemapError('PixiJS tilemap blocked: '+str(message))
def safe_file(root,rel):
    if not isinstance(rel,str) or not rel or '\\' in rel or ':' in rel or rel.startswith('/') or any(x in ('','.','..') for x in rel.split('/')):reject('Unsafe map or tileset path')
    root=Path(root).resolve();res=(root/rel).resolve()
    if root not in res.parents or not res.is_file():reject('Missing map/source tileset '+rel)
    return res

def valid_int(x,a,b,label):
    if type(x) is not int or x<a or x>b:reject('Invalid '+label)
    return x

def compiled_tile_layers(approved_zip,scene_path):
    art=load_scene(approved_zip) # strict full-cel identities / original motion gate
    scene_path=Path(scene_path).resolve();config=json.loads(scene_path.read_text('utf8'))
    tiled=config.get('tiled')
    if not isinstance(tiled,dict):reject('This exporter requires original scene.tiled JSON map; LDtk navigation still handled upstream')
    source=safe_file(scene_path.parent,tiled.get('map_json'))
    sourcebytes=source.read_bytes()
    with zipfile.ZipFile(approved_zip) as z:
        if z.testzip():reject('Approved actor art ZIP damaged')
        if z.read('project/tiled/original_map.json')!=sourcebytes:reject('Tiled source differs from map that passed original scene gate')
        scene=json.loads(z.read('scene.json'))
        if json.loads(z.read('motion_gate.json')).get('all_actors_pass') is not True:reject('Original actor art not approved')
    tiledmap=json.loads(sourcebytes)
    if tiledmap.get('type')!='map' or tiledmap.get('orientation')!='orthogonal' or tiledmap.get('infinite'):reject('Only finite orthogonal Tiled JSON is supported')
    tw=valid_int(tiledmap.get('tilewidth'),4,256,'tile width');th=valid_int(tiledmap.get('tileheight'),4,256,'tile height')
    mw=valid_int(tiledmap.get('width'),1,1000,'map width');mh=valid_int(tiledmap.get('height'),1,1000,'map height')
    if mw*tw!=art['width'] or mh*th!=art['height']:reject('Tiled map is not registered to original illustration')
    opts=scene.get('pixi',{}).get('tilemap',{})
    if not isinstance(opts,dict) or set(opts)-{'enabled','layer_z'}:reject('pixi.tilemap supports enabled and layer_z only')
    if type(opts.get('enabled',True)) is not bool:reject('Invalid tilemap enabled flag')
    if not opts.get('enabled',True):return {'sheets':[],'layers':[],'W':art['width'],'H':art['height']},[]
    zmap=opts.get('layer_z',{})
    if not isinstance(zmap,dict):reject('pixi.tilemap.layer_z must be an object')
    tilesets=tiledmap.get('tilesets',[])
    if not isinstance(tilesets,list) or not 1<=len(tilesets)<=8:reject('Require 1..8 original image-based Tiled tilesets')
    compiled_sheets=[];source_assets=[];indices=[];firsts=[]
    for idx,ts in enumerate(tilesets):
        if not isinstance(ts,dict) or 'source' in ts or 'tiles' in ts:reject('Embedded image tilesets only; external TSX/animated tiles unsupported')
        gid=valid_int(ts.get('firstgid'),1,2_000_000_000,'firstgid')
        if gid in firsts:reject('Duplicate firstgid')
        firsts.append(gid)
        sheetpath=safe_file(source.parent,ts.get('image'))
        image=sheetpath.read_bytes()
        if len(image)>12_000_000:reject('Source tileset PNG too large')
        with Image.open(io.BytesIO(image)) as im:
            if im.format!='PNG' or im.width>4096 or im.height>4096:reject('Tileset must be genuine PNG no larger than 4096px')
            width,height=im.size
        tilew=valid_int(ts.get('tilewidth',tw),1,256,'tileset tilewidth')
        tileh=valid_int(ts.get('tileheight',th),1,256,'tileset tileheight')
        columns=valid_int(ts.get('columns'),1,1024,'tileset columns');count=valid_int(ts.get('tilecount'),1,1_000_000,'tileset count')
        margin=valid_int(ts.get('margin',0),0,256,'tileset margin');space=valid_int(ts.get('spacing',0),0,128,'tileset spacing')
        if ts.get('imagewidth')!=width or ts.get('imageheight')!=height:reject('Tileset image size differs from authored Tiled map')
        if margin*2+columns*tilew+(columns-1)*space>width:reject('Tileset columns overrun source sheet')
        lastrow=(count-1)//columns
        if margin+(lastrow+1)*tileh+lastrow*space>height:reject('Tileset rows overrun source sheet')
        compiled_sheets.append({'firstgid':gid,'tilecount':count,'columns':columns,'w':tilew,'h':tileh,'margin':margin,'spacing':space,
          'png':'data:image/png;base64,'+base64.b64encode(image).decode('ascii'),'sha256':hashlib.sha256(image).hexdigest()})
        source_assets.append((f'project/tilemap/tileset_{idx:02d}.png',image))
        indices.append((gid,gid+count,idx))
    if sorted(firsts)!=firsts:reject('Tilesets must have increasing firstgid order')
    for i in range(1,len(indices)):
        if indices[i][0]<indices[i-1][1]:reject('Overlapping source Tiled firstgid ranges')
    layers=tiledmap.get('layers')
    if not isinstance(layers,list):reject('Tiled source layers invalid')
    render=[];used=set();tiles_total=0
    for order,layer in enumerate(layers):
        if not isinstance(layer,dict) or layer.get('type')!='tilelayer' or layer.get('visible',True) is False:continue
        name=layer.get('name')
        if not isinstance(name,str) or not name or name in used:reject('Tiled tile layer names must be unique')
        used.add(name)
        if layer.get('encoding') or layer.get('compression') or 'chunks' in layer:reject('Only uncompressed Tiled tile arrays supported')
        if layer.get('width')!=mw or layer.get('height')!=mh or layer.get('x',0)!=0 or layer.get('y',0)!=0:reject('Tile layer must align to source map origin')
        if any(layer.get(k,0)!=0 for k in ('offsetx','offsety')):reject('Layer offsets not supported; bake into original Tiled geometry')
        data=layer.get('data')
        if not isinstance(data,list) or len(data)!=mw*mh:reject('Tile layer must have full explicit cell array')
        z=zmap.get(name,-50+order)
        if type(z) not in (int,float) or not math.isfinite(z) or not -500<=z<=500:reject('Invalid author-specified tile depth')
        opacity=layer.get('opacity',1)
        if type(opacity) not in (int,float) or not math.isfinite(opacity) or not 0<=opacity<=1:reject('Invalid layer opacity')
        cells=[]
        for cell,gid in enumerate(data):
            if type(gid) is not int or gid<0 or gid>=2**32:reject('Invalid authored Tiled tile ID')
            if gid==0:continue
            if gid & 0xF0000000:reject('Flipped/rotated Tiled GIDs require exact prerendered tile art; refusing distortion')
            found=next(((start,end,idx) for start,end,idx in indices if start<=gid<end),None)
            if found is None:reject('Tile GID not found in original tilesets')
            start,_,sheet_index=found;s=compiled_sheets[sheet_index];local=gid-start
            u=s['margin']+(local%s['columns'])*(s['w']+s['spacing'])
            v=s['margin']+(local//s['columns'])*(s['h']+s['spacing'])
            cells.append([sheet_index,u,v,(cell%mw)*tw,(cell//mw)*th,s['w'],s['h']])
        tiles_total+=len(cells)
        if tiles_total>180_000:reject('More than 180000 tiles: split into source maps')
        render.append({'name':name,'z':z,'opacity':float(opacity),'cells':cells})
    if not render:reject('No visible author-authored Tiled tilelayers to render')
    if set(zmap)-used:reject('Tile layer_z references missing or hidden tilelayer')
    return {'sheets':compiled_sheets,'layers':render,'W':mw*tw,'H':mh*th,'tileCount':tiles_total},source_assets

def patch_html(upstream_html,out_html,approved_zip,scene_path,tilemap_js):
    data,assets=compiled_tile_layers(approved_zip,scene_path)
    path=Path(tilemap_js) if tilemap_js else Path(os.environ.get('LIA_TILEMAP_BUNDLE',''))
    if not tilemap_js and not os.environ.get('LIA_TILEMAP_BUNDLE'):reject('Genuine @pixi/tilemap v5 browser bundle unavailable')
    path=path.resolve()
    if not path.is_file():reject('Tilemap browser module missing')
    js=path.read_bytes()
    if not 30_000<=len(js)<=5_000_000 or b'CompositeTilemap' not in js:reject('Unrecognized original @pixi/tilemap browser library')
    code=js.decode('utf8')
    html=Path(upstream_html).resolve().read_text('utf8')
    marker='<script>const LIVING_SCENE='
    if html.count(marker)!=1 or html.count('    const avatars=[];')!=1 or 'PIXI' not in html:reject('Approved previous PixiJS + particles HTML template required')
    code=re.sub(r'</script',r'<\\/script',code,flags=re.I)
    html=html.replace(marker,'<script>/* @pixi/tilemap 5.0.2, MIT attribution retained in source archive. */\n'+code+'</script>'+marker,1)
    js_data=json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
    addition=r'''    // Genuine @pixi/tilemap: source-only Tiled tile GIDs, source pixels, source camera.
    const LIA_TILEMAP=__DATA__;
    const TilemapNS=(window.PIXI && PIXI.tilemap && PIXI.tilemap.CompositeTilemap)
      ? PIXI.tilemap : (window.pixi_tilemap && window.pixi_tilemap.CompositeTilemap)
      ? window.pixi_tilemap : (window.PixiTilemap && window.PixiTilemap.CompositeTilemap)
      ? window.PixiTilemap : null;
    if(!TilemapNS)throw new Error('Genuine @pixi/tilemap 5 UMD not initialized');
    const tileSheets=[];
    for(const s of LIA_TILEMAP.sheets){
      tileSheets.push(new PIXI.Texture({source:await sourceFromData(s.png)}));
    }
    const realTileLayers=[];
    for(const layer of LIA_TILEMAP.layers){
      // 4096 cels per batch avoids 16-bit tile index limits; no sprite animation is altered.
      for(let i=0;i<layer.cells.length;i+=4096){
        const tiles=new TilemapNS.CompositeTilemap();
        tiles.zIndex=layer.z;tiles.alpha=layer.opacity;world.addChild(tiles);
        for(const cell of layer.cells.slice(i,i+4096)){
          const [sheet,u,v,x,y,w,h]=cell;
          tiles.tile(tileSheets[sheet],x,y,{u,v,tileWidth:w,tileHeight:h});
        }
        realTileLayers.push(tiles);
      }
    }
    window.__livingTilemap={engine:'@pixi/tilemap 5.0.2',layers:LIA_TILEMAP.layers.length,
      tileCount:LIA_TILEMAP.tileCount,actorPixelsModified:0,originalTilesetHashes:LIA_TILEMAP.sheets.map(x=>x.sha256)};
'''.replace('__DATA__',js_data)
    html=html.replace('    const avatars=[];',addition+'    const avatars=[];',1)
    if len(html.encode('utf8'))>150*1024*1024:reject('Standalone tilemap HTML exceeds 150MiB browser budget')
    target=Path(out_html).resolve();target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(html,'utf8')
    return target,assets,{'original_tile_count':data['tileCount'],'tile_layers':len(data['layers']), 'sheets':len(data['sheets']), 'characters_unchanged':True,'offline':True}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--approved-zip',type=Path,required=True);p.add_argument('--scene',type=Path,required=True)
    p.add_argument('--upstream-html',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--tilemap-js',type=Path)
    a=p.parse_args();print(json.dumps(patch_html(a.upstream_html,a.out,a.approved_zip,a.scene,a.tilemap_js)[2],ensure_ascii=False))
