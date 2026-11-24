#!/usr/bin/env python3
"""Export original Unity scenes as GLB using pinned Khronos UnityGLTF inside Unity Editor.

Visual-assets-only pathway: the original Unity WebGL build retains gameplay.
Operates on a temporary copy. Does not modify the Unity source or vendor binaries.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
from unity_to_web import locate_project, copy_project

UNITYGLTF_VERSION = '2.25.0'
UNITYGLTF_PACKAGE = 'org.khronos.unitygltf'
UNITYGLTF_URL = 'https://github.com/KhronosGroup/UnityGLTF.git#release/' + UNITYGLTF_VERSION

EDITOR_CS = r'''using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityGLTF;

public static class MetaUnityGltfExport
{
    private static string Arg(string key)
    {
        var args = Environment.GetCommandLineArgs();
        int i = Array.IndexOf(args, key);
        if (i < 0 || i + 1 >= args.Length) throw new Exception("Missing " + key);
        return args[i+1];
    }

    // Executed in a temporary COPY of a Unity source project only.
    public static void Export()
    {
        string destination = Arg("-skillGltfOutput");
        bool all = Arg("-skillAllScenes") == "1";
        Directory.CreateDirectory(destination);
        string[] scenePaths;
        if (all)
            scenePaths = AssetDatabase.FindAssets("t:Scene")
                .Select(AssetDatabase.GUIDToAssetPath)
                .Where(p => p.StartsWith("Assets/", StringComparison.Ordinal))
                .OrderBy(p => p).ToArray();
        else
            scenePaths = EditorBuildSettings.scenes.Where(s => s.enabled)
                .Select(s => s.path).Where(p => !string.IsNullOrWhiteSpace(p)).ToArray();
        if (scenePaths.Length == 0)
            throw new Exception("No Unity scenes selected (enable Build Settings scenes, or pass --all-scenes)");
        for (int i = 0; i < scenePaths.Length; i++)
        {
            var path = scenePaths[i];
            var scene = EditorSceneManager.OpenScene(path, OpenSceneMode.Single);
            var roots = scene.GetRootGameObjects().Select(x => x.transform).ToArray();
            if (roots.Length == 0)
            {
                Debug.LogWarning("META_GLTF_EMPTY_SCENE " + path);
                continue;
            }
            var options = new ExportContext(GLTFSettings.GetOrCreateSettings())
            {
                TexturePathRetriever = GLTFExportMenu.RetrieveTexturePath
            };
            var exporter = new GLTFSceneExporter(roots, options);
            string baseName = Path.GetFileNameWithoutExtension(path);
            string safeName = new string(baseName.Select(c => char.IsLetterOrDigit(c) || c == '_' || c == '-' ? c : '_').ToArray());
            safeName = i.ToString("D3") + "_" + safeName;
            exporter.SaveGLB(destination, safeName);
            Debug.Log("META_GLTF_EXPORT_OK " + path + " => " + safeName + ".glb");
        }
    }
}
'''


def install_package_on_copy(work: Path):
    path = work/'Packages'/'manifest.json'
    if not path.is_file():
        raise RuntimeError('Original Unity project has no Packages/manifest.json; install UnityGLTF manually before export')
    raw = json.loads(path.read_text(encoding='utf-8-sig'))
    deps = raw.setdefault('dependencies', {})
    if not isinstance(deps, dict): raise ValueError('Invalid Unity Packages dependencies')
    deps[UNITYGLTF_PACKAGE] = UNITYGLTF_URL
    path.write_text(json.dumps(raw, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def parse_glb(path: Path):
    with path.open('rb') as f:
        hdr = f.read(20)
        if len(hdr) != 20:raise RuntimeError('Truncated GLB: '+str(path))
        magic, version, length, chunk_len, chunk_kind=struct.unpack('<4sIIII',hdr)
        if magic!=b'glTF' or version!=2 or chunk_kind!=0x4E4F534A or length!=path.stat().st_size:
            raise RuntimeError('Invalid glTF2 GLB header: '+str(path))
        if chunk_len>16_000_000: raise RuntimeError('Unexpectedly large GLB JSON: '+str(path))
        data=json.loads(f.read(chunk_len).rstrip(b' \x00\t\n').decode('utf-8'))
    keys=['nodes','meshes','materials','textures','animations','cameras','skins','scenes']
    used=data.get('extensionsUsed',[])
    unsupported=[x for x in used if x in ('KHR_animation_pointer','KHR_interactivity','KHR_audio')]
    return {'file':path.name, 'bytes':path.stat().st_size,
            'counts':{k:len(data.get(k,[])) for k in keys},
            'extensionsUsed':used,'browser_support_needs_verification':unsupported}


def export(source:Path, out:Path, editor:str|None=None, all_scenes=False, timeout=3600):
    source=locate_project(source.expanduser().resolve(strict=True))
    out=out.expanduser().resolve()
    if out==source or out in source.parents or source in out.parents:
        raise ValueError('Output must be separate from input project')
    unity=editor or os.environ.get('UNITY_EDITOR') or shutil.which('Unity') or shutil.which('unity-editor')
    if not unity: raise RuntimeError('Original Unity Editor required; specify --unity or UNITY_EDITOR')
    dest=out/'glb_scenes'
    if dest.exists() and any(dest.iterdir()): raise ValueError('GLB output directory is not empty')
    out.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='meta-unitygltf-') as tmp:
        work=Path(tmp)/'project'
        copy_project(source, work)
        install_package_on_copy(work)
        cs=work/'Assets'/'Editor'/'MetaUnityGltfExport.cs'
        if cs.exists(): raise RuntimeError('Unity project already defines MetaUnityGltfExport.cs')
        cs.parent.mkdir(parents=True,exist_ok=True)
        cs.write_text(EDITOR_CS,encoding='utf-8')
        log=out/'unitygltf_editor.log'
        cmd=[str(unity),'-batchmode','-nographics','-quit','-projectPath',str(work),
             '-executeMethod','MetaUnityGltfExport.Export',
             '-skillGltfOutput',str(dest),'-skillAllScenes',str(int(all_scenes)),
             '-logFile',str(log)]
        try:
            result=subprocess.run(cmd, timeout=timeout, check=False)
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(f'UnityGLTF export timed out; inspect {log}') from e
        if result.returncode:
            raise RuntimeError(f'UnityGLTF Editor command failed (exit {result.returncode}); inspect {log}')
    glbs=sorted(dest.glob('*.glb')) if dest.exists() else []
    if not glbs: raise RuntimeError('UnityGLTF returned without exporting any scene GLB; check Editor log')
    manifest={'tool':'Khronos UnityGLTF', 'package':UNITYGLTF_URL, 'engine':'Unity',
              'source_project':source.name,
              'fidelity':'visual scene assets; scripts, physics and game logic remain in Unity WebGL',
              'scenes':[parse_glb(f) for f in glbs]}
    (dest/'gltf_manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('Original Unity scene GLBs:',dest)
    return dest


def main():
    ap=argparse.ArgumentParser(description='Unity project -> GLB scenes (visual assets, not gameplay)')
    ap.add_argument('source',type=Path)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--unity',help='installed Unity Editor binary')
    ap.add_argument('--all-scenes',action='store_true',help='export all Assets/*.unity scenes, not just Build Settings')
    ap.add_argument('--timeout',type=int,default=3600)
    args=ap.parse_args()
    export(args.source,args.out,args.unity,args.all_scenes,args.timeout)

if __name__ == '__main__':
    try:main()
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError,json.JSONDecodeError) as e:
        sys.exit('ERROR: '+str(e))
