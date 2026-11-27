"""CPU UV atlas and surface-grid material bake candidate. Never replace source."""
import argparse, json, tempfile, shutil, importlib.metadata
from pathlib import Path
import numpy as np
from PIL import Image
from scipy.spatial import cKDTree
from scipy.ndimage import distance_transform_edt
from open3d_stack import load_inputs, digest, native_to_world


def validate_mapping(v,f,mapping,indices,uv):
    mapping=np.asarray(mapping); indices=np.asarray(indices); uv=np.asarray(uv,dtype=np.float64)
    if mapping.ndim!=1 or not len(mapping) or mapping.dtype.kind not in 'iu' or mapping.min()<0 or mapping.max()>=len(v): raise ValueError('Invalid xatlas vertex mapping')
    if indices.shape!=f.shape or indices.dtype.kind not in 'iu' or indices.min()<0 or indices.max()>=len(mapping): raise ValueError('Invalid atlas indices')
    if not np.array_equal(mapping[indices],f): raise ValueError('Triangle order, winding or geometry changed')
    if uv.shape!=(len(mapping),2) or not np.isfinite(uv).all() or np.any((uv<0)|(uv>1)): raise ValueError('Invalid UVs')
    t=uv[indices]; a=t[:,1]-t[:,0]; b=t[:,2]-t[:,0]
    if np.any(np.abs(a[:,0]*b[:,1]-a[:,1]*b[:,0])<1e-14): raise ValueError('Degenerate UV triangles')
    return mapping,indices,uv


def raster(v,f,uv,mapping,indices,xyz,maps,step,width,height,padding):
    """Nearest native surface sample, not ray tracing or true original texture recovery."""
    if not (1<=width<=2048 and 1<=height<=2048 and 0<=padding<=16): raise ValueError('Invalid atlas dimensions/padding')
    mapping,indices,uv=validate_mapping(v,f,mapping,indices,uv)
    tree=cKDTree(xyz); hit=np.full((height,width),-1,np.int32); inside=np.zeros_like(hit,dtype=bool); work=0; peak=0.
    for i,(p,t) in enumerate(zip(v[f],uv[indices])):
        t=t*np.array([width,-height])+[0,height]
        low=np.maximum(np.ceil(t.min(0)-.5).astype(int),0); high=np.minimum(np.floor(t.max(0)-.5).astype(int),[width-1,height-1]); size=high-low+1
        if np.any(size<=0): raise ValueError('Subpixel triangle; increase atlas resolution or use source')
        work+=int(np.prod(size))
        if work>100_000_000: raise ValueError('Raster budget exceeded')
        yy,xx=np.mgrid[low[1]:high[1]+1,low[0]:high[0]+1]; q=np.stack([xx+.5,yy+.5],-1)-t[0]
        ab=np.linalg.solve(np.stack([t[1]-t[0],t[2]-t[0]],axis=1),q.reshape(-1,2).T).T.reshape(*q.shape[:2],2)
        bary=np.concatenate([1-ab.sum(-1,keepdims=True),ab],-1); mask=(bary>=-1e-9).all(-1)
        if not mask.any(): raise ValueError('Triangle has no texel center; increase resolution')
        y,x=yy[mask],xx[mask]; b=bary[mask]; strict=(b>1e-8).all(-1)
        if np.any(inside[y,x]&strict): raise ValueError('Overlapping UV chart interiors')
        dist,idx=tree.query(b@p,k=1)
        if np.any(dist>1.75*step): raise ValueError('Surface samples too far from mesh; retain source')
        peak=max(peak,float(dist.max())); write=(hit[y,x]<0)|strict; hit[y[write],x[write]]=idx[write]; inside[y,x]|=strict
    coverage=hit>=0
    if not coverage.any(): raise ValueError('Empty UV atlas')
    # Extend only into unused texels, not across chart interiors; no artificial alpha on geometry.
    distance,nearest=distance_transform_edt(~coverage,return_indices=True); pad=(~coverage)&(distance<=padding); hit[pad]=hit[nearest[0][pad],nearest[1][pad]]
    result={}
    for name,data in maps.items():
        a=np.zeros((height,width,data.shape[1]),np.float32); valid=hit>=0; a[valid]=data[hit[valid]]; result[name]=a
    return result,coverage,peak


def run(asset,out,resolution,padding,subdiv=None):
    root=Path(asset).resolve(); out=Path(out).resolve()
    if out.exists() or root in out.parents or out in root.parents: raise ValueError('Separate new output required')
    meta,v,f,xyz,rgba,step=load_inputs(root)
    subdiv_binding=None
    if subdiv is not None:
        from opensubdiv_pack import load_candidate
        if np.any(rgba[:,3]<1-1e-6): raise ValueError('Subdivision candidate requires opaque static asset')
        v,f,m=load_candidate(root,subdiv,v,f,xyz,step)
        subdiv_binding={'manifestSHA256':digest(Path(subdiv)/'subdiv.json'),'meshSHA256':m['meshSHA256'],'level':m['level']}
    if len(f)>1_000_000 or not np.all((rgba>=0)&(rgba<=1)): raise ValueError('Invalid material range or mesh budget')
    maps={'baseColor':rgba}
    with np.load(root/'native_grid.npz',allow_pickle=False) as g:
        if 'attrs' in g and 'layout' in g:
            attrs=g['attrs']; layout=json.loads(str(g['layout'].item()))
            for key in ('roughness','metallic'):
                if key in layout:
                    lo,hi=layout[key]; a=attrs[:,lo:hi]
                    if a.shape!=(len(xyz),1) or not np.isfinite(a).all() or np.any((a<0)|(a>1)): raise ValueError('Invalid '+key)
                    maps[key]=a
    import xatlas
    atlas=xatlas.Atlas(); atlas.add_mesh(np.asarray(v,np.float32),np.asarray(f,np.uint32)); options=xatlas.PackOptions();options.resolution=resolution;options.padding=padding; atlas.generate(pack_options=options)
    pages,_=atlas.get_mesh_vertex_assignement(0)
    if not np.all(np.asarray(pages)==0): raise ValueError('Multiple atlas pages or unassigned vertices unsupported; use source')
    mapping,indices,uv=validate_mapping(v,f,*atlas[0]); w,h=int(atlas.width),int(atlas.height)
    maps,coverage,peak=raster(v,f,uv,mapping,indices,xyz,maps,step,w,h,padding)
    out.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out.parent) as tmp:
        stage=Path(tmp)/'atlas';stage.mkdir()
        # OBJ is a bake/review intermediate; no automatic GLB or material replacement.
        world=native_to_world(v[mapping],meta['nativeUp']); obj=stage/'uv-mesh.obj'
        with obj.open('w') as stream:
            stream.write('# +Z up, original world units; UV candidate only\n')
            for x in world: stream.write('v %.17g %.17g %.17g\n'%tuple(x))
            for x in uv: stream.write('vt %.17g %.17g\n'%tuple(x))
            for face in indices+1: stream.write('f '+' '.join(f'{j}/{j}' for j in face)+'\n')
        np.savez_compressed(stage/'uv-mapping.npz',mapping=mapping,indices=indices,uv=uv,coverage=coverage)
        entries={}
        for key,a in maps.items():
            p=stage/(key+'.npy');np.save(p,a,allow_pickle=False); entries[key]={'path':p.name,'sha256':digest(p),'colorSpace':'sRGB' if key=='baseColor' else 'Non-Color'}
        Image.fromarray(np.rint(maps['baseColor']*255).astype(np.uint8),'RGBA').save(stage/'baseColor.png')
        sources={n:digest(root/n) for n in ('native_grid.npz','native_mesh.npz','stack.json')}
        if any(sources[n]!=json.loads((root/'geometry-source.json').read_text())[n] for n in ('native_grid.npz','native_mesh.npz')): raise ValueError('Source changed')
        (stage/'uv-atlas.json').write_text(json.dumps({'schema':'cover-pack-xatlas/1','sourceSHA256':sources,'subdivisionCandidate':subdiv_binding,'sourceNativeUp':meta['nativeUp'],'pivot':meta['pivot'],'gridOrigin':meta['gridOrigin'],'xatlasVersion':importlib.metadata.version('xatlas'),'atlasSize':[w,h],'padding':padding,'maps':entries,'meshSHA256':digest(obj),'mappingSHA256':digest(stage/'uv-mapping.npz'),'maxNativeSampleDistance':peak,'coverageTexels':int(coverage.sum()),'status':'review-required; nearest surface approximation, not original UV/PBR recovery; static only'},indent=2)+'\n')
        stage.rename(out)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--asset',required=True);p.add_argument('--out',required=True);p.add_argument('--resolution',type=int,choices=[256,512,1024,2048],default=1024);p.add_argument('--padding',type=int,choices=range(2,17),default=8);p.add_argument('--subdiv',help='Separate reviewed OpenSubdiv candidate directory');a=p.parse_args();run(a.asset,a.out,a.resolution,a.padding,a.subdiv)
