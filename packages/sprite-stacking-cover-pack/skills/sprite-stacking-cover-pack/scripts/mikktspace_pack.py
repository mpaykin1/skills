"""Static xatlas → official MikkTSpace CPU → separate textured GLB candidate."""
import argparse, ctypes, json, struct, tempfile
from pathlib import Path
import numpy as np
from PIL import Image
from open3d_stack import digest


def checked(path,expected):
    path=Path(path)
    if not path.is_file() or digest(path)!=expected: raise ValueError('Missing or changed input: '+str(path))
    return path


def read_obj(path):
    v=[]; uv=[]; f=[]
    for line in Path(path).read_text().splitlines():
        s=line.split()
        if not s or s[0]=='#': continue
        if s[0]=='v' and len(s)==4:v.append([float(x) for x in s[1:]])
        elif s[0]=='vt' and len(s)==3:uv.append([float(x) for x in s[1:]])
        elif s[0]=='f' and len(s)==4:
            row=[x.split('/') for x in s[1:]]
            if any(len(x)!=2 or x[0]!=x[1] or int(x[0])<1 for x in row):raise ValueError('Require xatlas one-to-one OBJ indices')
            f.append([int(x[0])-1 for x in row])
        else:raise ValueError('Unexpected xatlas OBJ data')
    v=np.asarray(v);uv=np.asarray(uv);f=np.asarray(f,dtype=np.int64)
    if v.ndim!=2 or v.shape[1]!=3 or uv.shape!=(len(v),2) or f.ndim!=2 or f.shape[1]!=3 or not len(f) or len(f)>1_000_000 or f.min()<0 or f.max()>=len(v) or not np.isfinite(v).all() or not np.isfinite(uv).all() or np.any((uv<0)|(uv>1)):raise ValueError('Invalid mesh')
    return v,uv,f


def prepare(v,uv,f,n):
    p=v[f]; t=uv[f].copy();t[:,:,1]=1-t[:,:,1] # OBJ bottom-up to glTF top-down
    # Proper rotation +Z up to +Y up, determinant +1.
    p=p[:,:,[0,2,1]]*[1,1,-1]
    n=np.asarray(n,dtype=np.float64)
    if n.shape!=p.shape or not np.isfinite(n).all() or not np.allclose(np.linalg.norm(n,axis=-1),1,atol=1e-4):raise ValueError('Require reviewed unit corner normals in source +Z frame')
    n=n[:,:,[0,2,1]]*[1,1,-1]
    cross=np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0]); scale=max(float(np.ptp(p.reshape(-1,3),axis=0).max()),1e-15)
    if np.any(np.linalg.norm(cross,axis=1)<1e-12*scale**2):raise ValueError('Degenerate geometry')
    if np.any(np.einsum('fi,fji->fj',cross,n)<=0):raise ValueError('Normals disagree with face winding')
    a,b=t[:,1]-t[:,0],t[:,2]-t[:,0]
    if np.any(np.abs(a[:,0]*b[:,1]-a[:,1]*b[:,0])<1e-12):raise ValueError('Degenerate UV')
    return tuple(np.ascontiguousarray(x,dtype=np.float32) for x in (p,n,t))


def validate_tangent(n,t):
    if t.shape!=(*n.shape[:-1],4) or not np.isfinite(t).all() or not np.allclose(np.linalg.norm(t[...,:3],axis=-1),1,atol=2e-4) or np.max(np.abs(np.sum(n*t[...,:3],axis=-1)))>2e-4 or not np.isin(t[...,3],[-1,1]).all() or not np.all(t[...,3]==t[:,0:1,3]):raise ValueError('Invalid tangent frame or inconsistent triangle handedness')
    return t


def mikk(lib,p,n,uv):
    fn=ctypes.CDLL(str(Path(lib).resolve())).cover_mikk
    ptr=ctypes.POINTER(ctypes.c_float);fn.argtypes=[ctypes.c_int]+[ptr]*4;fn.restype=ctypes.c_int
    t=np.full((*p.shape[:-1],4),np.nan,np.float32)
    if fn(len(p),*[x.ctypes.data_as(ptr) for x in (p,n,uv,t)])!=1:raise RuntimeError('MikkTSpace failed')
    return validate_tangent(n,t)


def glb(path,p,n,uv,t,images,material):
    # Corner-expanded triangles retain UV and tangent discontinuities. No welding.
    d={'asset':{'version':'2.0','generator':'Cover Pack MikkTSpace bridge'},'scene':0,'scenes':[{'nodes':[0]}],'nodes':[{'mesh':0}],'meshes':[{'primitives':[{'attributes':{},'material':0,'mode':4}]}],'materials':[material],'bufferViews':[],'accessors':[],'images':[],'textures':[],'buffers':[{}]}
    data=bytearray()
    def view(raw,target=None):
        while len(data)%4:data.append(0)
        off=len(data);data.extend(raw);v={'buffer':0,'byteOffset':off,'byteLength':len(raw)}
        if target:v['target']=target
        d['bufferViews'].append(v);return len(d['bufferViews'])-1
    for name,a in [('POSITION',p),('NORMAL',n),('TEXCOORD_0',uv),('TANGENT',t)]:
        a=np.asarray(a,dtype='<f4').reshape(-1,a.shape[-1]); b=view(a.tobytes(),34962); acc={'bufferView':b,'componentType':5126,'count':len(a),'type':'VEC'+str(a.shape[1])}
        if name=='POSITION':acc.update(min=a.min(0).tolist(),max=a.max(0).tolist())
        d['accessors'].append(acc);d['meshes'][0]['primitives'][0]['attributes'][name]=len(d['accessors'])-1
    for img in images:
        d['images'].append({'bufferView':view(Path(img).read_bytes()),'mimeType':'image/png'});d['textures'].append({'source':len(d['images'])-1})
    while len(data)%4:data.append(0)
    d['buffers'][0]['byteLength']=len(data);j=json.dumps(d,separators=(',',':'),allow_nan=False).encode();j+=b' '*((-len(j))%4)
    Path(path).write_bytes(struct.pack('<4sII',b'glTF',2,12+8+len(j)+8+len(data))+struct.pack('<I4s',len(j),b'JSON')+j+struct.pack('<I4s',len(data),b'BIN\0')+data)


def run(atlas,review,library,out):
    root=Path(atlas).resolve();out=Path(out).resolve();review=Path(review).resolve();r=json.loads(review.read_text()); m=json.loads((root/'uv-atlas.json').read_text())
    if out.exists() or root in out.parents or out in root.parents:raise ValueError('Use separate new output')
    if m['schema']!='cover-pack-xatlas/1' or r['atlasSHA256']!=digest(root/'uv-atlas.json'):raise ValueError('Review must bind exact xatlas manifest')
    obj=checked(root/'uv-mesh.obj',m['meshSHA256']);mapping=checked(root/'uv-mapping.npz',m['mappingSHA256']);v,uv,f=read_obj(obj)
    with np.load(mapping,allow_pickle=False) as a:
        if not np.array_equal(f,a['indices']) or not np.allclose(uv,a['uv'],rtol=0,atol=1e-12):raise ValueError('OBJ and UV mapping disagree')
        coverage=a['coverage'].astype(bool)
    if coverage.shape!=tuple(m['atlasSize'][::-1]):raise ValueError('Atlas size mismatch')
    normal_file=checked(review.parent/r['cornerNormals'],r['cornerNormalsSHA256']);n=np.load(normal_file,allow_pickle=False)
    p,n,u=prepare(v,uv,f,n);t=mikk(library,p,n,u)
    def getmap(key,channels):
        q=m['maps'][key];a=np.load(checked(root/q['path'],q['sha256']),allow_pickle=False)
        if a.shape!=(*coverage.shape,channels) or not np.isfinite(a).all() or np.any((a<0)|(a>1)) or q['colorSpace']!=('sRGB' if key=='baseColor' else 'Non-Color'):raise ValueError('Invalid '+key)
        return a
    base=getmap('baseColor',4); mode=r['alphaMode']
    if mode not in ('OPAQUE','MASK','BLEND') or (mode=='OPAQUE' and np.any(base[coverage,3]<1-1e-6)):raise ValueError('Alpha mode would discard transparency')
    out.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out.parent) as tmp:
        stage=Path(tmp)/'candidate';stage.mkdir();images=[]
        def png(name,a):
            file=stage/name;Image.fromarray(np.rint(a*255).astype(np.uint8)).save(file);images.append(file);return len(images)-1
        bc=png('baseColor.png',base);pbr={'baseColorTexture':{'index':bc}}
        mr=np.ones((*coverage.shape,3),np.float32)
        for key,ch in [('roughness',1),('metallic',2)]:
            if key in m['maps']:mr[...,ch]=getmap(key,1)[...,0]
            else:
                value=r[key+'Factor'];
                if type(value) not in (int,float) or not 0<=value<=1:raise ValueError('Explicit material factor required')
                mr[...,ch]=value
        pbr.update(metallicRoughnessTexture={'index':png('metallicRoughness.png',mr)},metallicFactor=1,roughnessFactor=1)
        mat={'pbrMetallicRoughness':pbr,'alphaMode':mode}
        if mode=='MASK':
            cutoff=r['alphaCutoff'];
            if not 0<=cutoff<=1:raise ValueError('Invalid alpha cutoff')
            mat['alphaCutoff']=cutoff
        if 'normalMap' in r:
            if r.get('normalConvention')!='glTF-MikkTSpace-Y+' or r.get('normalBakeMeshSHA256')!=m['meshSHA256'] or r.get('normalBakeCornerNormalsSHA256')!=r['cornerNormalsSHA256']:raise ValueError('Normal map must be baked for exact reviewed mesh/normals and glTF convention')
            q=checked(review.parent/r['normalMap'],r['normalMapSHA256'])
            with Image.open(q) as im:
                if im.format!='PNG' or im.mode!='RGB' or im.size!=tuple(m['atlasSize']):raise ValueError('Need RGB normal PNG matching atlas')
            dst=stage/'normal.png';dst.write_bytes(q.read_bytes());images.append(dst);mat['normalTexture']={'index':len(images)-1}
        target=stage/'candidate.glb';glb(target,p,n,u,t,images,mat)
        np.savez_compressed(stage/'tangent-mesh.npz',positions=p,normals=n,uv=u,tangents=t)
        (stage/'tangent.json').write_text(json.dumps({'schema':'cover-pack-mikk/1','atlasSHA256':r['atlasSHA256'],'meshSHA256':m['meshSHA256'],'reviewSHA256':digest(review),'normalSHA256':digest(normal_file),'librarySHA256':digest(library),'candidateSHA256':digest(target),'normalMapIncluded':'normalMap' in r,'sourceAxis':'+Z','outputAxis':'+Y','sourceNativeSHA256':m['sourceSHA256'],'status':'review-required; Khronos validation and matched render required; no runtime approval'},indent=2)+'\n')
        stage.rename(out)

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--atlas',required=True);a.add_argument('--review',required=True);a.add_argument('--library',required=True);a.add_argument('--out',required=True);x=a.parse_args();run(x.atlas,x.review,x.library,x.out)
