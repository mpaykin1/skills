"""Stage the exact optional GPL UI addon in an isolated Blender user-scripts directory."""
import argparse,hashlib,pathlib,urllib.request
REV='7e9ac93dcc0ecf185c1d9883f71ef36e5235efa9'
FILES={'animation_layers.py':'2dc4aba8f860b5b3b90ba8462489c98cc07e00f7','LICENSE':'f288702d2fa16d3cdf0035b15a9fcbc552cd88e7'}
def git_blob(b):return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--profile',type=pathlib.Path,required=True);p.add_argument('--source-dir',type=pathlib.Path);a=p.parse_args()
 profile=a.profile.resolve(); data={}
 for name,sha in FILES.items():
  if a.source_dir:b=(a.source_dir/name).read_bytes()
  else:
   with urllib.request.urlopen(f'https://raw.githubusercontent.com/evilmushroom/Animation-Layers-for-Blender/{REV}/{name}',timeout=20) as f:b=f.read(1024*1024+1)
  if len(b)>1024*1024 or git_blob(b)!=sha:raise ValueError(f'{name}: source hash mismatch')
  data[name]=b
 profile.mkdir(parents=True,exist_ok=False);target=profile/'scripts'/'addons';target.mkdir(parents=True)
 (target/'animation_layers.py').write_bytes(data['animation_layers.py']);(profile/'LICENSE.animation-layers').write_bytes(data['LICENSE'])
 print('Addon source staged, NOT enabled or runtime-verified. BLENDER_USER_SCRIPTS='+str(profile/'scripts'))
if __name__=='__main__':main()
