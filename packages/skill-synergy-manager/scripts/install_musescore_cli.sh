#!/usr/bin/env bash
set -euo pipefail
work="${1:?absolute disposable runtime directory required}"
[[ "$work" == /* && "$(uname -s)" == Linux && "$(uname -m)" == x86_64 ]]
mkdir -p "$work/bin"
cd "$work"
sudo apt-get update -o Acquire::Retries=3
sudo apt-get install -y --no-install-recommends xvfb xauth libgl1 libegl1 libasound2t64 libxcb-cursor0 libnss3 libxkbcommon-x11-0
archive=MuseScore-Studio-4.6.5.253511702-x86_64.AppImage
curl --fail --location --retry 2 -o "$archive" "https://github.com/musescore/MuseScore/releases/download/v4.6.5/$archive"
printf '%s  %s\n' 193daa0ea18bcfa90a47145a842275b8069b7b2b8d153e562b15fab5fe50fcaf "$archive" | sha256sum -c -
chmod +x "$archive"
"./$archive" --appimage-extract >/dev/null
cat > "$work/bin/mscore" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
export QT_QPA_PLATFORM=offscreen
export QT_QUICK_BACKEND=software
exec "$root/squashfs-root/AppRun" "$@"
SH
chmod +x "$work/bin/mscore"
python3 -m venv "$work/venv"
git init upstream
git -C upstream remote add origin https://github.com/HKUDS/CLI-Anything.git
git -C upstream fetch --depth=1 origin 34f519533bc175d2fe287ab8316b0dd99bb9cc43
git -C upstream checkout --detach FETCH_HEAD
test "$(git -C upstream rev-parse HEAD)" = 34f519533bc175d2fe287ab8316b0dd99bb9cc43
"$work/venv/bin/python" -m pip install 'setuptools==75.8.2' 'wheel==0.45.1' 'click==8.1.8' 'prompt-toolkit==3.0.50' 'wcwidth==0.2.13' 'defusedxml==0.7.1' 'mido==1.3.3' 'packaging==24.2'
"$work/venv/bin/python" -m pip install --no-deps --no-build-isolation "$work/upstream/musescore/agent-harness"
export PATH="$work/bin:$work/venv/bin:$PATH"
mscore --version
cli-anything-musescore --help
if [[ -n "${GITHUB_PATH:-}" ]]; then printf '%s\n' "$work/bin" "$work/venv/bin" >> "$GITHUB_PATH"; fi
