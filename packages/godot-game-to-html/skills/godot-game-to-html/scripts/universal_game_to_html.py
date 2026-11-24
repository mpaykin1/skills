#!/usr/bin/env python3
"""Godot / Unity -> browser export; recovered builds -> original asset extraction.

UnityPy complements AssetRipper with targeted CPU-only extracts and provenance.
Compiled gameplay is NOT reconstructed by either extractor.
"""
from __future__ import annotations
import argparse
import zipfile
from pathlib import Path
import shutil
import subprocess
import sys
from game_to_html import BASE as SCRIPTS
from recover_unity import recover as recover_unity, auto_executable
from unity_to_web import build as build_unity
from export_unity_glb import export as export_unity_glb
from pack_unity_webgl import pack as pack_unity
from recover_unity_code import recover as recover_mono_csharp, find_assemblies, DEFAULT_DLLS
from recover_il2cpp import recover as recover_il2cpp, normalized_source as il2cpp_root, inspect_il2cpp

UNITYPY_VERSION = '1.25.4'


def autodetect(source: Path):
    if source.is_file():
        if source.suffix.lower()=='.pck':return 'godot'
        if source.suffix.lower() in ('.apk','.apkm','.xapk','.ipa','.tipa'):
            if zipfile.is_zipfile(source):
                with zipfile.ZipFile(source) as archive:
                    names=archive.namelist()
                    if any(n.endswith('/global-metadata.dat') for n in names) and any(n.endswith('/libil2cpp.so') for n in names):
                        return 'unity'
            if source.suffix.lower()=='.apk':return 'godot'
            return 'unity'
        if source.suffix.lower() in ('.assets', '.bundle', '.unity3d', '.sharedassets', '.ress', '.resource', '.obb', '.assetbundle', '.unityweb'):return 'unity'
        if source.suffix.lower() == '.html':
            if (source.parent/'Build').is_dir():return 'unity_web'
            return 'godot_web'
        if source.suffix.lower() == '.exe':
            if source.with_name(source.stem+'_Data').is_dir():return 'unity'
            return 'godot'
        raise ValueError('Unrecognized input. Specify an original Unity/Godot project or packed resource')
    if (source/'project.godot').is_file():return 'godot'
    if (source/'Assets').is_dir() and (source/'ProjectSettings'/'ProjectVersion.txt').is_file():return 'unity_project'
    if (source/'Build').is_dir() and (source/'index.html').is_file():return 'unity_web'
    children = [p for p in source.iterdir() if p.is_dir()]
    if len(children) == 1 and (children[0]/'project.godot').is_file():return 'godot'
    if len(children) == 1 and (children[0]/'Assets').is_dir() and (children[0]/'ProjectSettings'/'ProjectVersion.txt').is_file():return 'unity_project'
    if any(x.name.endswith('_Data') for x in children) or (source/'globalgamemanagers').is_file():return 'unity'
    if any(x.name.lower().endswith(('.assets', '.bundle', '.unity3d', '.assetbundle')) for x in source.iterdir()):return 'unity'
    raise ValueError('Unknown game type. Pass original project, Unity *_Data or Godot PCK')


def located_unitypy_python(explicit: str|None) -> str|None:
    if explicit:
        return str(Path(explicit).expanduser().resolve(strict=True))
    cache=Path.home()/'.cache'/'godot-unity-to-html'/'unitypy'/UNITYPY_VERSION
    exe=cache/('Scripts/python.exe' if sys.platform=='win32' else 'bin/python')
    if exe.is_file():return str(exe)
    try:
        import UnityPy
        if UnityPy.__version__ == UNITYPY_VERSION:return sys.executable
    except ImportError:
        pass
    return None


def ensure_unitypy_python(explicit: str|None, install: bool) -> str|None:
    executable=located_unitypy_python(explicit)
    if executable or not install:return executable
    script=SCRIPTS/'install_unitypy.py'
    p=subprocess.run([sys.executable,str(script)],check=True,capture_output=True,text=True,timeout=950)
    executable=p.stdout.strip().splitlines()[-1]
    if not Path(executable).is_file():raise RuntimeError('UnityPy installer did not produce a Python interpreter')
    return executable


def extract_compiled_unity(src:Path,out:Path,extractor:str,ripper:str|None,unitypy_python:str|None):
    done=[]; issues=[]
    want_ripper=extractor in ('auto','assetripper','both')
    want_py=extractor in ('auto','unitypy','both')
    ripper_exe=None
    if want_ripper:
        try:ripper_exe=auto_executable(ripper)
        except (RuntimeError,OSError) as e:
            if extractor=='assetripper' or extractor=='both':
                raise RuntimeError(f'AssetRipper is required: {e}')
            issues.append('AssetRipper unavailable: '+str(e))
    if ripper_exe:
        try:
            recovered=recover_unity(src,out/'recovered_unity',exe=ripper_exe,mode='unity')
            done.append(('AssetRipper Unity project resources',recovered))
        except (RuntimeError,ValueError,OSError) as e:
            if extractor != 'auto':raise
            issues.append('AssetRipper recovery failed: '+str(e))
    if want_py:
        try:
            python=ensure_unitypy_python(unitypy_python,install=(extractor in ('both','unitypy') or not done))
            if python:
                cmd=[python,str(SCRIPTS/'unitypy_extract.py'),str(src),'--out',str(out/'unitypy_assets')]
                subprocess.run(cmd,check=True,timeout=1800)
                done.append(('UnityPy typed original assets',out/'unitypy_assets'))
            elif extractor in ('both','unitypy'):
                raise RuntimeError('UnityPy missing; run install_unitypy.py or specify --unitypy-python')
            else:
                issues.append('UnityPy not installed (optional for auto)')
        except (RuntimeError,OSError,subprocess.SubprocessError,IndexError) as e:
            if extractor != 'auto':raise
            issues.append('UnityPy extraction failed: '+str(e))
    if not done:
        raise RuntimeError('No Unity assets extracted. '+ ' | '.join(issues))
    for title,path in done:print(title+': '+str(path))
    for msg in issues:print('INFO:',msg,file=sys.stderr)
    return done



def recover_compiled_code(src: Path, out: Path, a):
    """Choose Mono ILSpy or IL2CPP Cpp2IL->ILSpy from actual input, never guess."""
    backend=a.code_backend
    if backend=='auto':
        if src.is_file() and src.suffix.lower()=='.dll':
            backend='mono'
        elif src.is_file() and src.suffix.lower() in ('.apk','.xapk','.apkm','.ipa','.tipa'):
            backend='il2cpp'
        else:
            assemblies, markers=find_assemblies(src, DEFAULT_DLLS+tuple(a.extra_assembly))
            backend='mono' if assemblies else 'il2cpp' if markers else 'unknown'
            if backend=='unknown':
                try:inspect_il2cpp(il2cpp_root(src));backend='il2cpp'
                except ValueError:pass
    if backend=='mono':
        result=recover_mono_csharp(src,out/'managed_csharp',ilspy=a.ilspy,
                                   install=not a.no_install_ilspy,extra_assembly=tuple(a.extra_assembly))
        print('ILSpy recovered Mono Unity C# files:',sum(x['cs_files'] for x in result['assemblies']))
        return
    if backend=='il2cpp':
        result=recover_il2cpp(src,out/'il2cpp',cpp2il=a.cpp2il,
                              install=not a.no_install_cpp2il,ilspy=a.ilspy,
                              decompile=not a.no_decompile_il2cpp,
                              install_ilspy=not a.no_install_ilspy)
        print('Cpp2IL approximate recovered assemblies:',len(result['dlls']),
              'ILSpy C# decompiled:',len(result['csharp']))
        return
    raise RuntimeError('Neither Mono managed script DLLs nor an IL2CPP native binary plus metadata were found. Specify correct Unity game folder.')


def run():
    ap=argparse.ArgumentParser(description='Godot / Unity -> WebGL, optional HTML or asset recovery')
    ap.add_argument('source',type=Path)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--engine',choices=['auto','godot','unity'],default='auto')
    ap.add_argument('--mode',choices=['web','single','recover','scenes','sprites','code','visual','stacking'],default='web')
    ap.add_argument('--extractor',choices=['auto','assetripper','unitypy','both'],default='auto',
                    help='For compiled Unity only. both -> AssetRipper Unity project + UnityPy original decoded assets')
    ap.add_argument('--unitypy-python',help='Python interpreter containing UnityPy==1.25.4')
    ap.add_argument('--cpp2il',help='Existing official Cpp2IL development CLI executable')
    ap.add_argument('--no-install-cpp2il',action='store_true',help='Do not build pinned Cpp2IL from official MIT source when missing')
    ap.add_argument('--code-backend',choices=['auto','mono','il2cpp'],default='auto',help='Select Mono ILSpy or IL2CPP Cpp2IL+ILSpy recovery')
    ap.add_argument('--no-decompile-il2cpp',action='store_true',help='Only generate approximate IL2CPP DLLs; skip ILSpy source stage')
    ap.add_argument('--stack-xy',type=int,default=192,help='Sprite stacking horizontal voxel resolution limit')
    ap.add_argument('--stack-z',type=int,default=96,help='Sprite stacking vertical slice limit')
    ap.add_argument('--stack-closed-only',action='store_true',help='Refuse non-watertight original GLB instead of shell stacking')
    ap.add_argument('--mesh-visual',action='store_true',help='Opt out of default sprite-stacking-first visuals; use original Three.js GLB viewer')
    ap.add_argument('--ktx-manifest',help='Optional Khronos KTX2 candidate manifest for offline Three.js GLB visuals')
    ap.add_argument('--ilspy',help='Existing ilspycmd executable (Mono C# decompilation only)')
    ap.add_argument('--no-install-ilspy',action='store_true',help='Require existing ilspycmd, do not install via dotnet')
    ap.add_argument('--with-csharp',action='store_true',help='On --mode recover: restore Mono C# via ILSpy or approximate IL2CPP DLLs via Cpp2IL+ILSpy')
    ap.add_argument('--extra-assembly',action='append',default=[],help='Additional Mono DLL basename for ILSpy')
    ap.add_argument('--godot',help='Godot editor executable')
    ap.add_argument('--gdre',help='GDRETools executable')
    ap.add_argument('--ripper',help='AssetRipper executable')
    ap.add_argument('--unity',help='Unity Editor executable with WebGL module')
    ap.add_argument('--max-mb',type=int,default=256)
    ap.add_argument('--pixi-js',help='Offline PixiJS browser runtime path (for --mode sprites)')
    ap.add_argument('--no-install',action='store_true',help='Do not install PixiJS on demand')
    ap.add_argument('--export-glb',action='store_true',help='After native Unity WebGL export, also export original scene GLBs using UnityGLTF')
    ap.add_argument('--all-scenes',action='store_true',help='For UnityGLTF: include all Unity scenes, not only enabled Build Settings scenes')
    a=ap.parse_args()
    src=a.source.expanduser().resolve(strict=True)
    out=a.out.expanduser().resolve()
    if a.mode=='stacking' or (a.mode=='visual' and not a.mesh_visual and not a.ktx_manifest):
        # New visual default: maximize TRUE sprite stacking from source 3D volumes.
        # Never flatten a single PNG into counterfeit depth; if geometry is unsuitable,
        # native GLB viewer stays the safety fallback for 'visual' mode only.
        bridge=SCRIPTS.parent.parent/'sprite-stacking-priority'/'scripts'/'stack_to_html.py'
        cmd=[sys.executable,str(bridge),str(src),'--out',str(out),
             '--xy',str(a.stack_xy),'--z',str(a.stack_z)]
        if a.unity:cmd+=['--unity',a.unity]
        if a.all_scenes:cmd+=['--all-scenes']
        if a.stack_closed_only:cmd+=['--closed-only']
        if a.no_install:cmd+=['--no-install']
        if a.mode=='stacking':
            subprocess.run(cmd,check=True)
            return
        result=subprocess.run(cmd,check=False)
        if result.returncode==0:return
        print('SPRITE STACKING unavailable for this source; preserving original GLB visual path.',file=sys.stderr)
    if a.mode=='visual':
        # Original GLB or original Unity project -> visual HTML. This does NOT
        # replace the native engine gameplay/WebGL route.
        bridge=SCRIPTS.parent.parent/'three-glb-visual-runtime'/'scripts'/'three_glb_to_html.py'
        cmd=[sys.executable,str(bridge),str(src),'--out',str(out)]
        if a.unity:cmd+=['--unity',a.unity]
        if a.all_scenes:cmd+=['--all-scenes']
        if a.ktx_manifest:cmd+=['--ktx-manifest',a.ktx_manifest]
        if a.no_install:cmd+=['--no-install']
        subprocess.run(cmd,check=True)
        return
    if a.mode=='code':
        if a.engine=='godot' or src.suffix.lower() in ('.pck','.godot'):
            raise ValueError('C# / IL2CPP recovery is only for authorized Unity games, not Godot')
        recover_compiled_code(src,out,a)
        return
    if a.mode=='sprites':
        if not src.is_file() or src.suffix.lower()!='.json':
            raise ValueError('PixiJS sprites mode needs original scene JSON or UnityPy unitypy_manifest.json')
        bridge=SCRIPTS.parent.parent/'pixi-original-sprites'/'scripts'/'pixi_sprites_to_html.py'
        cmd=[sys.executable,str(bridge),str(src),'--out',str(out/'sprites.html'),'--max-mb',str(a.max_mb)]
        if a.pixi_js:cmd+=['--pixi-js',a.pixi_js]
        if a.no_install:cmd+=['--no-install']
        subprocess.run(cmd,check=True)
        return
    kind=autodetect(src)
    if a.engine=='godot' and not kind.startswith('godot'):
        raise ValueError('Requested Godot but input is not Godot')
    if a.engine=='unity' and not kind.startswith('unity'):
        raise ValueError('Requested Unity but input is not Unity')
    if kind.startswith('godot'):
        if a.mode=='scenes' or a.export_glb:raise ValueError('UnityGLTF mode requires an ORIGINAL Unity project')
        if kind=='godot_web':
            if a.mode!='single':raise ValueError('For prebuilt Godot Web use --mode single')
            subprocess.run([sys.executable,str(SCRIPTS/'pack_single_html.py'),str(src),'--out',str(out/'game.html')],check=True)
            return
        cmd=[sys.executable,str(SCRIPTS/'game_to_html.py'),str(src),'--out',str(out),'--mode',a.mode]
        if a.godot:cmd.extend(['--godot',a.godot])
        if a.gdre:cmd.extend(['--gdre',a.gdre])
        subprocess.run(cmd,check=True)
        return
    if kind=='unity_web':
        if a.mode=='scenes' or a.export_glb:raise ValueError('Scene GLB export requires original Unity project')
        if a.mode=='recover':raise ValueError('WebGL already exported')
        web=src/'index.html' if src.is_dir() else src
        if a.mode=='web':print('Existing Unity WebGL export:',web.parent);return
        pack_unity(web,out/'game.html',a.max_mb)
        return
    if kind=='unity_project':
        if a.mode=='recover':print('Original Unity project already present:',src);return
        if a.mode=='scenes':
            export_unity_glb(src,out,a.unity,a.all_scenes)
            return
        project=src
        if not (project/'Assets').is_dir():project=next(p for p in src.iterdir() if p.is_dir() and (p/'Assets').is_dir())
        web=build_unity(project,out,a.unity)
        if a.export_glb:export_unity_glb(project,out,a.unity,a.all_scenes)
        if a.mode=='single':pack_unity(web/'index.html',out/'game.html',a.max_mb)
        return
    if kind=='unity':
        if a.mode=='scenes' or a.export_glb:raise ValueError('UnityGLTF requires ORIGINAL Unity project, not recovered compiled assets')
        if src.is_file() and src.suffix.lower()=='.exe':
            data_dir=src.with_name(src.stem+'_Data')
            if data_dir.is_dir():src=data_dir
        extract_compiled_unity(src,out,a.extractor,a.ripper,a.unitypy_python)
        if a.mode=='recover' and a.with_csharp:
            recover_compiled_code(src,out,a)
        if a.mode!='recover':
            raise RuntimeError('Original Unity assets recovered; compiled C#/IL2CPP logic is NOT automatically playable in HTML. Provide original project or implement a faithful gameplay port.')
        return
    raise ValueError('Unsupported input: '+kind)

if __name__=='__main__':
    try:run()
    except (OSError,RuntimeError,ValueError,subprocess.SubprocessError) as e:sys.exit('ERROR: '+str(e))
