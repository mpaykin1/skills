#!/usr/bin/env bash
set -euo pipefail
work="${1:?absolute disposable runtime directory required}"
[[ "$work" == /* && "$(uname -s)" == Linux ]]
mkdir -p "$work"
cd "$work"
sudo apt-get update -o Acquire::Retries=3
sudo apt-get install -y --no-install-recommends renderdoccmd python3-renderdoc python3-venv
/usr/bin/python3 -m venv --system-site-packages "$work/venv"
git init upstream
git -C upstream remote add origin https://github.com/HKUDS/CLI-Anything.git
git -C upstream fetch --depth=1 origin 34f519533bc175d2fe287ab8316b0dd99bb9cc43
git -C upstream checkout --detach FETCH_HEAD
test "$(git -C upstream rev-parse HEAD)" = 34f519533bc175d2fe287ab8316b0dd99bb9cc43
"$work/venv/bin/python" -m pip install 'setuptools==75.8.2' 'wheel==0.45.1' 'click==8.1.8' 'prompt-toolkit==3.0.50' 'wcwidth==0.2.13'
"$work/venv/bin/python" -m pip install --no-deps --no-build-isolation "$work/upstream/renderdoc/agent-harness"
"$work/venv/bin/python" -c 'import renderdoc; print(renderdoc.GetVersionString())'
"$work/venv/bin/cli-anything-renderdoc" --help
renderdoccmd version
if [[ -n "${GITHUB_PATH:-}" ]]; then printf '%s\n' "$work/venv/bin" >> "$GITHUB_PATH"; fi
