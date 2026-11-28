"""Lossless CPU archive of trusted, newly rendered straight RGBA float32 frames.
Never decode externally supplied EXR with the legacy OpenCV backend.
"""
import argparse, hashlib, json, math, os, re, shutil, struct, tempfile
from pathlib import Path
import numpy as np

def need(x,msg):
    if not x: raise ValueError(msg)
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()
def digest(s):return isinstance(s,str) and re.fullmatch('[0-9a-f]{64}',s) is not None
def recipe(p):
    r=json.loads(p.read_text());need(r.get('schema')=='meta-ocio-render-v1' and r.get('source_kind')=='unapproved-linear-render' and r.get('alpha')=='straight','source type')
    need(r.get('source_space') in ('Linear Rec.709 (sRGB)','ACEScg') and r.get('display')=='sRGB - Display' and r.get('view') in ('ACES 1.0 - SDR Video','Un-tone-mapped'),'color declaration')
    need(isinstance(r.get('asset_id'),str) and 0<len(r['asset_id'])<=128 and digest(r.get('source_recipe_sha256')),'identity')
    need(type(r.get('fps')) in (int,float) and math.isfinite(r['fps']) and 1<=r['fps']<=60,'fps')
    need(isinstance(r.get('frames'),list) and 1<=len(r['frames'])<=240,'frame count')
    for i,e in enumerate(r['frames']):need(type(e.get('frame')) is int and e['frame']==i and isinstance(e.get('file'),str) and digest(e.get('sha256')),'frame sequence')
    return r

def read_source(root,e):
    p=(root/e['file']).resolve();need(p.is_relative_to(root.resolve()) and p.is_file() and p.suffix=='.npy' and p.stat().st_size<=2048*2048*16+4096,'input path/size');need(sha(p)==e['sha256'],'source hash')
    a=np.load(p,allow_pickle=False);need(a.dtype==np.float32 and a.ndim==3 and a.shape[2]==4 and all(1<=x<=2048 for x in a.shape[:2]) and np.isfinite(a).all(),'source shape');need(a[...,:3].min()>=0 and a[...,:3].max()<=65504 and a[...,3].min()>=0 and a[...,3].max()<=1,'source range')
    need(not np.any((a[...,3:4]==0)&(a[...,:3]!=0)),'additive or hidden RGB requires separate upstream treatment')
    return a

def header(p,w,h):
    # Only canonical single-part scanline files created by this tool are accepted.
    need(p.stat().st_size<=w*h*16+4*1024*1024,'EXR size')
    with p.open('rb') as f:
        need(f.read(8)==struct.pack('<II',20000630,2),'EXR magic/version flags')
        def cstr():
            b=bytearray()
            while len(b)<256:
                x=f.read(1);need(bool(x),'truncated header')
                if x==b'\0':return bytes(b)
                b+=x
            raise ValueError('header string too long')
        attrs={}
        for _ in range(64):
            k=cstr()
            if not k:break
            t=cstr();q=f.read(4);need(len(q)==4,'attribute size');n=struct.unpack('<I',q)[0];need(n<=65536 and k not in attrs,'attribute bounds');v=f.read(n);need(len(v)==n,'truncated attribute');attrs[k]=(t,v)
        else:raise ValueError('header too long')
    for k in (b'dataWindow',b'displayWindow'):need(attrs[k]==(b'box2i',struct.pack('<iiii',0,0,w-1,h-1)),'window mismatch')
    need(attrs[b'compression']==(b'compression',b'\x03'),'not ZIP')
    t,v=attrs[b'channels'];need(t==b'chlist','channel list');names=[];pos=0
    while pos<len(v) and v[pos]!=0:
        end=v.index(0,pos);names.append(v[pos:end]);pos=end+1;need(pos+16<=len(v),'channel record');pt,pl,xs,ys=struct.unpack('<iB3xii',v[pos:pos+16]);need(pt==2 and xs==ys==1,'not full-resolution FLOAT');pos+=16
    need(pos==len(v)-1 and v[pos:]==b'\0' and sorted(names)==[b'A',b'B',b'G',b'R'],'RGBA channels')

def backend():
    # Explicit opt-in for self-authored EXR only. OpenCV may bundle an older codec.
    os.environ['OPENCV_IO_ENABLE_OPENEXR']='1'
    import cv2
    cv2.setNumThreads(4)
    match=re.search(r'^\s*OpenEXR:\s*(.+)$',cv2.getBuildInformation(),re.M);need(match is not None and 'NO' not in match[1].upper(),'OpenEXR codec absent')
    return cv2,match[1].strip()

def exact(cv,p,a):
    h,w=a.shape[:2];header(p,w,h);v=cv.imread(str(p),cv.IMREAD_UNCHANGED);need(v is not None and v.dtype==np.float32 and v.shape==a.shape,'decode failed')
    need(np.array_equal(np.ascontiguousarray(v[...,[2,1,0,3]]).view(np.uint32),np.ascontiguousarray(a).view(np.uint32)),'FP32 roundtrip changed bits')

def export(src,out):
    r=recipe(src);need(not out.exists(),'output exists');cv,ver=backend();out.parent.mkdir(parents=True,exist_ok=True);tmp=Path(tempfile.mkdtemp(prefix='.exr-',dir=out.parent))
    try:
        entries=[];shape=None
        for e in r['frames']:
            a=read_source(src.parent,e);shape=shape or a.shape;need(a.shape==shape,'dimensions changed');p=tmp/f"{e['frame']:04d}.exr"
            need(cv.imwrite(str(p),np.ascontiguousarray(a[...,[2,1,0,3]]),[cv.IMWRITE_EXR_TYPE,cv.IMWRITE_EXR_TYPE_FLOAT,cv.IMWRITE_EXR_COMPRESSION,cv.IMWRITE_EXR_COMPRESSION_ZIP]),'EXR write failed');exact(cv,p,a)
            entries.append({'frame':e['frame'],'file':p.name,'sha256':sha(p)})
        rr={k:r[k] for k in ('source_kind','asset_id','source_recipe_sha256','source_space','display','view','alpha','fps')};rr.update(schema='meta-oiio-exr-v1',subimage=0,channels=['R','G','B','A'],frames=entries)
        (tmp/'oiio-recipe.json').write_text(json.dumps(rr,indent=2));m={'schema':'meta-openexr-archive-v1','backend':'opencv-openexr','codec':ver,'opencv':cv.__version__,'pixel_type':'FLOAT32','compression':'ZIP','source_manifest_sha256':sha(src),'oiio_recipe_sha256':sha(tmp/'oiio-recipe.json'),'source_frame_sha256':[e['sha256'] for e in r['frames']],'size':[shape[1],shape[0]],'approved':False}
        (tmp/'archive.json').write_text(json.dumps(m,indent=2));need(not out.exists(),'output exists');tmp.rename(out)
    finally:
        if tmp.exists():shutil.rmtree(tmp)

def audit(src,out):
    r=recipe(src);m=json.loads((out/'archive.json').read_text());p=out/'oiio-recipe.json';rr=json.loads(p.read_text());need(m.get('schema')=='meta-openexr-archive-v1' and m.get('backend')=='opencv-openexr' and m.get('pixel_type')=='FLOAT32' and m.get('compression')=='ZIP' and m.get('source_manifest_sha256')==sha(src) and m.get('oiio_recipe_sha256')==sha(p) and m.get('source_frame_sha256')==[e['sha256'] for e in r['frames']],'provenance')
    need(rr.get('schema')=='meta-oiio-exr-v1' and rr.get('subimage')==0 and rr.get('channels')==['R','G','B','A'] and len(rr['frames'])==len(r['frames']),'bridge')
    for k in ('source_kind','asset_id','source_recipe_sha256','source_space','display','view','alpha','fps'):need(rr[k]==r[k],'recipe mismatch')
    # Audit only self-produced archives whose provenance is independently trusted; hashes alone are not authorization.
    cv,_=backend()
    for e,o in zip(r['frames'],rr['frames']):
        a=read_source(src.parent,e);name=f"{e['frame']:04d}.exr";p=out/name;need(o['frame']==e['frame'] and o['file']==name and p.is_file() and p.resolve().is_relative_to(out.resolve()) and sha(p)==o['sha256'] and m['size']==[a.shape[1],a.shape[0]],'frame provenance');exact(cv,p,a)
    return m
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['export','audit']);p.add_argument('recipe',type=Path);p.add_argument('out',type=Path);a=p.parse_args();export(a.recipe,a.out) if a.mode=='export' else audit(a.recipe,a.out)
