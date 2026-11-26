#!/usr/bin/env python3
"""One complete original source-painted animated 2.5D *game* plus REAL 360 sprite stacking.

Mandatory upstream: original pose gate -> GIF/asset ZIP -> Godot + Blender ->
PixiJS8 -> PathFinding A* -> Matter.js -> nipplejs -> optional YUKA NPC AI.
The stacked result is another FULLY OFFLINE interactive HTML (with prior real
engine scripts embedded), not a fake standalone art preview.
"""
from __future__ import annotations
import argparse,json,subprocess,sys,zipfile
from pathlib import Path
from sprite_stacking_bridge import patch_html,archive_original_views,SpriteStackError


def main():
    p=argparse.ArgumentParser()
    p.add_argument('source',type=Path);p.add_argument('--scene',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--seconds',type=int,default=48);p.add_argument('--fps',type=int,default=24)
    p.add_argument('--max-width',type=int,default=720)
    p.add_argument('--export-glb',action='store_true',help='Real glTF 3D horizontal sprite planes for Three.js/Godot/Blender')
    p.add_argument('--all-poses-glb',action='store_true',help='Export separate GLB for each already-approved original actor pose')
    for key in ('pixelorama','opentoonz','mmpose-device','comfyui-url','godot','blender'):
        p.add_argument('--'+key)
    for key in ('pixi-js','pathfinding-js','matter-js','nipple-js','yuka-js'):
        p.add_argument('--'+key,type=Path)
    for key in ('fetch-pixi','fetch-pathfinding','fetch-matter','fetch-nipple','fetch-yuka','preflight-only'):
        p.add_argument('--'+key,action='store_true')
    a=p.parse_args()
    if not a.source.is_file() or not a.scene.is_file():p.error('Original source illustration and scene JSON required')
    if a.fps<24 or not 40<=a.seconds<=60:p.error('Every original animation needs 24+fps / 40–60 seconds')
    sourcecfg=json.loads(a.scene.resolve().read_text('utf8'))
    if not isinstance(sourcecfg.get('sprite_stacking_game',sourcecfg.get('sprite_stacking')),dict):p.error('Set scene.sprite_stacking_game (or sprite_stacking) with original stack.json or four-view art')
    has_ai=isinstance(sourcecfg.get('browser_ai'),dict) and bool(sourcecfg['browser_ai'].get('agents'))
    if a.all_poses_glb and not a.export_glb:p.error('--all-poses-glb requires --export-glb')
    if a.yuka_js and not has_ai:p.error('--yuka-js requires actual source-approved scene.browser_ai.agents')
    if a.fetch_yuka and not has_ai:p.error('--fetch-yuka requires source-approved NPCs')
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    upstream=Path(__file__).with_name('yuka_delivery.py' if has_ai else 'nipplejs_delivery.py')
    cmd=[sys.executable,str(upstream),str(a.source.resolve()),'--scene',str(a.scene.resolve()),
         '--out',str(out),'--seconds',str(a.seconds),'--fps',str(a.fps),'--max-width',str(a.max_width)]
    keys=['pixelorama','opentoonz','mmpose-device','comfyui-url','godot','blender',
          'pixi-js','pathfinding-js','matter-js','nipple-js']
    if has_ai:keys.append('yuka-js')
    for key in keys:
        value=getattr(a,key.replace('-','_'))
        if value:cmd.extend(['--'+key,str(value)])
    keys=['fetch-pixi','fetch-pathfinding','fetch-matter','fetch-nipple','preflight-only']
    if has_ai:keys.append('fetch-yuka')
    for key in keys:
        if getattr(a,key.replace('-','_')):cmd.append('--'+key)
    result=subprocess.run(cmd,check=False)
    if result.returncode:raise SystemExit(result.returncode)
    if a.preflight_only:return
    original_zip=out/'living_scene_assets.zip'
    source_html=out/('living_scene_pixi_ai.html' if has_ai else 'living_scene_pixi_controls.html')
    original_gif=out/'living_scene.gif'
    if any(not v.is_file() for v in (original_zip,source_html,original_gif)):
        raise SpriteStackError('Original full-cel GIF/source ZIP/actual physical game HTML not complete')
    final_html,stats=patch_html(original_zip,a.scene,out/('living_scene_pixi_ai.html' if has_ai else 'living_scene_pixi_controls.html'),out/'living_scene_sprite_stacking.html')
    source_art=archive_original_views(original_zip,a.scene)
    stats['archived_original_views']=source_art['archived_original_views']
    glb_pack=None
    if a.export_glb:
        from sprite_stacking_bridge import config_from_source
        from sprite_stacking_glb import export_from_compiled
        compiled=config_from_source(original_zip,a.scene)
        glb_dir=out/'living_scene_sprite_stacking_glb'
        export_manifest=export_from_compiled(compiled,glb_dir,a.all_poses_glb)
        glb_pack=out/'living_scene_sprite_stacking_glb.zip'
        with zipfile.ZipFile(glb_pack,'w',zipfile.ZIP_DEFLATED,compresslevel=7) as z:
            for path in sorted(glb_dir.rglob('*')):
                if path.is_file():z.write(path,'living_scene_sprite_stacking_glb/'+path.relative_to(glb_dir).as_posix())
        stats['glb_count']=len(export_manifest['glb_files'])
    doc=Path(__file__).parent.parent/'references/sprite-stacking-game-integration.md'
    lic=Path(__file__).parent.parent/'references/LICENSE.sprite-stacking-reference.txt'
    if not doc.is_file() or not lic.is_file():raise SpriteStackError('Original project documentation or open-source reference license missing')
    package=out/'living_scene_sprite_stacking.zip'
    if package.exists():raise SpriteStackError('Stack ZIP already exists; choose new out directory')
    with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED,compresslevel=7) as z:
        z.write(final_html,'living_scene_sprite_stacking/index.html')
        z.write(doc,'living_scene_sprite_stacking/SPRITE_STACKING.md')
        z.write(lic,'living_scene_sprite_stacking/LICENSE.sprite-stacking-reference.txt')
        if glb_pack is not None:z.write(glb_pack,'living_scene_sprite_stacking/living_scene_sprite_stacking_glb.zip')
        z.writestr('living_scene_sprite_stacking/metadata.json',json.dumps(stats,ensure_ascii=False,indent=2))
    with zipfile.ZipFile(original_zip,'a',zipfile.ZIP_DEFLATED,compresslevel=7) as z:
        member='project/browser/living_scene_sprite_stacking.zip'
        if member in z.namelist():raise SpriteStackError('Sprite stacking package already in source ZIP')
        z.write(package,member)
        if glb_pack is not None:z.write(glb_pack,'project/sprite_stacking/living_scene_sprite_stacking_glb.zip')
        z.write(lic,'project/licenses/LICENSE.sprite-stacking-reference.txt')
    with zipfile.ZipFile(original_zip) as z:
        if z.testzip() is not None:raise SpriteStackError('Original source animation ZIP became corrupt')
    print(json.dumps({'game_html':str(final_html),'game_zip':str(package),
                      'original_gif':str(original_gif),'original_assets':str(original_zip),
                      'glb_pack':str(glb_pack) if glb_pack is not None else None,
                      **stats},ensure_ascii=False))

if __name__=='__main__':main()
