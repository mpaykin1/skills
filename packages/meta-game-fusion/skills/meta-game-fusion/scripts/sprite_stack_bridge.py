#!/usr/bin/env python3
"""META GAME FUSION sprite-stack compiler: TRUE planar RGBA slices from a coherent volume.

Input: approved <source>/<asset>/stack.json + layers/000.png... . For animation,
optional <asset>/actions/<action>/<frame-index>/layers/000.png... . This CLI
NEVER slices a single image into stripes or mislabels extrusion as full 3D.

Also creates original *illustrative* scene props from analytical 3D volumes for
new concept games with no approved external artwork. It never replaces approved
characters, architectural facades, animation cells, or imported GLB sources.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import re
from pathlib import Path
import shutil
import sys
from typing import Any

try:
    from PIL import Image, ImageFilter
except ImportError:
    raise SystemExit('sprite_stack_bridge requires Pillow (pip install Pillow numpy)')
try:
    import numpy as np
except ImportError:
    raise SystemExit('sprite_stack_bridge requires NumPy (pip install Pillow numpy)')

SCHEMA = 'meta-game-fusion.sprite-stacking.v1'
ID_RE = re.compile(r'^[a-z][a-z0-9-]{1,42}$')
MAX_ATLAS_PIXELS = 16_000_000
MAX_TOTAL = 25_000_000
MAX_SLICES = 128
MIN_SLICES = 12


def digest(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def safe_child(path: Path, parent: Path) -> Path:
    if path.is_symlink() or parent.resolve() not in path.resolve().parents:
        raise ValueError('Unsafe source path (symlink or traversal)')
    return path


def positive_dimensions(d: dict) -> tuple[float,float,float]:
    a=d.get('dimensions')
    if not isinstance(a,list) or len(a)!=3 or any(not isinstance(x,(int,float)) or isinstance(x,bool) or not math.isfinite(x) or x<=0 or x>60 for x in a):
        raise ValueError('dimensions must be finite positive [worldX,worldY,worldZ] <=60')
    return tuple(float(x) for x in a)


def pack_frame(paths: list[Path], output: Path, tile: int) -> tuple[int,int]:
    n=len(paths)
    if not MIN_SLICES<=n<=MAX_SLICES:raise ValueError('Allowed slice count: 12..128')
    columns=max(1,math.ceil(math.sqrt(n)))
    rows=math.ceil(n/columns)
    if columns*rows*tile*tile > MAX_ATLAS_PIXELS:raise ValueError('Atlas GPU memory budget exceeded')
    atlas=Image.new('RGBA',(columns*tile,rows*tile),(0,0,0,0))
    alphas=[];voxels=[]
    for i,path in enumerate(paths):
        with Image.open(path) as src:
            if src.mode!='RGBA' or src.size!=(tile,tile):
                raise ValueError(f'{path.name}: RGBA square {tile}x{tile} required')
            if src.getbbox():alphas.append(i)
            atlas.alpha_composite(src,(i%columns*tile,i//columns*tile))
            voxels.append(np.asarray(src,dtype=np.uint8))
    if len(alphas)<MIN_SLICES//3:raise ValueError('Not enough nonempty slices for true volume')
    output.parent.mkdir(parents=True,exist_ok=True)
    atlas.save(output,'PNG',compress_level=9,optimize=True)
    # Exactly horizontal view would make infinitesimally thin planes invisible.
    # Derive four *orthographic side projections of the same real stack*, not
    # invented independent sides, and use them only near the horizon.
    vol=np.stack(voxels,axis=0) # (layer,z,x,rgba)
    opaque=vol[...,3]>100
    front_idx=np.argmax(opaque,axis=1)
    back_idx=tile-1-np.argmax(opaque[:,::-1,:],axis=1)
    front=np.take_along_axis(vol,front_idx[:,None,:,None],axis=1)[:,0,:,:]
    back=np.take_along_axis(vol,back_idx[:,None,:,None],axis=1)[:,0,::-1,:]
    front[...,3]*=opaque.any(axis=1)
    back[...,3]*=opaque.any(axis=1)[:,::-1]
    left_idx=np.argmax(opaque,axis=2)
    right_idx=tile-1-np.argmax(opaque[:,:,::-1],axis=2)
    left=np.take_along_axis(vol,left_idx[:,:,None,None],axis=2)[:,:,0,:]
    right=np.take_along_axis(vol,right_idx[:,:,None,None],axis=2)[:,:,0,:]
    left[...,3]*=opaque.any(axis=2)
    right[...,3]*=opaque.any(axis=2)
    # Screen right axes are mirrored for the opposite side views.
    side_views=[front, np.flip(right,axis=1), back, left]
    sheet=np.zeros((n,4*tile,4),dtype=np.uint8)
    for direction,view in enumerate(side_views):
        sheet[:,direction*tile:(direction+1)*tile,:]=view[::-1]
    Image.fromarray(sheet,'RGBA').save(output.with_name(output.stem+'-views.png'),'PNG',compress_level=9,optimize=True)
    return columns,rows


def _collect_layers(folder: Path,root:Path) -> list[Path]:
    if not folder.is_dir():raise ValueError('Missing volume slice directory: '+str(folder))
    files=sorted(folder.glob('*.png'))
    if not MIN_SLICES<=len(files)<=MAX_SLICES:raise ValueError('Expected 12..128 sequential PNG slices')
    if any(p.name!=f'{i:03d}.png' for i,p in enumerate(files)):
        raise ValueError('Slices must be numbered 000.png,001.png,... without gaps')
    return [safe_child(p,root) for p in files]


def compile_asset(folder: Path, source: Path, out: Path)->dict:
    config_path=safe_child(folder/'stack.json',source)
    c=json.loads(config_path.read_text('utf-8'))
    ident=folder.name
    if not ID_RE.fullmatch(ident):raise ValueError('Asset id not a safe lowercase slug: '+ident)
    if c.get('approved_for_reuse') is not True:
        raise ValueError('Each imported sprite stack needs explicit approved_for_reuse=true: '+ident)
    if c.get('license') not in ('CC0-1.0','CC-BY-4.0','MIT','proprietary-user-owned','approved-private'):
        raise ValueError('Imported sprite slice license missing/unauthorized: '+ident)
    base=_collect_layers(folder/'layers',source)
    first=Image.open(base[0]);size=first.size;mode=first.mode;first.close()
    tile=size[0]
    if 'dimensions' in c:
        dims=positive_dimensions(c)
        pivot=c.get('pivot',[0,0,0])
    else:
        spacing=c.get('spacing')
        if not isinstance(spacing,list) or len(spacing)!=3 or any(not isinstance(x,(int,float)) or isinstance(x,bool) or not math.isfinite(x) or x<=0 or x>2 for x in spacing):
            raise ValueError('Legacy Sprite Stacking Grunge stack.json requires positive spacing[dx,dy,dz]')
        dims=positive_dimensions({'dimensions':[tile*spacing[0],len(base)*spacing[2],tile*spacing[1]]})
        old_pivot=c.get('pivot',[0,0,0])
        if not isinstance(old_pivot,list) or len(old_pivot)!=3:
            raise ValueError('Expected original pivot [X,Y,Z]')
        pivot=[old_pivot[0],old_pivot[2],old_pivot[1]]
    if mode!='RGBA' or size[0]!=size[1] or not 32<=tile<=512:
        raise ValueError('Input must be 32..512px square RGBA PNG slices')
    frames={'idle':[base]}
    acts=folder/'actions'
    if acts.exists():
        for action in sorted(acts.iterdir()):
            if action.is_symlink() or not action.is_dir() or not ID_RE.fullmatch(action.name):
                raise ValueError('Unsafe action folder')
            sequences=[]
            for frame in sorted(action.iterdir()):
                if frame.is_symlink() or not frame.is_dir() or not re.fullmatch(r'\d{3}',frame.name):
                    raise ValueError('Invalid pose frame folder')
                seq=_collect_layers(frame/'layers',source)
                if len(seq)!=len(base):raise ValueError('Frame slice count mismatch')
                sequences.append(seq)
            if not 1<=len(sequences)<=24:raise ValueError('Only 1..24 complete pose frames')
            frames[action.name]=sequences
    # Preserve raw input slice sources. No original is changed.
    asset={'id':ident,'dimensions':list(dims),'sliceCount':len(base),'tile':tile,
           'source':'approved-volume-slices','sourceConfigSha256':digest(config_path),
           'origin':c.get('origin','artist-authored-or-source-derived'),
           'pivot':pivot,'license':c['license'],'approved_for_reuse':True,
           'actions':{}}
    total=0
    for action,sequences in frames.items():
        produced=[]
        for fi,seq in enumerate(sequences):
            name=f'{ident}-{action}-{fi:03d}.png'
            output=out/name
            columns,rows=pack_frame(seq,output,tile)
            total+=output.stat().st_size
            if total>MAX_TOTAL:raise ValueError('Asset output size over 25MB budget')
            produced.append({'atlas':name,'sha256':digest(output), 'columns':columns,'rows':rows,
                'views':name[:-4]+'-views.png','viewsSha256':digest(output.with_name(output.stem+'-views.png')),
                'sourceSlicesSha256':[digest(p) for p in seq]})
        asset['actions'][action]=produced
    if not isinstance(asset['pivot'],list) or len(asset['pivot'])!=3 or any(not isinstance(x,(int,float)) or not math.isfinite(x) for x in asset['pivot']):
        raise ValueError('Invalid pivot')
    return asset


def compile_source(source:Path,out:Path,*,preserve_existing:bool=False)->dict:
    if source.is_symlink() or not source.is_dir():raise ValueError('Source folder missing or symlink')
    root=source.resolve(strict=True)
    if out.exists() and not preserve_existing:raise ValueError('Output already exists; do not overwrite')
    previous=[]
    if preserve_existing:
        p=out/'manifest.json'
        if p.is_file():
            old=json.loads(p.read_text('utf-8'))
            if old.get('schema')!=SCHEMA:raise ValueError('Bad existing stack manifest')
            previous=list(old.get('assets',[]))
    out.mkdir(parents=True,exist_ok=True)
    assets=list(previous)
    for asset in sorted(root.iterdir()):
        if asset.is_symlink():raise ValueError('Symlink asset is blocked')
        if asset.is_dir():
            if asset.name in {v['id'] for v in assets}:
                raise ValueError('Refusing to overwrite existing stack: '+asset.name)
            assets.append(compile_asset(asset,root,out))
    if not assets:raise ValueError('No volume slice assets found')
    manifest={'schema':SCHEMA,'coordinateSystem':'X-right/Y-up/Z-forward','atlasColorSpace':'sRGB',
              'alphaMode':'MASK','mode':'horizontal-physical-slices','assets':assets}
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n','utf-8')
    return manifest


# Scene decor below is GENERATED FROM ACTUAL 3D ANALYTIC VOLUMES, rather than
# stretching the same picture N times. This art is only for new concept worlds,
# never a replacement for a user-provided character / vehicle / building.
WORLD_ASSETS = {
 'rock':([2.2,1.45,1.95],64,90),
 'rubble':([1.9,.95,1.85],52,90),
 'tree':([2.4,5.2,2.4],88,96),
 'pillar':([1.25,3.5,1.25],76,96),
 'gothic-arch':([3.7,4.25,1.15],86,96),
 'lantern':([.8,1.8,.8],58,90),
 'crate':([1.12,1.12,1.12],56,90),
 'shrub':([1.9,1.25,1.8],55,90),
 'spire':([1.6,7,1.6],90,96),
 'wanderer':([1.25,2.05,1.1],72,96),
 'sentinel-blue':([1.2,1.9,1.0],70,96),
 'sentinel-violet':([1.2,1.9,1.0],70,96),
}
COLORS = {'rock':(48,57,66),'rubble':(69,68,64),'tree':(36,58,54),
          'pillar':(80,75,76),'gothic-arch':(77,78,83),'lantern':(112,98,82),
          'crate':(95,78,62),'shrub':(47,69,65),'spire':(50,60,70),
          'wanderer':(110,62,62),'sentinel-blue':(42,64,78),
          'sentinel-violet':(59,47,75)}


def analytical_slice(ident:str,i:int,n:int,tile:int,seed:int,action:str='idle',phase:float=0)->Image.Image:
    # Texture is continuous in world coordinates across height; no tiled noise.
    yy=(i+.5)/n; x=np.linspace(-1,1,tile,dtype=np.float32);
    X,Z=np.meshgrid(x,x)
    jitter=(.055*np.sin(X*11+Z*5.7+yy*13+seed*.071)
            +.029*np.sin(X*23-Z*17+yy*8+seed*.017)
            +.012*np.sin(X*37+Z*29+yy*24))
    R=np.sqrt((X*.98+.035*np.sin(yy*8+seed))**2+(Z*.92)**2)
    if ident=='rock':
        radius=.78*np.sqrt(max(.008,1-((yy-.37)/.65)**2))
        mask=R<radius+jitter
    elif ident=='rubble':
        a=(X+.27)**2+(.95*Z-.1)**2; b=(X-.34)**2+(Z+.15)**2
        mask=(a < (.52*(1-yy**1.6)+jitter)**2) | (b < (.64*(1-yy**1.2)+jitter)**2)
    elif ident=='tree':
        trunk=(R < .10+.024*np.sin(yy*9+seed*.03))
        r=.81*np.sqrt(max(.0001,1-((yy-.73)/.34)**2))
        leaves=((yy>.38)&(R<r+jitter*2))
        mask=trunk|leaves
    elif ident=='pillar':
        slab=(np.maximum(np.abs(X),np.abs(Z))<(.49 if yy<.13 or .85<yy<.91 else .34)+jitter*.36)
        broken=(yy<.88+.10*np.sin(X*8+Z*12+seed)*np.sin(Z*9+seed))
        mask=slab&broken
    elif ident=='gothic-arch':
        W=np.abs(X);depth=np.abs(Z)<.65+jitter*.22
        open_width=.47
        arch_height=.58+.15*np.sqrt(np.maximum(0,1-(X/open_width)**2))
        opening=(W<open_width)&(yy<arch_height)
        battlement=(yy<.90+.055*np.sin(X*22+seed*.09))
        mask=depth&(W<.93+jitter*.25)&(~opening)&battlement
    elif ident=='lantern':
        edge=(np.abs(X)>.48)&(np.abs(X)<.61)&(np.abs(Z)>.48)&(np.abs(Z)<.61)
        cell=(R<.38)&(yy>.24)&(yy<.70)
        foot=(yy<.18)&(R<.47)
        lid=(yy>.77)&(yy<.91)&(R<.57*(1.05-yy))
        mask=edge|cell|foot|lid
    elif ident=='crate':
        mask=(np.maximum(np.abs(X),np.abs(Z))<.68+jitter*.1)&(yy<.92+jitter*.35)
    elif ident=='shrub':
        rr=.83*np.sqrt(max(.001,1-((yy-.43)/.60)**2))
        mask=R<rr+jitter*2.1
    elif ident=='spire':
        radius=.33*(1-yy*.75)+.18*(yy<.1)+.10*(.54<yy<.60)
        mask=R<radius+jitter*.2
    elif ident in ('wanderer','sentinel-blue','sentinel-violet'):
        move=math.sin(phase) if action in ('walk','patrol','return') else 0.0
        breath=.012*math.sin(phase) if action=='idle' else 0.0
        torso= (yy>.19)&(yy<.76)&(R<.52-.24*yy+breath+jitter*.28)
        leftleg= (yy<.28)&(((X+.20-move*.11)**2)/.042 + (Z+.015)**2/.058 < 1)
        rightleg=(yy<.28)&(((X-.20+move*.11)**2)/.042 + (Z+.015)**2/.058 < 1)
        head=(yy>.73)&(((X-.02)**2+(Z+.11)**2)/.15 + ((yy-.835)/.155)**2<1)
        armL=(yy>.23)&(yy<.69)&((X+.44)**2+(Z-.07-move*.14)**2 < .105**2)
        armR=(yy>.23)&(yy<.69)&((X-.44)**2+(Z-.07+move*.14)**2 < .105**2)
        staff=(ident=='wanderer') & (yy>.05)&(yy<.95)&((X-.69)**2+(Z+.14)**2<.06**2)
        mask=torso|leftleg|rightleg|head|armL|armR|staff
    else:raise ValueError('Unknown volume model')
    base=np.asarray(COLORS[ident],dtype=np.float32)
    n3=(np.sin(X*18+Z*26+yy*21+seed*.29)*.47
        +np.sin(X*59-Z*47+yy*35+seed*.13)*.16
        +np.sin(X*9+Z*7+yy*15+seed*.71)*.35)
    rust=(np.sin(X*37+Z*19+yy*31+seed*.5)*np.sin(X*13-Z*32+yy*17))>.50
    d=(.88+yy*.17)+n3*.20
    color=np.empty((tile,tile,4),dtype=np.uint8)
    for j in range(3):color[:,:,j]=np.clip(base[j]*d,0,255).astype(np.uint8)
    if ident in ('pillar','gothic-arch','spire','crate'):
        color[:,:,:3]=np.where(rust[...,None],np.maximum(0,color[:,:,:3].astype(np.int16)-np.array([11,1,0])[None,None,:]),color[:,:,:3]).astype(np.uint8)
    if ident=='tree':
        trunk=(R<.13)&(yy<.70)
        color[:,:,:3]=np.where(trunk[...,None],np.array([77,61,48],np.uint8),color[:,:,:3])
    if ident=='lantern':
        cell=(R<.38)&(yy>.24)&(yy<.70)
        color[:,:,:3]=np.where(cell[...,None],np.array([193,126,65],np.uint8),color[:,:,:3])
    if ident in ('wanderer','sentinel-blue','sentinel-violet'):
        head=(yy>.73)&(((X-.02)**2+(Z+.11)**2)/.15 + ((yy-.835)/.155)**2<1)
        hood= head & (Z>-.25)
        face=head & ~hood
        color[:,:,:3]=np.where(hood[...,None],np.array([35,34,43],np.uint8),color[:,:,:3])
        color[:,:,:3]=np.where(face[...,None],np.array([161,127,107],np.uint8),color[:,:,:3])
        # Geometry-backed eye/lantern glints, preserving the same volume and identity.
        eyes=face&(yy>.79)&(yy<.84)&(abs(X)>.065)&(abs(X)<.15)&(Z<-.25)
        glint=[244,169,100] if ident=='wanderer' else ([249,180,116] if ident=='sentinel-blue' else [178,161,255])
        color[:,:,:3]=np.where(eyes[...,None],np.array(glint,np.uint8),color[:,:,:3])
    color[:,:,3]=np.where(mask,255,0).astype(np.uint8)
    out=Image.fromarray(color,'RGBA')
    # Slight antialiasing on silhouette; threshold in renderer retains depth integrity.
    out.putalpha(out.getchannel('A').filter(ImageFilter.GaussianBlur(.28)))
    return out


def make_original_demo(out:Path,seed:int=257,style:str='grunge')->dict:
    if out.exists() and any(out.iterdir()):raise ValueError('Sprite atlas destination is not empty')
    out.mkdir(parents=True,exist_ok=True)
    assets=[]
    for ai,(ident,(dims,n,tile)) in enumerate(WORLD_ASSETS.items()):
        actions={'idle':6,'walk':8,'investigate':6} if ident.startswith('sentinel-') else (
            {'idle':6,'walk':8,'jump':4} if ident=='wanderer' else {'idle':1})
        baked={}
        import tempfile
        for action,count in actions.items():
            produced=[]
            for frame in range(count):
                phase=2*math.pi*frame/count
                with tempfile.TemporaryDirectory(prefix='mgf-slices-') as tmp:
                    paths=[]
                    for i in range(n):
                        path=Path(tmp)/f'{i:03d}.png'
                        analytical_slice(ident,i,n,tile,seed+ai*619,action,phase).save(path)
                        paths.append(path)
                    name=f'{ident}-{action}-{frame:03d}.png';loc=out/name
                    columns,rows=pack_frame(paths,loc,tile)
                produced.append({'atlas':name,'sha256':digest(loc),'columns':columns,'rows':rows,
                  'views':loc.stem+'-views.png','viewsSha256':digest(loc.with_name(loc.stem+'-views.png'))})
            baked[action]=produced
        assets.append({'id':ident,'dimensions':dims,'tile':tile,'sliceCount':n,
              'pivot':[0,0,0],'source':'analytical-original-3d-volumes',
              'license':'original-new-scene-only','actions':baked})
    manifest={'schema':SCHEMA,'coordinateSystem':'X-right/Y-up/Z-forward','atlasColorSpace':'sRGB',
              'alphaMode':'MASK','mode':'horizontal-physical-slices','style':style,'assets':assets}
    (out/'manifest.json').write_text(json.dumps(manifest,sort_keys=True,separators=(',',':'))+'\n','utf-8')
    return manifest


def main()->None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['bake','original-concept'])
    parser.add_argument('--source',help='Folder with approved layer slice assets')
    parser.add_argument('--out',required=True)
    parser.add_argument('--seed',type=int,default=257)
    parser.add_argument('--style',default='grunge')
    parser.add_argument('--merge',action='store_true',help='Merge approved assets into copied original-scene template')
    a=parser.parse_args()
    out=Path(a.out).expanduser().resolve()
    if a.command=='bake':
        if not a.source:parser.error('bake requires --source')
        source=Path(a.source).expanduser().resolve(strict=True)
        if out==source or out in source.parents or source in out.parents:parser.error('Output must not overlap source')
        m=compile_source(source,out,preserve_existing=a.merge)
    else:m=make_original_demo(out,seed=a.seed,style=a.style)
    print(json.dumps({'schema':m['schema'],'assets':len(m['assets']), 'manifest':str(out/'manifest.json'), 'sha256':digest(out/'manifest.json')}))

if __name__=='__main__':
    try: main()
    except (OSError,ValueError,TypeError,KeyError,json.JSONDecodeError) as e:
        print(str(e),file=sys.stderr)
        sys.exit(2)
