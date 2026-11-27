"""Read authorized scene-linear EXR frames with OIIO; bridge to existing OCIO CPU recipe."""
import argparse, hashlib, json, math, re, shutil, tempfile
from pathlib import Path
import numpy as np
VERSION='3.0.6.0'
SCHEMA='meta-oiio-exr-v1'
def require(ok,msg):
    if not ok: raise ValueError(msg)
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''): h.update(b)
    return h.hexdigest()
def digest(x):return isinstance(x,str) and re.fullmatch('[a-f0-9]{64}',x) is not None
def read_recipe(p):
    c=json.loads(p.read_text(encoding='utf8'))
    require(c.get('schema')==SCHEMA and c.get('source_kind')=='unapproved-linear-render','recipe')
    require(isinstance(c.get('asset_id'),str) and 0<len(c['asset_id'])<=128 and digest(c.get('source_recipe_sha256')),'identity')
    require(c.get('source_space') in ('Linear Rec.709 (sRGB)','ACEScg') and c.get('alpha') in ('straight','premultiplied') and c.get('display')=='sRGB - Display' and c.get('view') in ('ACES 1.0 - SDR Video','Un-tone-mapped'),'color declaration')
    require(type(c.get('fps')) in (int,float) and math.isfinite(c['fps']) and 1<=c['fps']<=60,'fps')
    channels=c.get('channels'); require(isinstance(channels,list) and len(channels)==4 and all(isinstance(x,str) and 0<len(x)<=256 for x in channels) and len(set(channels))==4,'explicit RGBA channels')
    require(type(c.get('subimage',0)) is int and 0<=c.get('subimage',0)<=31,'subimage')
    require(isinstance(c.get('frames'),list) and 1<=len(c['frames'])<=240,'frame count')
    for i,e in enumerate(c['frames']):require(type(e.get('frame')) is int and e['frame']==i and isinstance(e.get('file'),str) and digest(e.get('sha256')),'frame sequence')
    return c

def straight(a,association):
    require(a.dtype==np.float32 and a.ndim==3 and a.shape[2]==4 and np.isfinite(a).all(),'float RGBA')
    a=np.array(a,copy=True,order='C'); alpha=a[...,3:4]
    require(alpha.min()>=0 and alpha.max()<=1 and a[...,:3].min()>=0,'invalid range')
    if association=='premultiplied':
        require(not np.any((alpha==0)&(a[...,:3]!=0)),'nonzero emission with zero alpha cannot be represented as straight RGBA')
        np.divide(a[...,:3],alpha,out=a[...,:3],where=alpha>0)
    a[alpha[...,0]==0,:3]=0
    require(np.isfinite(a).all() and a[...,:3].max()<=65504,'straight RGB outside existing OCIO bridge range')
    return a

def native():
    import OpenImageIO as oiio
    require(str(oiio.VERSION_STRING)==VERSION,'reviewed OIIO version required')
    oiio.attribute('threads',4)
    return oiio

def source(root,e):
    p=(root/e['file']).resolve();require(p.is_relative_to(root.resolve()) and p.is_file() and p.suffix.lower()=='.exr' and p.stat().st_size<=256*1024*1024,'EXR path / size')
    require(sha(p)==e['sha256'],'source hash');return p

def read_exr(oiio,p,c):
    f=oiio.ImageInput.open(str(p));require(f is not None,'OpenImageIO could not open EXR')
    try:
        sub=c.get('subimage',0);require(f.seek_subimage(sub,0),'missing EXR subimage')
        s=f.spec();require(not s.deep and s.depth==1 and 1<=s.width<=2048 and 1<=s.height<=2048 and 4<=s.nchannels<=32,'EXR bounds or deep data')
        require(s.x==s.full_x and s.y==s.full_y and s.width==s.full_width and s.height==s.full_height,'cropped data window requires upstream export')
        names=list(s.channelnames); require(all(x in names for x in c['channels']),'missing exact RGBA channels')
        # No color transform; read selected part at mip zero. EXR alpha association is declared by the author.
        data=f.read_image(sub,0,0,s.nchannels,oiio.FLOAT)
        require(data is not None and data.shape==(s.height,s.width,s.nchannels),'read failure')
        return straight(np.asarray(data,dtype=np.float32)[...,[names.index(x) for x in c['channels']]],c['alpha'])
    finally:f.close()

def convert(recipe,out):
    c=read_recipe(recipe);require(not out.exists(),'output exists');oiio=native();out.parent.mkdir(parents=True,exist_ok=True)
    tmp=Path(tempfile.mkdtemp(prefix='.oiio-',dir=out.parent))
    try:
        entries=[];shape=None
        for e in c['frames']:
            a=read_exr(oiio,source(recipe.parent,e),c);shape=shape or a.shape;require(shape==a.shape,'inconsistent dimensions')
            name=f"{e['frame']:04d}.npy";p=tmp/name;np.save(p,a,allow_pickle=False)
            entries.append({'frame':e['frame'],'file':name,'sha256':sha(p)})
        r={k:c[k] for k in ('asset_id','source_recipe_sha256','source_space','display','view','fps')};r.update(schema='meta-ocio-render-v1',source_kind='unapproved-linear-render',alpha='straight',frames=entries)
        (tmp/'ocio-recipe.json').write_text(json.dumps(r,indent=2),encoding='utf8')
        m={'schema':'meta-oiio-exr-bridge-v1','backend':'OpenImageIO','version':VERSION,'source_manifest_sha256':sha(recipe),'ocio_recipe_sha256':sha(tmp/'ocio-recipe.json'),'size':[shape[1],shape[0]],'source_frame_sha256':[e['sha256'] for e in c['frames']],'approved':False}
        (tmp/'bridge.json').write_text(json.dumps(m,indent=2),encoding='utf8');require(not out.exists(),'output exists');tmp.rename(out)
    finally:
        if tmp.exists():shutil.rmtree(tmp)

def audit(recipe,out,recompute=False):
    c=read_recipe(recipe);m=json.loads((out/'bridge.json').read_text());rp=out/'ocio-recipe.json';r=json.loads(rp.read_text())
    require(m['schema']=='meta-oiio-exr-bridge-v1' and m['backend']=='OpenImageIO' and m['version']==VERSION and m['source_manifest_sha256']==sha(recipe) and m['ocio_recipe_sha256']==sha(rp) and m['source_frame_sha256']==[e['sha256'] for e in c['frames']],'provenance')
    require(r['schema']=='meta-ocio-render-v1' and r['source_kind']==c['source_kind'] and r['alpha']=='straight' and len(r['frames'])==len(c['frames']),'OCIO recipe')
    for k in ('asset_id','source_recipe_sha256','source_space','display','view','fps'):require(r[k]==c[k],'recipe mismatch '+k)
    oiio=native() if recompute else None
    for e,o in zip(c['frames'],r['frames']):
        src=source(recipe.parent,e);name=f"{e['frame']:04d}.npy";p=out/name
        require(o['frame']==e['frame'] and o['file']==name and p.stat().st_size<=2048*2048*16+4096 and sha(p)==o['sha256'],'frame integrity')
        a=np.load(p,allow_pickle=False);require(a.dtype==np.float32 and a.ndim==3 and a.shape[2]==4 and list(a.shape[:2][::-1])==m['size'] and 1<=a.shape[0]<=2048 and 1<=a.shape[1]<=2048,'frame dimensions')
        require(np.array_equal(a,straight(a,'straight')),'invalid straight frame')
        if recompute:require(np.array_equal(a,read_exr(oiio,src,c)),'EXR decode mismatch')
    return m

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['convert','audit']);p.add_argument('recipe',type=Path);p.add_argument('out',type=Path);p.add_argument('--recompute',action='store_true');a=p.parse_args();convert(a.recipe,a.out) if a.mode=='convert' else audit(a.recipe,a.out,a.recompute)
