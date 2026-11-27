"""Offline OCIO display transform for new, unapproved linear RGBA render candidates."""
import argparse, hashlib, json, re, math
from pathlib import Path
import numpy as np
from PIL import Image
CONFIG = 'cg-config-v2.2.0_aces-v1.3_ocio-v2.4'
VERSION = '2.4.2'
SCHEMA = 'meta-ocio-render-v1'

def require(ok, msg):
    if not ok: raise ValueError(msg)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def digest(s): return isinstance(s,str) and re.fullmatch(r'[0-9a-f]{64}',s) is not None
def load_recipe(path):
    c=json.loads(path.read_text())
    require(c.get('schema')==SCHEMA and c.get('source_kind')=='unapproved-linear-render' and c.get('alpha')=='straight' and c.get('source_space') in ('Linear Rec.709 (sRGB)','ACEScg') and c.get('display')=='sRGB - Display' and c.get('view') in ('ACES 1.0 - SDR Video','Un-tone-mapped'), 'recipe / color space')
    require(isinstance(c.get('asset_id'),str) and c['asset_id'] and digest(c.get('source_recipe_sha256')), 'identity')
    require(type(c.get('fps')) in (int,float) and math.isfinite(c['fps']) and 1<=c['fps']<=60,'fps')
    require(isinstance(c.get('frames'),list) and 1<=len(c['frames'])<=240,'frame count')
    for i,e in enumerate(c['frames']):
        require(type(e.get('frame')) is int and e['frame']==i and digest(e.get('sha256')), 'frame sequence or hash')
    return c

def source(root,e):
    p=(root/e['file']).resolve();require(p.is_relative_to(root.resolve()) and p.is_file() and p.suffix=='.npy' and p.stat().st_size<=2048*2048*16+4096,'source path/size')
    require(sha(p)==e['sha256'],'source hash');a=np.load(p,allow_pickle=False)
    require(a.dtype==np.float32 and a.ndim==3 and a.shape[2]==4 and 1<=a.shape[0]<=2048 and 1<=a.shape[1]<=2048 and np.isfinite(a).all(),'linear float32 RGBA')
    require(a[...,:3].min()>=0 and a[...,:3].max()<=65504 and a[...,3].min()>=0 and a[...,3].max()<=1,'linear range')
    return a

def processor(c):
    import PyOpenColorIO as ocio
    require(ocio.__version__==VERSION,'reviewed OCIO version required')
    cfg=ocio.Config.CreateFromBuiltinConfig(CONFIG);cfg.validate()
    require(cfg.getColorSpace(c['source_space']) is not None and c['display'] in list(cfg.getDisplays()) and c['view'] in list(cfg.getViews(c['display'])),'unsupported built-in profile')
    return cfg.getProcessor(c['source_space'],c['display'],c['view'],ocio.TRANSFORM_DIR_FORWARD).getDefaultCPUProcessor(),str(cfg.getCacheID())

def alpha8(a): return np.rint(a[...,3]*255).astype(np.uint8)
def render(path,out):
    c=load_recipe(path);require(not out.exists(),'output exists');cpu,cache=processor(c)
    out.mkdir(parents=True);frames=[];shape=None
    for e in c['frames']:
        a=source(path.parent,e);shape=shape or a.shape;require(a.shape==shape,'inconsistent render dimensions')
        rgb=np.ascontiguousarray(a[...,:3]);cpu.applyRGB(rgb);require(np.isfinite(rgb).all(),'invalid transformed color')
        rgba=np.empty(a.shape,dtype=np.uint8);rgba[...,:3]=np.rint(np.clip(rgb,0,1)*255).astype(np.uint8);rgba[...,3]=alpha8(a)
        rgba[rgba[...,3]==0,:3]=0
        f=out/f"{e['frame']:04d}.png";Image.fromarray(rgba).save(f)
        frames.append({'frame':e['frame'],'file':f.name,'sha256':sha(f),'source_sha256':e['sha256']})
    m={'schema':'meta-ocio-display-v1','backend':'ocio-cpu','version':VERSION,'config':CONFIG,'config_cache_id':cache,'recipe_sha256':sha(path),'source_recipe_sha256':c['source_recipe_sha256'],'asset_id':c['asset_id'],'source_space':c['source_space'],'display':c['display'],'view':c['view'],'fps':c['fps'],'size':[shape[1],shape[0]],'output_space':'srgb-display','alpha':'straight','tone_mapped':c['view']!='Un-tone-mapped','approved':False,'frames':frames}
    (out/'display.json').write_text(json.dumps(m,indent=2),encoding='utf8')

def audit(path,out,recompute=False):
    c=load_recipe(path);m=json.loads((out/'display.json').read_text());require(m['schema']=='meta-ocio-display-v1' and m['backend']=='ocio-cpu' and m['version']==VERSION and m['config']==CONFIG and m['recipe_sha256']==sha(path) and m['output_space']=='srgb-display' and m['alpha']=='straight' and m['tone_mapped']==(c['view']!='Un-tone-mapped'),'manifest')
    for k in ('asset_id','source_recipe_sha256','fps','source_space','display','view'):require(m[k]==c[k],k)
    require(len(m['frames'])==len(c['frames']),'frame count')
    if recompute:
        cpu,cache=processor(c);require(m['config_cache_id']==cache,'config changed')
    for e,o in zip(c['frames'],m['frames']):
        a=source(path.parent,e);name=f"{e['frame']:04d}.png";f=out/name;require(o['frame']==e['frame'] and o['file']==name and o['source_sha256']==e['sha256'] and sha(f)==o['sha256'],'frame provenance')
        with Image.open(f) as im:
            require(im.mode=='RGBA' and list(im.size)==m['size']==[a.shape[1],a.shape[0]],'image shape');v=np.array(im)
        require(np.array_equal(v[...,3],alpha8(a)),'alpha changed');require(np.all(v[v[...,3]==0,:3]==0),'hidden RGB')
        if recompute:
            rgb=np.ascontiguousarray(a[...,:3]);cpu.applyRGB(rgb);q=np.rint(np.clip(rgb,0,1)*255).astype(np.uint8);q[v[...,3]==0]=0;require(np.max(np.abs(q.astype(np.int16)-v[...,:3].astype(np.int16)))<=1,'display mismatch')
    return m

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['render','audit']);p.add_argument('recipe',type=Path);p.add_argument('out',type=Path);p.add_argument('--recompute',action='store_true');a=p.parse_args();render(a.recipe,a.out) if a.mode=='render' else audit(a.recipe,a.out,a.recompute)
