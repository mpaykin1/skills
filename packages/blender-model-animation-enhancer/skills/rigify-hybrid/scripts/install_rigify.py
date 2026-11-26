"""Install a reviewed local Rigify extension in an isolated Blender profile."""
import argparse, hashlib, os, pathlib, subprocess, sys, tomllib, zipfile
p=argparse.ArgumentParser(); p.add_argument('--blender',default='blender'); p.add_argument('--zip',required=True,type=pathlib.Path); p.add_argument('--sha256',required=True); p.add_argument('--version',required=True); p.add_argument('--profile',required=True,type=pathlib.Path); a=p.parse_args()
if hashlib.sha256(a.zip.read_bytes()).hexdigest()!=a.sha256.lower(): sys.exit('archive hash mismatch')
with zipfile.ZipFile(a.zip) as z:
    m=tomllib.loads(z.read('blender_manifest.toml').decode())
    if m.get('id')!='rigify' or m.get('version')!=a.version: sys.exit('not expected Rigify version')
    if not any('GPL' in x for x in m.get('license',[])): sys.exit('license mismatch')
a.profile.mkdir(parents=True,exist_ok=False)
env=dict(os.environ,BLENDER_USER_RESOURCES=str(a.profile.resolve()))
def run(*args): subprocess.run([a.blender,*args],env=env,check=True,timeout=180)
run('--command','extension','validate',str(a.zip.resolve()))
run('--command','extension','repo-add','meta_rigify','--name','META Rigify','--directory',str((a.profile/'extensions'/'meta_rigify').resolve()))
run('--command','extension','install-file','-r','meta_rigify','-e',str(a.zip.resolve()))
run('--background','--python-exit-code','1','--python-expr',"import bpy; assert any(k.endswith('.rigify') or k=='rigify' for k in bpy.context.preferences.addons.keys()); print('Rigify enabled')")
