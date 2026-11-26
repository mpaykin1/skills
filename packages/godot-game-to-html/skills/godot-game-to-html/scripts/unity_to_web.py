#!/usr/bin/env python3
"""Official Unity Editor WebGL build from an authorized ORIGINAL Unity source project.

Copies (Assets, Packages, ProjectSettings) into temporary project; never edits user source.
AssetRipper recoveries with missing MonoBehaviours are NOT auto-promoted as originals.
Requires installed Unity Editor with WebGL Build Support (proprietary, not bundled).
"""
from __future__ import annotations
import argparse
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile

EDITOR_CS = r'''using System;
using System.Linq;
using UnityEditor;
using UnityEditor.Build.Reporting;
public static class SkillUnityWebExport {
    public static void Build() {
        string[] args = Environment.GetCommandLineArgs();
        int idx = Array.IndexOf(args, "-skillOutput");
        if (idx < 0 || idx + 1 >= args.Length) throw new Exception("Missing -skillOutput path");
        string destination = args[idx + 1];
        var enabledScenes = EditorBuildSettings.scenes.Where(s => s.enabled).Select(s => s.path).ToArray();
        if (enabledScenes.Length == 0) throw new Exception("No enabled scenes in Build Settings. Cannot build a playable game.");
        PlayerSettings.WebGL.compressionFormat = WebGLCompressionFormat.Disabled;
        var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions {
            scenes = enabledScenes,
            locationPathName = destination,
            target = BuildTarget.WebGL,
            options = BuildOptions.None
        });
        if (report.summary.result != BuildResult.Succeeded)
            throw new Exception("Unity WebGL BuildPipeline failed: " + report.summary.result);
        UnityEngine.Debug.Log("SKILL_UNITY_WEBGL_BUILD_OK " + destination);
    }
}
'''
ALLOWED={'Assets','Packages','ProjectSettings','UserSettings'}


def locate_project(src:Path):
    if (src/'Assets').is_dir() and (src/'ProjectSettings'/'ProjectVersion.txt').exists():return src
    matches=[p for p in src.iterdir() if p.is_dir() and (p/'Assets').is_dir() and (p/'ProjectSettings'/'ProjectVersion.txt').exists()]
    if len(matches)==1:return matches[0]
    raise ValueError('Need original Unity source folder with Assets/ and ProjectSettings/ProjectVersion.txt')


def copy_project(source:Path,dst:Path):
    dst.mkdir(parents=True,exist_ok=False)
    for name in ALLOWED:
        root=source/name
        if not root.exists():continue
        if root.is_symlink():raise ValueError('Refuse symlinked Unity project component: '+str(root))
        def ignore(folder,names):
            return {n for n in names if (Path(folder)/n).is_symlink()}
        shutil.copytree(root,dst/name,ignore=ignore,symlinks=False)


def build(source:Path,out:Path,editor=None,timeout=3600):
    source=locate_project(source.expanduser().resolve(strict=True))
    out=out.expanduser().resolve()
    if out==source or source in out.parents or out in source.parents: raise ValueError('Output must be separate from input')
    unity=editor or os.environ.get('UNITY_EDITOR') or shutil.which('Unity') or shutil.which('unity-editor')
    if not unity:raise RuntimeError('Unity Editor + WebGL Build Support required. Use --unity /path/to/Unity binary')
    unity=str(unity)
    out.mkdir(parents=True,exist_ok=True)
    web=out/'web'
    if web.exists() and any(web.iterdir()):raise ValueError('WebGL destination is not empty')
    with tempfile.TemporaryDirectory(prefix='unity-to-html-') as temp:
        work=Path(temp)/'source'
        copy_project(source,work)
        script=work/'Assets'/'Editor'/'SkillUnityWebExport.cs'
        if script.exists():raise ValueError('Project already contains Assets/Editor/SkillUnityWebExport.cs')
        script.parent.mkdir(parents=True,exist_ok=True)
        script.write_text(EDITOR_CS,encoding='utf-8')
        logfile=out/'unity_export.log'
        command=[unity,'-batchmode','-nographics','-quit','-projectPath',str(work),
                 '-buildTarget','WebGL','-executeMethod','SkillUnityWebExport.Build',
                 '-skillOutput',str(web),'-logFile',str(logfile)]
        try:
            p=subprocess.run(command,timeout=timeout,check=False)
        except subprocess.TimeoutExpired:raise RuntimeError(f'Unity build timed out; see {logfile}')
        if p.returncode!=0:raise RuntimeError(f'Unity Editor exited {p.returncode}; see {logfile}')
        if not (web/'index.html').is_file() or not list((web/'Build').glob('*.wasm')):
            # On some builds codeUrl is .wasm.unityweb if compression was not disabled.
            raise RuntimeError('Unity WebGL artifacts missing: expected index.html and Build/*.wasm; see '+str(logfile))
    print('Native Unity WebGL game built:',web)
    return web


def main():
    ap=argparse.ArgumentParser(description='Unity source -> official Unity Editor WebGL export')
    ap.add_argument('source',type=Path);ap.add_argument('--out',required=True,type=Path)
    ap.add_argument('--unity');ap.add_argument('--timeout',type=int,default=3600)
    a=ap.parse_args();build(a.source,a.out,a.unity,a.timeout)

if __name__=='__main__':
    try:main()
    except (OSError,RuntimeError,ValueError,subprocess.SubprocessError) as e:sys.exit('ERROR: '+str(e))
