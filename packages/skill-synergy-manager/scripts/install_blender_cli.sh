#!/usr/bin/env bash
set -euo pipefail
# Dedicated disposable Linux x86_64 worker; no credentials or protected checkout.
[[ "$(uname -s)" == Linux && "$(uname -m)" == x86_64 ]]
work="${1:?absolute disposable runtime directory required}"
[[ "$work" == /* ]]
mkdir -p "$work"
cd "$work"
version=4.2.0
archive="blender-${version}-linux-x64.tar.xz"
url="https://download.blender.org/release/Blender4.2"
mirror="https://mirror.blender.org/release/Blender4.2"
fetch_release() {
  local name="$1" out="$2"
  curl --fail --location --retry 2 --connect-timeout 20 -o "$out" "$url/$name" ||
  curl --fail --location --retry 2 --connect-timeout 20 -o "$out" "$mirror/$name"
}
fetch_release "$archive" "$archive"
fetch_release "blender-${version}.sha256" blender.sha256
awk -v f="$archive" '$2==f || $2=="*"f {print $1 "  " f}' blender.sha256 > selected.sha256
test -s selected.sha256
sha256sum -c selected.sha256
tar -xJf "$archive"
python3 -m venv "$work/venv"
# Fixed source commit; fixed dependency versions; package hashes not yet locked.
git init upstream
git -C upstream remote add origin https://github.com/HKUDS/CLI-Anything.git
git -C upstream fetch --depth=1 origin 34f519533bc175d2fe287ab8316b0dd99bb9cc43
git -C upstream checkout --detach FETCH_HEAD
test "$(git -C upstream rev-parse HEAD)" = 34f519533bc175d2fe287ab8316b0dd99bb9cc43
"$work/venv/bin/python" -m pip install 'setuptools==75.8.2' 'wheel==0.45.1' 'click==8.1.8' 'prompt-toolkit==3.0.50' 'wcwidth==0.2.13'
"$work/venv/bin/python" -m pip install --no-deps --no-build-isolation "$work/upstream/blender/agent-harness"
export PATH="$work/venv/bin:$work/blender-${version}-linux-x64:$PATH"
blender --version
cli-anything-blender --help
if [[ -n "${GITHUB_PATH:-}" ]]; then printf '%s\n' "$work/venv/bin" "$work/blender-${version}-linux-x64" >> "$GITHUB_PATH"; fi
