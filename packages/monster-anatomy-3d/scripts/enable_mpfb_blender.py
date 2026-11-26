"""Install locally built MPFB2 extension in Blender 4.2+ (user profile only)."""
import argparse
import sys
from pathlib import Path
import bpy

parser = argparse.ArgumentParser()
parser.add_argument('--package', required=True)
args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
source = Path(args.package).resolve()
if not source.is_file() or source.suffix.lower() != '.zip':
    raise FileNotFoundError(f'MPFB extension ZIP not found: {source}')
repos = list(bpy.context.preferences.extensions.repos)
repo_modules = [repo.module for repo in repos if repo.enabled and not repo.use_remote_url]
repo = 'user_default' if 'user_default' in repo_modules else (repo_modules[0] if repo_modules else None)
if repo is None:
    raise RuntimeError('No enabled local Blender extension repository. Configure Preferences > Get Extensions > Repositories')
result = bpy.ops.extensions.package_install_files(filepath=str(source), repo=repo, enable_on_install=True)
if 'FINISHED' not in result:
    raise RuntimeError('MPFB extension install did not finish: ' + str(result))
if not any(k.endswith('.mpfb') or k == 'mpfb' for k in bpy.context.preferences.addons.keys()):
    raise RuntimeError('MPFB was installed but not enabled, check Blender extension preferences')
bpy.ops.wm.save_userpref()
print('MPFB2 installed and enabled through official Blender extension operator.')
