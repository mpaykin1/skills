"""TRELLIS.2 native sparse material grid -> horizontal RGBA sprite slices.
CPU conversion also accepts saved native grids; does not invent solid interiors.
"""
import argparse, hashlib, json, math, os, shutil
from pathlib import Path
import numpy as np
from PIL import Image


def export_stack(coords, rgba, voxel_size, out, size=256, up='z', origin=(-.5, -.5, -.5)):
    coords = np.asarray(coords)
    rgba = np.asarray(rgba, dtype=np.float32)
    if coords.ndim != 2 or coords.shape[1] != 3 or rgba.shape != (len(coords), 4) or not len(coords):
        raise ValueError('Expected nonempty Nx3 grid and Nx4 RGBA')
    if not np.isfinite(coords).all() or not np.isfinite(rgba).all() or not np.isfinite(voxel_size) or voxel_size <= 0:
        raise ValueError('Invalid native grid')
    if size not in (128, 256, 512, 1024):
        raise ValueError('Unsupported maximum resolution')
    xyz = (coords.astype(np.float64) + .5) * float(voxel_size) + np.asarray(origin)
    if up == 'y':
        xyz = xyz[:, [0, 2, 1]] * [1, -1, 1]
    elif up != 'z':
        raise ValueError('Specify native up axis y or z')
    lo = xyz.min(0) - voxel_size/2
    hi = xyz.max(0) + voxel_size/2
    extent = hi-lo
    step = max(float(voxel_size), float(extent.max()) / size)
    # One isotropic world-space grid; horizontal canvas is square, not stretched.
    dims = np.maximum(1, np.ceil(extent/step-1e-7).astype(int))
    side = max(int(dims[0]), int(dims[1]))
    depth = int(dims[2])
    if side > size or depth > size:
        raise ValueError('Resolution limit exceeded')
    anchor = lo.copy()
    anchor[:2] -= (side*step - extent[:2])/2
    idx = np.floor((xyz-anchor)/step + 1e-8).astype(int)
    idx = np.clip(idx, 0, [side-1,side-1,depth-1])
    rgba = np.clip(rgba, 0, 1)
    # Premultiplied average RGB, maximum source alpha per occupied cell.
    flat = (idx[:,2]*side+idx[:,1])*side+idx[:,0]
    unique, inv = np.unique(flat, return_inverse=True)
    alpha = rgba[:,3]
    weight = np.bincount(inv, weights=alpha)
    colors = np.stack([np.bincount(inv, weights=rgba[:,c]*alpha)/np.maximum(weight,1e-12) for c in range(3)], axis=1)
    opacity = np.zeros(len(unique),np.float32)
    np.maximum.at(opacity,inv,alpha)
    values = np.rint(np.column_stack((colors,opacity))*255).astype(np.uint8)
    if not values[:,3].any():
        raise ValueError('No visible material in native grid')
    out = Path(out)
    layers = out/'layers'
    layers.mkdir(parents=True,exist_ok=False)
    zz, rem = np.divmod(unique,side*side)
    yy, xx = np.divmod(rem,side)
    files=[]
    for z in range(depth):
        pixels=np.zeros((side,side,4),np.uint8)
        mask=zz==z
        pixels[side-1-yy[mask],xx[mask]]=values[mask]
        name=f'layers/{z:04d}.png'
        Image.fromarray(pixels).save(out/name)
        files.append(name)
    metadata={'format':'rgba-horizontal-layers','layers':files,'size':side,'tileSize':[side,side],
        'layerCount':depth,'layerOrder':'bottom-to-top','spacing':[step]*3,
        'pivot':[0,0,-depth*step/2], 'pivotConvention':'offset from center of padded slice volume to bottom-center, in source world units',
        'gridOrigin':anchor.tolist(),'bounds':[lo.tolist(),hi.tolist()], 'axes':'+X right, +Y top of PNG, +Z up',
        'nativeUp':up,'representation':'sparse surface/material grid, not guaranteed solid','status':'prototype'}
    (out/'stack.json').write_text(json.dumps(metadata,indent=2))
    (out/'asset.json').write_text(json.dumps({**metadata,'id':out.name,'preview':None},indent=2))
    return metadata


def generate(args):
    os.environ.setdefault('OPENCV_IO_ENABLE_OPENEXR','1')
    os.environ.setdefault('PYTORCH_CUDA_ALLOC_CONF','expandable_segments:True')
    import torch
    if not torch.cuda.is_available() or torch.cuda.get_device_properties(0).total_memory < 23*1024**3:
        raise RuntimeError('Official TRELLIS.2 path requires a CUDA GPU in the 24 GB class; no fake CPU fallback')
    from trellis2.pipelines import Trellis2ImageTo3DPipeline
    import o_voxel
    image=Image.open(args.image).convert('RGBA')
    a=np.asarray(image)[:,:,3]
    if not (a<255).any() or not (a>204).any():
        raise ValueError('Use one isolated approved object with a transparent background')
    out=Path(args.out)
    if out.exists(): raise FileExistsError(out)
    out.mkdir(parents=True)
    shutil.copyfile(args.image,out/'reference.png') if Path(args.image).suffix.lower()=='.png' else image.save(out/'reference.png')
    pipe=Trellis2ImageTo3DPipeline.from_pretrained(args.model)
    pipe.cuda()
    mesh=pipe.run(image,seed=args.seed,pipeline_type=args.pipeline)[0]
    coords=mesh.coords.detach().cpu().numpy()
    attrs=mesh.attrs.detach().float().cpu().numpy()
    rgba=np.concatenate((attrs[:,mesh.layout['base_color']],attrs[:,mesh.layout['alpha']]),axis=1)
    step=float(mesh.voxel_size)
    np.savez_compressed(out/'native_grid.npz',coords=coords,rgba=rgba,attrs=attrs,voxel_size=step,origin=np.array([-.5]*3),layout=np.array(json.dumps({k:[v.start,v.stop] for k,v in mesh.layout.items()})))
    # Exact native mesh, before optional GLB postprocess/normalization.
    np.savez_compressed(out/'native_mesh.npz',vertices=mesh.vertices.detach().float().cpu().numpy(),faces=mesh.faces.detach().cpu().numpy())
    (out/'geometry-source.json').write_text(json.dumps({name:hashlib.sha256((out/name).read_bytes()).hexdigest() for name in ('native_grid.npz','native_mesh.npz')},indent=2))
    export_stack(coords,rgba,step,out,args.size,args.up)
    (out/'provenance.json').write_text(json.dumps({'upstream':'https://github.com/microsoft/TRELLIS.2','model':args.model,'seed':args.seed,'pipeline':args.pipeline,'referenceSHA256':hashlib.sha256(Path(args.image).read_bytes()).hexdigest(),'status':'prototype; visual fidelity and animation unverified'},indent=2))
    if args.glb:
        # Export is optional: original O-Voxel material grid remains authoritative.
        model=o_voxel.postprocess.to_glb(vertices=mesh.vertices,faces=mesh.faces,attr_volume=mesh.attrs,coords=mesh.coords,attr_layout=mesh.layout,voxel_size=mesh.voxel_size,aabb=[[-.5]*3,[.5]*3],decimation_target=1000000,texture_size=4096,remesh=False,verbose=True)
        model.export(str(out/'source.glb'))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='mode',required=True)
    for mode in ('generate','convert'):
        s=sub.add_parser(mode);s.add_argument('--out',required=True);s.add_argument('--size',type=int,default=256,choices=[128,256,512,1024]);s.add_argument('--up',choices=['y','z'],required=True)
        if mode=='generate':
            s.add_argument('--image',required=True);s.add_argument('--model',default='microsoft/TRELLIS.2-4B');s.add_argument('--seed',type=int,default=42);s.add_argument('--pipeline',choices=['512','1024','1024_cascade','1536_cascade'],default='1024_cascade');s.add_argument('--glb',action='store_true')
        else:s.add_argument('--grid',required=True)
    a=p.parse_args()
    if a.mode=='generate':generate(a)
    else:
        if Path(a.out).exists():raise FileExistsError(a.out)
        with np.load(a.grid,allow_pickle=False) as g:
            export_stack(g['coords'],g['rgba'],float(g['voxel_size']),a.out,a.size,a.up,g['origin'] if 'origin' in g else [-.5]*3)

if __name__=='__main__':main()
