#!/usr/bin/env bash
set -euo pipefail
dir="$(cd "$(dirname "$0")" && pwd)"
source="${1:?pinned Lavapipe scripts directory required}"
work="$(mktemp -d)"; trap 'rm -rf "$work"' EXIT
icd=""
for f in /usr/share/vulkan/icd.d/lvp_icd.x86_64.json /usr/share/vulkan/icd.d/lvp_icd.json; do if [[ -f "$f" ]]; then icd="$f"; break; fi; done
[[ -n "$icd" ]] || { echo "Lavapipe ICD missing" >&2; exit 2; }
export VK_DRIVER_FILES="$icd" VK_ICD_FILENAMES="$icd"
unset VK_ADD_DRIVER_FILES VK_LOADER_DRIVERS_SELECT VK_LOADER_DRIVERS_DISABLE VK_INSTANCE_LAYERS VK_LAYER_PATH VK_ADD_LAYER_PATH VK_LOADER_LAYERS_ENABLE VK_LOADER_LAYERS_DISABLE
compiler="$(command -v glslangValidator || command -v glslang)"
"$compiler" -V --target-env vulkan1.1 "$source/triangle.vert" -o "$work/vert.spv"
"$compiler" -V --target-env vulkan1.1 "$source/triangle.frag" -o "$work/frag.spv"
spirv-val --target-env vulkan1.1 "$work/vert.spv"
spirv-val --target-env vulkan1.1 "$work/frag.spv"
python3 "$dir/instrument.py" "$source/vulkan_probe.c" "$work/probe.c"
cc -std=c11 -O2 -Wall -Wextra "$work/probe.c" -lvulkan -o "$work/probe"
"$work/probe" "$work/vert.spv" "$work/frag.spv" 2>"$work/positive.log" || { cat "$work/positive.log"; exit 1; }
cat "$work/positive.log"
"$work/probe" "$work/vert.spv" "$work/frag.spv" negative 2>"$work/negative.log" || { cat "$work/negative.log"; exit 1; }
python3 "$dir/route_errors.py" "$work/negative.log" --expect VUID-VkBufferCreateInfo-size-00912
