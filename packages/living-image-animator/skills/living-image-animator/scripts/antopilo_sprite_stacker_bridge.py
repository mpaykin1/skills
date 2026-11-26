#!/usr/bin/env python3
"""Bidirectional lossless legacy antopilo/SpriteStacker Godot 3 editor PNG layer bridge.

Original editor Export.gd writes 0.png, 1.png, ..., in DrawingBoard.Layers order.
This adapter does not synthesize views, poses, layers, texture or geometry. All
source RGBA pixels and original PNG file bytes are copied, never reencoded.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import zipfile
from pathlib import Path
from PIL import Image

UPSTREAM = 'https://github.com/antopilo/SpriteStacker'
COMMIT = '20b8b3ffae50e709292a428347997a89d38379b6'
class LegacyEditorError(ValueError):
    pass

def fail(msg):
    raise LegacyEditorError('SpriteStacker Godot3 editor interchange: ' + msg)

def safe_relative(root: Path, name: str) -> Path:
    if not isinstance(name, str) or not name or len(name) > 260 or '\\' in name or ':' in name or name.startswith('/'):
        fail('Unsafe source PNG path')
    pieces = name.split('/')
    if any(x in ('', '.', '..') for x in pieces):fail('Unsafe relative filename')
    path = (root/name).resolve()
    if root.resolve() not in path.parents or not path.is_file():fail('Source file missing: '+name)
    return path

def validate_bytes(raw: bytes, dim=None):
    import io
    if len(raw) > 15_000_000:fail('Original individual PNG larger than 15MB')
    try:
        with Image.open(io.BytesIO(raw)) as im:
            if im.format!='PNG':fail('Expected original PNG image')
            if im.mode not in ('RGBA','LA','P'):fail('Source needs actual alpha-capable PNG')
            if dim is not None and im.size != (dim,dim):fail('All slices must have the same square XY dimensions')
            if not 16<=im.width<=512 or im.height!=im.width:fail('XY slice size must be square, 16..512px')
            rgba=im.convert('RGBA'); alpha=rgba.getchannel('A')
            return im.width, hashlib.sha256(rgba.tobytes()).hexdigest(), alpha.getextrema()[1]>0,alpha.getextrema()[0]<255
    except (OSError,ValueError) as e:fail('Corrupt or invalid original PNG: '+str(e))

def inspect_layers(paths):
    if not 8<=len(paths)<=160:fail('8..160 real Z PNG layers required')
    dim=None; hashes=set(); nonempty=0; transparency=False; bytecount=0
    for p in paths:
        if not p.is_file():fail('Missing PNG: '+str(p))
        raw=p.read_bytes();n,sha,visible,has_alpha=validate_bytes(raw,dim)
        dim=n;hashes.add(sha);nonempty+=int(visible);transparency=transparency or has_alpha;bytecount+=len(raw)
        if bytecount > 150_000_000:fail('Layer PNG files exceed 150MB source budget')
    if len(hashes)<4 or nonempty<4:fail('Flat repeated card / empty stack: need 4 actual distinct non-empty Z sections')
    if not transparency:fail('PNG source has no transparent regions')
    if len(paths)*dim*dim*4 > 256_000_000:fail('Estimated RGBA GPU volume >256MB')
    return {'size':dim,'layers':len(paths),'distinct_slices':len(hashes),'visible_slices':nonempty,'bytes':bytecount}

def certified_pose_sha(approved_zip, pose_relative):
    """Return SHA256 only after original full-body source gate and cast-frame membership."""
    from pixijs_bridge import load_scene
    approved=Path(approved_zip).resolve()
    if not approved.is_file():fail('Certified approved actor source ZIP is required')
    verified=load_scene(approved)
    if not isinstance(pose_relative,str):fail('Specify actual original character source PNG relpath')
    paths={p for a in verified['actors'] for p in a['frames']}
    if pose_relative not in paths:fail('Original source pose is not in approved full-body cast')
    with zipfile.ZipFile(approved) as z:
        raw=z.read('project/inputs/'+pose_relative)
    return hashlib.sha256(raw).hexdigest()

def free_destination(dest):
    if dest.exists() and any(dest.iterdir()):fail('Target must be empty: '+str(dest))
    dest.mkdir(parents=True,exist_ok=True)

def canonical_from_editor(editor_dir, out_dir, spacing=(1.,1.,1.), pivot=(0.,0.,0.), source_pose_sha=None):
    source=Path(editor_dir).resolve(); dest=Path(out_dir).resolve()
    if not source.is_dir():fail('Original SpriteStacker exported folder missing')
    if source==dest or source in dest.parents or dest in source.parents:fail('Input and output directories must be separate')
    imgs=list(source.glob('*.png'))
    if any(not re.fullmatch(r'(0|[1-9][0-9]*)\.png',p.name) for p in imgs):
        fail('Only native editor numbered PNG exports 0.png, 1.png, ... accepted')
    by_index={int(p.stem):p for p in imgs}
    if len(imgs)!=len(by_index) or set(by_index)!=set(range(len(imgs))):
        fail('Native layer indices must be contiguous 0..N-1; do not guess layer order')
    ordered=[by_index[i] for i in range(len(imgs))]
    info=inspect_layers(ordered)
    if len(spacing)!=3 or any(not 0.0005<=float(x)<=50 for x in spacing):fail('Invalid source XYZ spacing')
    if len(pivot)!=3 or any(not -50000<=float(x)<=50000 for x in pivot):fail('Invalid source pivot')
    if source_pose_sha is not None and not re.fullmatch(r'[a-f0-9]{64}',source_pose_sha):
        fail('Source actor pose requires exact 64-byte-hex SHA256 provenance')
    free_destination(dest)
    layer_dir=dest/'layers';layer_dir.mkdir()
    originals={};ordered_names=[]
    for i,p in enumerate(ordered):
        name=f'layers/{i:04d}.png';target=dest/name
        shutil.copyfile(p,target)
        if hashlib.sha256(target.read_bytes()).digest()!=hashlib.sha256(p.read_bytes()).digest():
            fail('Original editor PNG bytes modified during conversion')
        ordered_names.append(name)
        originals[p.name]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(), 'to':name}
    manifest={'layers':ordered_names,'spacing':list(spacing),'pivot':list(pivot),'size':info['size'],
              'source':'antopilo/SpriteStacker exported numbered PNG layers @ '+COMMIT}
    if source_pose_sha:manifest['source_pose_sha256']=source_pose_sha
    (dest/'stack.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf8')
    (dest/'editor_source.json').write_text(json.dumps({'upstream':UPSTREAM,'revision':COMMIT,
           'format':'Godot 3 editor numbered PNG export; 0.png is bottom Z layer',
           'source_pngs':originals,'quality':info},ensure_ascii=False,indent=2),'utf8')
    return dest/'stack.json',info

def editor_from_canonical(manifest_path, out_dir):
    manifest=Path(manifest_path).resolve();dest=Path(out_dir).resolve()
    if not manifest.is_file() or manifest.name!='stack.json':fail('Provide existing authentic stack.json')
    if dest in manifest.parents or manifest.parent in dest.parents:fail('Input and output directories must be separate')
    config=json.loads(manifest.read_text('utf8'))
    if not isinstance(config,dict) or set(config)-{'layers','spacing','pivot','size','source_pose_sha256','source','author','material'}:
        fail('Unexpected canonical stack.json structure')
    layers=config.get('layers');size=config.get('size')
    if not isinstance(layers,list) or len(set(layers))!=len(layers):fail('Duplicate/missing Z slice paths')
    if type(size)!=int:fail('Missing canonical stack size')
    ordered=[safe_relative(manifest.parent,rel) for rel in layers]
    info=inspect_layers(ordered)
    if info['size']!=size:fail('Manifest and original PNG dimensions differ')
    free_destination(dest)
    for i,p in enumerate(ordered):
        target=dest/f'{i}.png'
        shutil.copyfile(p,target)
        if p.read_bytes()!=target.read_bytes():fail('Loss of native RGBA PNG during export')
    (dest/'SOURCE.txt').write_text('SpriteStacker (Godot 3.1 editor): import this numbered PNG layer folder.\n'
        'Layers run 0..N-1 bottom to top; do not reorder.\n'
        'Upstream https://github.com/antopilo/SpriteStacker (MIT).\n'
        'Original stack.json and PNG source remain unchanged.\n','utf8')
    return dest,info

def main():
    p=argparse.ArgumentParser(description='Legacy Godot3 antopilo SpriteStacker <-> canonical original PNG stack.json')
    s=p.add_subparsers(dest='mode',required=True)
    incoming=s.add_parser('import-editor',help='Original antopilo export folder (0.png..N.png) to stack.json')
    incoming.add_argument('input',type=Path);incoming.add_argument('out',type=Path)
    incoming.add_argument('--spacing',nargs=3,type=float,default=[1,1,1]);incoming.add_argument('--pivot',nargs=3,type=float,default=[0,0,0])
    incoming.add_argument('--approved-zip',type=Path,help='Validated full-body artist asset ZIP if importing an actor stack')
    incoming.add_argument('--pose-relative',help='Original approved actor source frame path within ZIP')
    outgoing=s.add_parser('export-editor',help='Existing canonical stack.json to original editor PNG folder')
    outgoing.add_argument('input',type=Path);outgoing.add_argument('out',type=Path)
    a=p.parse_args()
    if a.mode=='import-editor':
        if bool(a.approved_zip)!=bool(a.pose_relative):fail('Approved actor pose ZIP and path must be supplied together')
        pose_sha=certified_pose_sha(a.approved_zip,a.pose_relative) if a.approved_zip else None
        result,meta=canonical_from_editor(a.input,a.out,spacing=a.spacing,pivot=a.pivot,source_pose_sha=pose_sha)
    else:result,meta=editor_from_canonical(a.input,a.out)
    print(json.dumps({'result':str(result),'same_source_png_bytes':True,'quality':meta},ensure_ascii=False))

if __name__=='__main__':main()
