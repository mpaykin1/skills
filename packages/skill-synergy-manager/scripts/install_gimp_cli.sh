#!/usr/bin/env bash
set -euo pipefail
work="${1:?absolute disposable runtime directory required}"
[[ "$work" == /* && "$(uname -s)" == Linux ]]
mkdir -p "$work"
cd "$work"
# Ubuntu package signatures verified by apt. Native version follows Ubuntu 24.04.
sudo apt-get update -o Acquire::Retries=3
sudo apt-get install -y --no-install-recommends gimp xvfb xauth
gimp --version
python3 -m venv "$work/venv"
git init upstream
git -C upstream remote add origin https://github.com/HKUDS/CLI-Anything.git
git -C upstream fetch --depth=1 origin 34f519533bc175d2fe287ab8316b0dd99bb9cc43
git -C upstream checkout --detach FETCH_HEAD
test "$(git -C upstream rev-parse HEAD)" = 34f519533bc175d2fe287ab8316b0dd99bb9cc43
"$work/venv/bin/python" -m pip install 'setuptools==75.8.2' 'wheel==0.45.1' 'click==8.1.8' 'prompt-toolkit==3.0.50' 'wcwidth==0.2.13' 'Pillow==11.3.0' 'numpy==2.2.6'
"$work/venv/bin/python" -m pip install --no-deps --no-build-isolation "$work/upstream/gimp/agent-harness"
"$work/venv/bin/cli-anything-gimp" --help
if [[ -n "${GITHUB_PATH:-}" ]]; then printf '%s\n' "$work/venv/bin" >> "$GITHUB_PATH"; fi
