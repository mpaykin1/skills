#!/usr/bin/env python3
"""Export an original Godot 4 GDScript game through the official Web templates.

The input tree is NEVER edited. Existing Windows-only export presets are
preserved and a Web preset is appended to the temporary copy when necessary.
Optional lossless resource optimizations run only on that temporary copy.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

SCRIPT_DIR=Path(__file__).resolve().parent
IGNORED_DIRS={'.godot','.git','.import','node_modules','build','dist','target','Library','Temp'}

def locate_project(path:Path)->Path:
    path=path.resolve()
    if (path/'project.godot').is_file():return path
    if not path.is_dir():raise ValueError(f'No Godot project folder: {path}')
    matches=[p for p in path.glob('*/project.godot') if p.is_file()]
    if len(matches)==1:return matches[0].parent
    raise ValueError('Expected exactly one project.godot at root or one child folder')

def inspect(project:Path):
    gd=(project/'project.godot').read_text(encoding='utf-8-sig',errors='replace')
    native=[];csharp=[]
    for p in project.rglob('*'):
        if any(x in IGNORED_DIRS for x in p.relative_to(project).parts):continue
        if p.is_file() and p.suffix=='.gdextension':native.append(str(p.relative_to(project)))
        if p.is_file() and p.suffix in {'.cs','.csproj','.sln'}:csharp.append(str(p.relative_to(project)))
    if csharp:raise RuntimeError('Godot C# detected; Godot 4 C# Web export is unsupported: '+', '.join(csharp[:4]))
    if native:raise RuntimeError('GDExtension detected; verify Web module explicitly: '+', '.join(native[:4]))
    if 'config_version=3' in gd or 'config_version=2' in gd:raise RuntimeError('Old Godot project: this exporter targets Godot 4')

def copytree_safe(src:Path,dst:Path):
    def ignore(path,names):
        return {n for n in names if n in IGNORED_DIRS or (Path(path)/n).is_symlink()}
    shutil.copytree(src,dst,ignore=ignore,symlinks=False)

def ensure_web_preset(project:Path,preset:str):
    p=project/'export_presets.cfg'
    content=p.read_text(encoding='utf-8-sig',errors='replace') if p.exists() else ''
    if re.search(r'^name\s*=\s*"'+re.escape(preset)+r'"\s*$',content,re.M):return
    if preset!='Web':raise RuntimeError(f'No existing export preset {preset!r}')
    nums=[int(m) for m in re.findall(r'^\[preset\.(\d+)\]$',content,re.M)]
    index=max(nums,default=-1)+1
    new=f'''\n[preset.{index}]\n\nname="Web"\nplatform="Web"\nrunnable=true\nadvanced_options=false\ndedicated_server=false\ncustom_features=""\nexport_filter="all_resources"\ninclude_filter=""\nexclude_filter="tools/*, build/*, release/*, shots/*, docs/*"\nexport_path="index.html"\nscript_export_mode=2\n\n[preset.{index}.options]\n\nvariant/extensions_support=false\nhtml/export_icon=true\nhtml/custom_html_shell=""\nhtml/head_include=""\nhtml/canvas_resize_policy=2\nhtml/focus_canvas_on_start=true\nprogressive_web_app/enabled=false\n\n'''
    p.write_text(content.rstrip()+'\n'+new,encoding='utf-8')

def ensure_web_renderer(project:Path):
    """Override only the cloned project's .web setting. Unsupported effects need manual fixes."""
    p=project/'project.godot'
    content=p.read_text(encoding='utf-8-sig')
    k='rendering/renderer/rendering_method.web'
    if re.search(r'^'+re.escape(k)+r'\s*=',content,re.M):
        content=re.sub(r'^'+re.escape(k)+r'\s*=.*$',k+'="gl_compatibility"',content,flags=re.M)
    elif re.search(r'^\[rendering\]\s*$',content,re.M):
        content=re.sub(r'^(\[rendering\]\s*)$',r'\1\n'+k+'="gl_compatibility"',content,count=1,flags=re.M)
    else:content+='\n[rendering]\n'+k+'="gl_compatibility"\n'
    p.write_text(content,encoding='utf-8')

def main():
    ap=argparse.ArgumentParser(description='Godot original Web export with opt-in optimization')
    ap.add_argument('project',type=Path)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--godot',default=None)
    ap.add_argument('--preset',default='Web')
    ap.add_argument('--mode',choices=['web','single'],default='web')
    ap.add_argument('--lossless',action='store_true',help='Run oxipng on staged PNG assets')
    ap.add_argument('--glb',choices=['none','dedup','gltfpack'],default='none',help='Opt-in, scene verification required')
    ap.add_argument('--ogg-quality',type=int,default=None,help='Opt-in lossy audio')
    args=ap.parse_args()
    project=locate_project(args.project)
    inspect(project)
    editor=args.godot or shutil.which('godot') or shutil.which('godot4') or shutil.which('Godot')
    if not editor:raise RuntimeError('Godot editor missing. Install matching Godot editor AND Web export templates.')
    out=args.out.resolve()
    if out==project or project in out.parents:raise RuntimeError('Output must be outside the input project folder')
    out.mkdir(parents=True,exist_ok=True)
    webdir=out/'web';webdir.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='godot-preserve-') as temp:
        work=Path(temp)/'source';copytree_safe(project,work)
        ensure_web_preset(work,args.preset)
        ensure_web_renderer(work)
        if args.lossless or args.glb!='none' or args.ogg_quality is not None:
            opt=[sys.executable,str(SCRIPT_DIR/'optimize_assets.py'),str(work),'--apply','--glb',args.glb]
            if args.ogg_quality is not None:opt+=['--ogg-quality',str(args.ogg_quality)]
            subprocess.run(opt,check=True)
        print('Original game: Godot import in temporary WebGL2-compatible copy')
        subprocess.run([editor,'--headless','--path',str(work),'--editor','--import','--quit'],check=True,timeout=1200)
        print('Export native Godot Web build')
        subprocess.run([editor,'--headless','--path',str(work),'--export-release',args.preset,str(webdir/'index.html')],check=True,timeout=1200)
        if not (webdir/'index.html').exists():raise RuntimeError('Web export did not produce index.html')
    if args.mode=='single':
        subprocess.run([sys.executable,str(SCRIPT_DIR/'pack_single_html.py'),str(webdir/'index.html'),'--out',str(out/'game.html')],check=True)
        print('EXPERIMENTAL single HTML:',out/'game.html')
    print('Original engine Web build:',webdir)
    print('Original project not modified:',project)

if __name__=='__main__':
    try:main()
    except (ValueError,RuntimeError,subprocess.CalledProcessError,subprocess.TimeoutExpired) as exc:sys.exit('ERROR: '+str(exc))
