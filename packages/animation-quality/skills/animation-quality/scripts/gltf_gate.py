"""Khronos validation + strict root-motion-only GLB release gate. No source mutation."""
import argparse, hashlib, json, struct, subprocess, sys
from pathlib import Path
import numpy as np
from blender_root_solver import metrics

LIMIT=256*1024*1024

def read_glb(path):
    if not path.is_file() or not 20<=path.stat().st_size<=LIMIT: raise ValueError('GLB size/path invalid')
    b=path.read_bytes()
    if struct.unpack_from('<4sII',b)!=(b'glTF',2,len(b)): raise ValueError('invalid GLB header')
    chunks=[]; i=12
    while i<len(b):
        if i+8>len(b): raise ValueError('truncated chunk')
        n,t=struct.unpack_from('<I4s',b,i); i+=8
        if n%4 or i+n>len(b): raise ValueError('invalid chunk length')
        chunks.append((t,b[i:i+n])); i+=n
    if [x[0] for x in chunks] not in ([b'JSON'],[b'JSON',b'BIN\x00']): raise ValueError('unsupported chunk layout')
    d=json.loads(chunks[0][1]); binary=chunks[1][1] if len(chunks)==2 else b''
    if any('uri' in x for x in d.get('buffers',[])+d.get('images',[])): raise ValueError('only embedded buffers/images supported')
    return d,binary,hashlib.sha256(b).hexdigest()

def validate(path, strict=False):
    _,_,sha=read_glb(path)
    p=subprocess.run(['node',str(Path(__file__).with_name('khronos_validate.cjs')),str(path.resolve())],capture_output=True,text=True,timeout=180)
    if p.returncode: raise ValueError('Khronos gate blocked: '+(p.stderr or p.stdout)[-2500:])
    r=json.loads(p.stdout)
    if r.get('ok') is not True or r.get('sha256')!=sha or r.get('validator')!='2.0.0-dev.3.10': raise ValueError('validator result/hash mismatch')
    if strict and r['issues']['numWarnings']: raise ValueError('strict mode: warnings')
    return r

def array(d,b,i,width):
    a=d['accessors'][i]; v=d['bufferViews'][a['bufferView']]
    if a.get('sparse') or a.get('normalized') or a['componentType']!=5126 or a['type']!=('SCALAR' if width==1 else 'VEC3') or v['buffer']!=0 or 'byteStride' in v or v.get('extensions') or a.get('extensions'): raise ValueError('dense float accessor required')
    start=v.get('byteOffset',0)+a.get('byteOffset',0); end=start+a['count']*width*4
    if not 0<=start<end<=len(b) or end>v.get('byteOffset',0)+v['byteLength']: raise ValueError('accessor bounds')
    q=np.frombuffer(b[start:end],dtype='<f4').astype(float).reshape(-1,width)
    if not np.isfinite(q).all(): raise ValueError('nonfinite accessor')
    return q,start,end

def protected_compare(src,dst,clip,node,radius,anchors):
    d,b,sha=read_glb(src); e,c,shb=read_glb(dst)
    if not np.isfinite(radius) or radius<=0 or len(b)!=len(c): raise ValueError('radius or layout mismatch')
    if not 0<=clip<len(d['animations']) or not 0<=node<len(d['nodes']): raise ValueError('invalid clip/node index')
    if d.get('extensionsUsed') or d.get('extensionsRequired'): raise ValueError('root edit guard supports core glTF only')
    if any(node in n.get('children',[]) for n in d['nodes']): raise ValueError('root must be unparented')
    an=d['animations'][clip]; ch=[x for x in an['channels'] if x['target']=={'node':node,'path':'translation'}]
    if len(ch)!=1: raise ValueError('exactly one root translation channel required')
    s=an['samplers'][ch[0]['sampler']]; i=s['output']; ti=s['input']
    if s.get('interpolation','LINEAR')!='LINEAR' or i==ti: raise ValueError('LINEAR root track required')
    # Reject all shared accessors/views, including other animation channels, mesh or skin use.
    if sum(x.get('output')==i for a in d['animations'] for x in a['samplers'])!=1 or sum(x['sampler']==ch[0]['sampler'] for x in an['channels'])!=1 or any(x.get('input')==i for a in d['animations'] for x in a['samplers']): raise ValueError('shared root animation accessor')
    for m in d.get('meshes',[]):
        for p in m['primitives']:
            if i==p.get('indices') or i in p['attributes'].values() or any(i in t.values() for t in p.get('targets',[])): raise ValueError('shared geometry accessor')
    if any(x.get('inverseBindMatrices')==i for x in d.get('skins',[])): raise ValueError('shared skin accessor')
    vi=d['accessors'][i]['bufferView']; view=d['bufferViews'][vi]
    if any(k!=i and (a.get('bufferView')==vi or any(x.get('bufferView')==vi for x in a.get('sparse',{}).values() if isinstance(x,dict))) for k,a in enumerate(d['accessors'])) or any(x.get('bufferView')==vi for x in d.get('images',[])): raise ValueError('shared view')
    lo=view.get('byteOffset',0); hi=lo+view['byteLength']
    if any(k!=vi and v['buffer']==view['buffer'] and max(lo,v.get('byteOffset',0))<min(hi,v.get('byteOffset',0)+v['byteLength']) for k,v in enumerate(d['bufferViews'])): raise ValueError('overlapping views')
    # Require identical JSON except bounds of the sole edited accessor, and identical remaining bytes.
    for x in (d,e):
        for key in ('min','max'): x['accessors'][i].pop(key,None)
    if d!=e: raise ValueError('protected GLB metadata changed')
    p,start,end=array(d,b,i,3); q,st2,en2=array(e,c,i,3); t,_,_=array(d,b,ti,1); t=t[:,0]
    if (start,end)!=(st2,en2) or b[:start]!=c[:start] or b[end:]!=c[end:]: raise ValueError('protected GLB bytes changed')
    if len(p)!=len(t) or not 6<=len(t)<=2000: raise ValueError('dense track length required')
    dt=np.diff(t)
    if np.any(dt<=0) or not np.allclose(dt,dt[0],rtol=1e-3,atol=1e-7): raise ValueError('uniform time grid required')
    fixed=sorted(set([0,1,len(p)-2,len(p)-1,*anchors]))
    if any(not 0<=j<len(p) for j in fixed) or not np.array_equal(p[fixed],q[fixed]): raise ValueError('locked samples changed')
    deviation=float(np.linalg.norm(q-p,axis=1).max()); old=metrics(p,float(dt.mean())); new=metrics(q,float(dt.mean()))
    if deviation>radius+1e-8 or old['jerk_rms']<1e-9 or new['jerk_rms']>=.99*old['jerk_rms'] or new['acceleration_rms']>old['acceleration_rms']+1e-9: raise ValueError('no safe root-motion improvement')
    return {'source_sha256':sha,'candidate_sha256':shb,'before':old,'after':new,'max_deviation':deviation,'locked_samples':fixed,'artistic_quality':None}

def main():
    p=argparse.ArgumentParser(); s=p.add_subparsers(dest='cmd',required=True)
    a=s.add_parser('validate'); a.add_argument('input',type=Path); a.add_argument('--strict',action='store_true')
    a=s.add_parser('compare-root'); a.add_argument('before',type=Path); a.add_argument('after',type=Path); a.add_argument('--clip',type=int,required=True); a.add_argument('--node',type=int,required=True); a.add_argument('--radius',type=float,required=True); a.add_argument('--anchors',type=int,nargs='*',required=True); a.add_argument('--confirm-contact-samples',action='store_true',required=True); a.add_argument('--strict',action='store_true')
    a=p.parse_args()
    if a.cmd=='validate': result=validate(a.input,a.strict)
    else:
        if a.before.resolve()==a.after.resolve(): raise ValueError('distinct original and candidate required')
        v1=validate(a.before,a.strict); v2=validate(a.after,a.strict)
        result=protected_compare(a.before,a.after,a.clip,a.node,a.radius,a.anchors)
        if result['source_sha256']!=v1['sha256'] or result['candidate_sha256']!=v2['sha256']: raise ValueError('file changed after validator')
        from collections import Counter
        w=lambda v: Counter((m.get('code'),m.get('pointer')) for m in v['issues']['messages'] if m.get('severity')==1)
        if w(v2)-w(v1): raise ValueError('new validator warnings')
        result['validator']=v1['validator']; result['structural_gate']='passed'; result['visual_review_required']=True
    print(json.dumps(result,allow_nan=False,ensure_ascii=False))

if __name__=='__main__':
    try: main()
    except Exception as e: print('BLOCKED: '+str(e),file=sys.stderr); sys.exit(2)
