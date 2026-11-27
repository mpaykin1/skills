#!/usr/bin/env bash
set -euo pipefail
dir="$(cd "$(dirname "$0")" && pwd)"
work="$(mktemp -d)"; trap 'rm -rf "$work"' EXIT
shopt -s nullglob
icds=(/usr/share/vulkan/icd.d/lvp_icd.x86_64.json /usr/share/vulkan/icd.d/lvp_icd.json)
icd=""
for f in "${icds[@]}"; do if [[ -f "$f" ]]; then icd="$f"; break; fi; done
[[ -n "$icd" ]] || { echo "Lavapipe ICD missing" >&2; exit 2; }
export VK_DRIVER_FILES="$icd" VK_ICD_FILENAMES="$icd"
unset VK_ADD_DRIVER_FILES VK_LOADER_DRIVERS_SELECT VK_LOADER_DRIVERS_DISABLE
compiler="$(command -v glslangValidator || command -v glslang)"
"$compiler" -V --target-env vulkan1.1 "$dir/triangle.vert" -o "$work/vert.spv"
"$compiler" -V --target-env vulkan1.1 "$dir/triangle.frag" -o "$work/frag.spv"
spirv-val --target-env vulkan1.1 "$work/vert.spv"
spirv-val --target-env vulkan1.1 "$work/frag.spv"
cc -std=c11 -O2 -Wall -Wextra "$dir/vulkan_probe.c" -lvulkan -o "$work/probe"
"$work/probe" "$work/vert.spv" "$work/frag.spv"
