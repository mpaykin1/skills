#!/usr/bin/env python3
"""Original antopilo editor PNG layers -> shared stack.json and additive Godot4 atlas / Three.js optional preview.

Does not run or replace the strict original game character motion gate. This is
only source asset interchange, not new approved character action artwork.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import subprocess
import sys
import zipfile
from pathlib import Path
from PIL import Image
from antopilo_sprite_stacker_bridge import canonical_from_editor, editor_from_canonical, certified_pose_sha


def delivery(editor_folder, out, *, spacing=(1,1,1),pivot=(0,0,0),three_js=None,approved_zip=None,pose_relative=None):
    out=Path(out).resolve()
    if out.exists() and any(out.iterdir()):raise ValueError('Use a fresh output destination')
    out.mkdir(parents=True,exist_ok=True)
    canonical=out/'canonical_source'
    if bool(approved_zip)!=bool(pose_relative):raise ValueError('Actor pose ZIP and source frame relpath must be supplied together')
    pose_sha=certified_pose_sha(approved_zip,pose_relative) if approved_zip else None
    manifest,stats=canonical_from_editor(editor_folder,canonical,spacing,pivot,pose_sha)
    edited=out/'legacy_editor';editor_from_canonical(manifest,edited)
    # Match the actual Godot4 Shader Stacker contract: bottom source slice in BOTTOM row.
    layers=json.loads(manifest.read_text('utf8'))['layers'];imgs=[]
    for rel in layers:
        with Image.open(canonical/rel) as im:imgs.append(im.convert('RGBA').copy())
    size=stats['size'];sheet=Image.new('RGBA',(size,len(imgs)*size))
    for i,frame in enumerate(imgs):sheet.paste(frame,(0,(len(imgs)-1-i)*size))
    for i,frame in enumerate(imgs):
        if sheet.crop((0,(len(imgs)-1-i)*size,size,(len(imgs)-i)*size)).tobytes()!=frame.tobytes():
            raise ValueError('Godot4 atlas round-trip damaged original pixel alpha')
    godot=out/'godot4_shader_stacker';godot.mkdir()
    sheet.save(godot/'sprite_sheet_vertical.png',format='PNG',compress_level=6)
    attributes=json.loads(manifest.read_text('utf8'))
    (godot/'sprite_sheet_settings.json').write_text(json.dumps({
        'addon':'x3cca/Shader-Stacker','node':'SpriteStack','layers':len(imgs),
        'pitch':attributes['spacing'][2]/attributes['spacing'][0],
        'sheet':'sprite_sheet_vertical.png','bottom_slice_at_bottom_row':True,
        'original_source_stack':'../canonical_source/stack.json',
        'native_godot4_addon':'Already integrated via shader_stacker_bridge.py',
        'original_source_unchanged':True},ensure_ascii=False,indent=2),'utf8')
    html=None
    if three_js is not None:
        bridge=Path(__file__).with_name('sprite_stack_asset_preview.py')
        html=out/'living_scene_antopilo_360.html'
        p=subprocess.run([sys.executable,str(bridge),'--stack',str(manifest),'--out',str(html),'--three-js',str(Path(three_js).resolve())],capture_output=True,text=True,check=False)
        if p.returncode:raise ValueError('Real Three.js original 3D preview failed: '+p.stderr[-1300:])
    license=Path(__file__).resolve().parent.parent/'references'/'LICENSE.antopilo-SpriteStacker.txt'
    if not license.is_file():raise ValueError('Authentic antopilo MIT license notice missing')
    bundle=out/'living_scene_antopilo_spritestacker.zip'
    with zipfile.ZipFile(bundle,'w',zipfile.ZIP_DEFLATED,compresslevel=7) as z:
        for base in (canonical,edited,godot):
            for path in sorted(base.rglob('*')):
                if path.is_file():z.write(path,(Path('antopilo_spritestacker')/path.relative_to(out)).as_posix())
        z.write(license,'antopilo_spritestacker/LICENSE.antopilo-SpriteStacker.txt')
        if html:z.write(html,'antopilo_spritestacker/living_scene_antopilo_360.html')
    with zipfile.ZipFile(bundle) as z:
        if z.testzip():raise ValueError('SpriteStacker conversion bundle ZIP corrupted')
    return {'canonical_stack':str(manifest),'godot4_sheet':str(godot/'sprite_sheet_vertical.png'),
            'legacy_godot3_editor_folder':str(edited),'threejs_html':str(html) if html else None,
            'bundle':str(bundle),'source_bytes_unchanged':True,'source_pngs':len(imgs),
            'sha256':hashlib.sha256(bundle.read_bytes()).hexdigest()}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--editor-folder',required=True,type=Path);p.add_argument('--out',required=True,type=Path)
    p.add_argument('--spacing',nargs=3,type=float,default=[1.,1.,1.]);p.add_argument('--pivot',nargs=3,type=float,default=[0.,0.,0.])
    p.add_argument('--approved-zip',type=Path,help='Original approved full-body assets ZIP for an actor volume')
    p.add_argument('--pose-relative',help='Original approved actor source pose PNG within the ZIP')
    p.add_argument('--three-js',type=Path,help='Existing genuine three.module.js for optional 360 HTML')
    a=p.parse_args()
    print(json.dumps(delivery(a.editor_folder,a.out,spacing=a.spacing,pivot=a.pivot,three_js=a.three_js,approved_zip=a.approved_zip,pose_relative=a.pose_relative),ensure_ascii=False))
