#!/usr/bin/env bash
set -euo pipefail
work="${1:?absolute disposable runtime directory required}"
[[ "$work" == /* && "$(uname -s)" == Linux && "$(uname -m)" == x86_64 ]]
mkdir -p "$work/bin"
cd "$work"
tag=4.5.1-stable
zip="Godot_v${tag}_linux.x86_64.zip"
templates="Godot_v${tag}_export_templates.tpz"
url="https://github.com/godotengine/godot/releases/download/$tag"
curl --fail --location --retry 2 -o "$zip" "$url/$zip"
printf '%s  %s\n' 02ec53d1cc7dbb9cc6355393c61b9ab43d1244751a124f10248a4802830788cd "$zip" | sha256sum -c -
unzip -q "$zip" -d engine
install -m 755 "engine/Godot_v${tag}_linux.x86_64" "$work/bin/godot"
if [[ "${2:-}" == --web ]]; then
  curl --fail --location --retry 2 -o "$templates" "$url/$templates"
  printf '%s  %s\n' 1998af37f1387684e2c211cdb483daf492fc64dc6b12096bddcdca25b6910c86 "$templates" | sha256sum -c -
  mkdir -p "$HOME/.local/share/godot/export_templates/4.5.1.stable"
  unzip -q "$templates" 'templates/web_*' -d "$work/templates"
  cp "$work/templates/templates"/web_* "$HOME/.local/share/godot/export_templates/4.5.1.stable/"
fi
python3 -m venv "$work/venv"
git init upstream
git -C upstream remote add origin https://github.com/HKUDS/CLI-Anything.git
git -C upstream fetch --depth=1 origin 34f519533bc175d2fe287ab8316b0dd99bb9cc43
git -C upstream checkout --detach FETCH_HEAD
test "$(git -C upstream rev-parse HEAD)" = 34f519533bc175d2fe287ab8316b0dd99bb9cc43
"$work/venv/bin/python" -m pip install 'setuptools==75.8.2' 'wheel==0.45.1' 'click==8.1.8' 'prompt-toolkit==3.0.50' 'wcwidth==0.2.13'
"$work/venv/bin/python" -m pip install --no-deps --no-build-isolation "$work/upstream/godot/agent-harness"
export PATH="$work/bin:$work/venv/bin:$PATH"
godot --headless --version
cli-anything-godot --json engine status
if [[ -n "${GITHUB_PATH:-}" ]]; then printf '%s\n' "$work/bin" "$work/venv/bin" >> "$GITHUB_PATH"; fi
