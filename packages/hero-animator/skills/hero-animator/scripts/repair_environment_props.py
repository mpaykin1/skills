#!/usr/bin/env python3
"""Replace incomplete billboard cutouts in the existing autonomous game with validated full props.
Also used as the final mandatory stage by the original-game builder.
"""
import argparse,base64,hashlib,io,json,re
from pathlib import Path
from PIL import Image
from prop_integrity_gate import validate_image

LEGACY_SCENERY="""for(const c of world.chunks.values())for(const p of c.props){const d=Math.hypot(p.x-player.x,p.z-player.z);if(d<6||d>62)continue;const a=A[p.type];layers.push([p.type,p.x,terrainY(p.x,p.z)-.22,p.z,p.size,p.size,Math.floor(t*1000*a.speed/180)%9,a.alpha,.75,0,Math.atan2(cam.x-p.x,cam.z-p.z)]);}"""
SCENERY=r'''
visibleWorldProps=[];
for(const c of world.chunks.values())for(const p of c.props){
 const d=Math.hypot(p.x-player.x,p.z-player.z);if(d>=70)continue;
 const a=HERO_PROP_PACK.assets[p.type];if(!a)throw Error('Unvalidated world prop '+p.type);
 const yaw=Math.atan2(cam.x-p.x,cam.z-p.z),height=p.size,width=height*a.width/a.height;
 const rootOffset=width*(.5-a.pivot[0]/a.width),px=p.x+Math.cos(yaw)*rootOffset,pz=p.z-Math.sin(yaw)*rootOffset;
 const py=terrainY(p.x,p.z)-.22-height*(1-a.pivot[1]/a.height);
 const fade=Math.min(1,Math.max(0,(70-d)/12)); // Continuous far fade; no near-distance disappearance.
 layers.push([p.type,px,py,pz,width,height,0,fade,.65,0,yaw]);
 visibleWorldProps.push({id:p.type,x:p.x,z:p.z,rootY:terrainY(p.x,p.z)-.22,width,height,opacity:fade});
}
'''
BACKGROUND=r'''
// Panorama is a background, not a finite world billboard with exposed vertical edges.
const previousVP=vp;vp=new Float32Array([1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]);
const viewAspect=canvas.width/canvas.height,imageAspect=A.original.w/A.original.h;
const coverW=Math.min(1,viewAspect/imageAspect),coverH=Math.min(1,imageAspect/viewAspect);
const backgroundUV=[(1-coverW)*(.5+mouseYaw*.3),(1-coverH)*.5,coverW,coverH];
gl.disable(gl.DEPTH_TEST);gl.depthMask(false);
draw(plane,'original',new Float32Array([2,0,0,0,0,2,0,0,0,0,1,0,0,-1,0,1]),{uv:backgroundUV,localLight:false});
vp=previousVP;gl.enable(gl.DEPTH_TEST);gl.depthMask(true);
'''

def validate_pack(pack):
    if pack.get('kind')!='complete-prop-pack' or len(pack.get('assets',{}))<3:raise ValueError('Validated complete prop pack with >=3 actual silhouettes required')
    if not {'tree_ash_oak','tree_ash_elm','tree_ash_twisted'}.issubset(pack['assets']):raise ValueError('Ash adapter requires its three registered tree IDs')
    if len({a.get('sha256') for a in pack['assets'].values()})!=len(pack['assets']):raise ValueError('Distinct tree variants required, not duplicate placeholders')
    for key,a in pack['assets'].items():
        if a.get('role')!='complete-prop' or a.get('sourceKind')!='independently-painted-complete-object':raise ValueError('Background fragments forbidden: '+key)
        if a.get('review',{}).get('fullSilhouetteObserved') is not True:raise ValueError('Full silhouette visual review missing: '+key)
        url=a.get('url','')
        if not url.startswith('data:image/webp;base64,'):raise ValueError('Embedded lossless asset required')
        data=base64.b64decode(url.split(',',1)[1],validate=True)
        if hashlib.sha256(data).hexdigest()!=a.get('sha256'):raise ValueError('Prop payload hash mismatch')
        with Image.open(io.BytesIO(data)) as im:
            r=validate_image(im,'complete-prop',.05)
            if list(im.size)!=[a['width'],a['height']]:raise ValueError('Wrong prop dimensions')
            x,y=a.get('pivot',[None,None])
            if not isinstance(x,(float,int)) or not isinstance(y,(float,int)) or not 0<x<im.width or not 0<y<im.height:raise ValueError('Invalid root pivot')
            if abs(y-(r['bbox'][3]-1))>2:raise ValueError('Root pivot must follow the painted foot, not the transparent canvas edge')
        if a.get('gate',{}).get('bbox')!=r['bbox']:raise ValueError('Stale structural evidence')
    return True

def repair(src,pack,world_source):
    validate_pack(pack)
    if 'window.HERO_PROP_PACK=' in src:raise ValueError('Already repaired: do not stack environment adapters')
    protected={n:re.search(r'window\.'+n+r'=(.*?);</script>',src,re.S)[1] for n in ['ASSETS','HERO_PACK']}
    def once(old,new):
        nonlocal src
        if src.count(old)!=1:raise ValueError('Unsupported environment adapter: '+old[:90])
        src=src.replace(old,new,1)
    once('<script>window.ASSETS=', '<script>window.HERO_PROP_PACK='+json.dumps(pack,separators=(',',':'))+';</script><script>window.ASSETS=')
    once('for(let [n,a] of Object.entries(A))loadTex(n,a);',"for(const [id,p] of Object.entries(HERO_PROP_PACK.assets))A[id]={url:p.url,w:p.width,h:p.height,aw:p.width,ah:p.height,frames:1,alpha:1,speed:0,role:p.role};\nfor(let [n,a] of Object.entries(A))loadTex(n,a);")
    # Swap only the deterministic world generator, preserving the independent input module.
    start=src.index('/* Deterministic, bounded terrain streaming.')
    end=src.index('})(globalThis);',start)+len('})(globalThis);')
    src=src[:start]+world_source.strip()+src[end:]
    once(LEGACY_SCENERY,SCENERY)
    once("paint('original',player.x,-4,player.z-80,230,70,0,1,0,0);",BACKGROUND)
    once('let renderOrigin=[0,0];const world=', 'let visibleWorldProps=[];let renderOrigin=[0,0];const world=')
    once('textures:ready,',"textures:ready,textureTotal:Object.keys(A).length,environment:{completeProps:true,propIds:Object.keys(HERO_PROP_PACK.assets),visible:visibleWorldProps},")
    for n,data in protected.items():
        if re.search(r'window\.'+n+r'=(.*?);</script>',src,re.S)[1]!=data:raise ValueError('Original artwork or character pack changed')
    return src

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path);p.add_argument('output',type=Path);p.add_argument('--props',type=Path);a=p.parse_args()
    if a.input.resolve()==a.output.resolve():p.error('Preserve previous HTML')
    base=Path(__file__).resolve().parent.parent;props=a.props or base/'assets/complete-ash-props.json'
    result=repair(a.input.read_text(encoding='utf8'),json.loads(props.read_text(encoding='utf8')),(base/'runtime/infinite-world.js').read_text(encoding='utf8'))
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(result,encoding='utf8');print(json.dumps({'output':str(a.output),'bytes':a.output.stat().st_size,'sha256':hashlib.sha256(a.output.read_bytes()).hexdigest()}))
if __name__=='__main__':main()
