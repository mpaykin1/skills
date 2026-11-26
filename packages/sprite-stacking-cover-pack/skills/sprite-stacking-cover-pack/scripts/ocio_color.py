"""Explicit OCIO color contract. No fake conversion when OCIO is missing."""
import argparse, hashlib, json, math, os
from pathlib import Path


def digest(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def read_contract(scene, root):
    """Optional backward-compatible profile; new covers must supply one."""
    p = scene.get('colorManagement')
    if p is None:
        return None, {}
    if not isinstance(p, dict) or p.get('schema') != 'cover-pack-color/1':
        raise ValueError('Invalid color contract')
    if p.get('display') != 'sRGB' or p.get('outputEncoding') != 'sRGB' or p.get('alpha') != 'straight':
        raise ValueError('Require sRGB display/output and straight alpha for web delivery')
    if p.get('baseColorSpace') != 'sRGB' or p.get('dataColorSpace') != 'Non-Color':
        raise ValueError('Require Blender sRGB base colors and Non-Color data maps')
    for k in ('view','look','paletteId'):
        if not isinstance(p.get(k), str) or not p[k].strip():
            raise ValueError('Missing reviewed color field: '+k)
    for k,lo,hi in [('exposure',-10,10),('gamma',.1,5)]:
        v=p.get(k)
        if type(v) not in (float,int) or not math.isfinite(v) or not lo<=v<=hi:
            raise ValueError('Invalid '+k)
    root=Path(root).resolve(); rel=p.get('config')
    if not isinstance(rel,str): raise ValueError('Explicit bundled OCIO config required')
    conf=(root/rel).resolve()
    if not conf.is_relative_to(root) or conf.suffix.lower()!='.ocio' or not conf.is_file() or conf.parent==root:
        raise ValueError('Keep OCIO config and LUTs in dedicated scene subdirectory')
    files={}
    for item in sorted(conf.parent.rglob('*')):
        if item.is_symlink(): raise ValueError('Symlink in OCIO bundle')
        if item.is_file(): files[str(item.relative_to(root))]=digest(item)
    if not files or len(files)>512: raise ValueError('Invalid config bundle size')
    # Bundle must be reviewed for portable relative LUT paths and no external context.
    if p.get('bundleReviewed') is not True: raise ValueError('Review OCIO bundle for external LUTs, paths and environment variables')
    return {**p,'config':str(conf.relative_to(root)),'bundleSHA256':files}, files


def check_blender(scene, contract, root):
    if contract is None: return None
    actual=os.environ.get('OCIO')
    config=(Path(root)/contract['config']).resolve()
    if not actual or Path(actual).resolve()!=config:
        raise RuntimeError('Launch Blender with OCIO set to the exact bundled config before startup')
    scene.display_settings.display_device=contract['display']
    scene.view_settings.view_transform=contract['view']
    scene.view_settings.look=contract['look']
    scene.view_settings.exposure=contract['exposure']
    scene.view_settings.gamma=contract['gamma']
    scene.view_settings.use_curve_mapping=False
    return contract


def apply_basecolor(rgb, processor):
    import numpy as np
    x=np.ascontiguousarray(rgb,dtype=np.float32).copy()
    if x.ndim!=3 or x.shape[-1]!=3 or not np.isfinite(x).all(): raise ValueError('Expected finite HxWx3 float RGB')
    processor.applyRGB(x.reshape(-1,3))
    if not np.isfinite(x).all(): raise ValueError('Non-finite OCIO output')
    return x


def convert(a):
    import numpy as np
    from PIL import Image, ImageCms
    import PyOpenColorIO as ocio
    src=Path(a.source).resolve(); dest=Path(a.out).resolve(); config=Path(a.config).resolve()
    meta=dest.with_suffix('.color.json')
    if dest.exists() or meta.exists() or dest.suffix.lower()!='.png': raise ValueError('Output must be a new PNG')
    if a.source_space=='sRGB': raise ValueError('Already sRGB: use original, avoid double conversion')
    if a.role!='base-color': raise ValueError('Never color transform alpha/roughness/normal/metallic/AO/height/density')
    cfg=ocio.Config.CreateFromFile(str(config));cfg.validate()
    for name in (a.source_space,'sRGB'):
        cs=cfg.getColorSpace(name)
        if cs is None or cs.isData():raise ValueError('Expected explicit non-data color space: '+name)
    x=np.load(src,allow_pickle=False)
    if x.ndim!=3 or x.shape[-1]!=4 or not np.issubdtype(x.dtype,np.floating) or not np.isfinite(x).all() or not np.all((x[:,:,3]>=0)&(x[:,:,3]<=1)):
        raise ValueError('Require straight-alpha float HxWx4 NPY; alpha in [0,1]')
    proc=cfg.getProcessor(a.source_space,'sRGB')
    rgb=apply_basecolor(x[:,:,:3],proc.getDefaultCPUProcessor())
    if np.min(rgb)<-1e-5 or np.max(rgb)>1.00001:
        raise ValueError('Out of sRGB gamut/range; author mapping required, no silent clipping')
    y=np.rint(np.clip(np.concatenate((rgb,x[:,:,3:]),axis=2),0,1)*255).astype(np.uint8)
    dest.parent.mkdir(parents=True,exist_ok=True)
    icc=ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
    Image.fromarray(y,'RGBA').save(dest,icc_profile=icc)
    with Image.open(dest) as im:
        if not np.array_equal(np.asarray(im)[:,:,3],y[:,:,3]):raise ValueError('Alpha quantization mismatch')
    meta.write_text(json.dumps({'sourceSHA256':digest(src),'outputSHA256':digest(dest),'configSHA256':digest(config),'processorCacheID':proc.getCacheID(),'ocioVersion':ocio.GetVersion(),'sourceSpace':a.source_space,'targetSpace':'sRGB','alpha':'straight; unchanged except explicit 8-bit quantization','role':'base-color','status':'converted; review palette and gamut'},indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',required=True);p.add_argument('--config',required=True);p.add_argument('--source-space',required=True);p.add_argument('--role',choices=['base-color'],required=True);p.add_argument('--out',required=True);convert(p.parse_args())
