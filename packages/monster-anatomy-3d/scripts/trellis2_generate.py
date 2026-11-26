#!/usr/bin/env python3
"""Official TRELLIS.2 Image-to-3D API adapter -> PBR GLB.

Must run using Python from the official TRELLIS.2 CUDA environment, with the
TRELLIS.2 repository on PYTHONPATH (or as cwd) and its pretrained model files.
This yields an unrigged sculpt/reference mesh, NOT anatomical muscle topology.
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import sys

os.environ.setdefault('OPENCV_IO_ENABLE_OPENEXR','1')
os.environ.setdefault('PYTORCH_CUDA_ALLOC_CONF','expandable_segments:True')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--input',required=True,help='single-object image, preferably transparent background')
    parser.add_argument('--output',required=True,help='unrigged PBR GLB')
    parser.add_argument('--repo',default='',help='official TRELLIS.2 checkout')
    parser.add_argument('--model',default='microsoft/TRELLIS.2-4B')
    parser.add_argument('--seed',type=int,default=42)
    parser.add_argument('--pipeline',choices=('512','1024','1024_cascade','1536_cascade'),default='512')
    parser.add_argument('--faces',type=int,default=140000)
    parser.add_argument('--texture-size',type=int,choices=(512,1024,2048,4096),default=2048)
    parser.add_argument('--allow-low-vram',action='store_true')
    parser.add_argument('--webp',action='store_true',help='use WebP texture extension; default PNG for compatibility')
    opt=parser.parse_args()
    if not 5000 <=opt.faces<=1000000:parser.error('--faces must be 5000..1000000')
    image=Path(opt.input).expanduser().resolve()
    if not image.is_file():parser.error('input image not found: '+str(image))
    output=Path(opt.output).expanduser().resolve()
    if opt.repo:
        repo=Path(opt.repo).expanduser().resolve()
        if not (repo/'trellis2/pipelines/trellis2_image_to_3d.py').is_file():
            parser.error('official TRELLIS.2 checkout missing: '+str(repo))
        sys.path.insert(0,str(repo))
    try:
        import torch
        import o_voxel
        from PIL import Image
        from trellis2.pipelines import Trellis2ImageTo3DPipeline
    except ImportError as exc:
        raise SystemExit('TRELLIS.2 CUDA environment is not installed; use official setup.sh: '+str(exc)) from exc
    if not torch.cuda.is_available():
        raise SystemExit('NVIDIA CUDA GPU required; no CUDA device detected. Refusing fabricated GLB output.')
    props=torch.cuda.get_device_properties(0)
    if props.total_memory < 22 * 1024**3 and not opt.allow_low_vram:
        raise SystemExit('TRELLIS.2 officially recommends >=24 GB GPU VRAM; use --allow-low-vram only if supported.')
    source=Image.open(image)
    if source.mode not in ('RGB','RGBA'):source=source.convert('RGB')
    pipeline=Trellis2ImageTo3DPipeline.from_pretrained(opt.model)
    pipeline.cuda()
    meshes=pipeline.run(source, seed=opt.seed, pipeline_type=opt.pipeline)
    if not meshes:raise RuntimeError('TRELLIS.2 returned no mesh')
    mesh=meshes[0]
    mesh.simplify(16777216)  # Official nvdiffrast upper bound.
    glb=o_voxel.postprocess.to_glb(
        vertices=mesh.vertices,faces=mesh.faces,attr_volume=mesh.attrs,
        coords=mesh.coords,attr_layout=mesh.layout,voxel_size=mesh.voxel_size,
        aabb=[[-0.5,-0.5,-0.5],[0.5,0.5,0.5]],
        decimation_target=opt.faces,texture_size=opt.texture_size,
        remesh=True,remesh_band=1,remesh_project=0,verbose=True)
    output.parent.mkdir(parents=True,exist_ok=True)
    glb.export(str(output),extension_webp=opt.webp)
    if not output.exists() or output.stat().st_size < 1000:
        raise RuntimeError('TRELLIS.2 GLB export failed')
    print('TRELLIS.2 UNRIGGED draft:',output,'bytes:',output.stat().st_size)

if __name__=='__main__':main()
