#!/usr/bin/env python3
"""Verified non-deforming OpenToonz<->Pixelorama full-cel interchange.

Source of truth remains the existing OpenToonz/Pixelorama render bridges and
24fps full-pose compositor. This bridge only copies original RGBA pixels into
numbered OpenToonz image levels and Pixelorama import-ready sprite grids.
No skeleton warps, optical flow, new poses, silent static substitutes or casts.
"""
from __future__ import annotations
import hashlib
import json
import math
import re
import shutil
from pathlib import Path
from PIL import Image
from pixelorama_bridge import compile_scene as compile_pixelorama


class HandoffError(ValueError):
    pass


def _safe(value):
    name = re.sub(r'[^A-Za-z0-9_-]', '_', str(value))[:80]
    if not name or name in ('.', '..'):
        raise HandoffError('Invalid character/action identifier')
    return name


def _inside(root, rel):
    if not isinstance(rel, str) or not rel or Path(rel).is_absolute():
        raise HandoffError('Asset must be scene-relative: ' + repr(rel))
    path = (root / rel).resolve()
    if root != path and root not in path.parents:
        raise HandoffError('Source path escapes scene root')
    if not path.is_file():
        raise HandoffError('Missing genuine pose frame: ' + str(path))
    return path


def _validate_pose_file(path, box):
    with Image.open(path) as im:
        if im.format != 'PNG' or im.mode != 'RGBA':
            raise HandoffError(f'{path.name}: true transparent RGBA PNG required')
        size = tuple(map(int, box[2:]))
        if im.size != size:
            raise HandoffError(f'{path.name}: expected {size}, got {im.size}')
        rgba = im.copy()
    alpha = rgba.getchannel('A')
    lo, hi = alpha.getextrema()
    if hi == 0 or lo == 255:
        raise HandoffError(f'{path.name}: missing transparent complete character pose')
    return rgba


def _save_sheet(pngs, box, dest, cols=8):
    w, h = map(int, box[2:]); cols = min(cols, len(pngs))
    rows = math.ceil(len(pngs) / cols)
    if cols*w*rows*h > 100_000_000:
        raise HandoffError('Sprite sheet exceeds 100M pixels; divide source clip')
    sheet = Image.new('RGBA', (cols * w, rows * h), (0, 0, 0, 0))
    for i, path in enumerate(pngs):
        sheet.alpha_composite(_validate_pose_file(path, box), ((i % cols) * w, (i // cols) * h))
    dest.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(dest)
    return cols, rows


def _verify_exported_pxo_sheet(scene_root, clip, pngs, box):
    """Reject mangled/collapsed sheets and verify every extracted cel pixel-for-pixel."""
    original = clip['pixelorama_source']
    project = _inside(scene_root, original.get('project'))
    if project.suffix.lower() != '.pxo':
        raise HandoffError('Pixelorama provenance must reference real .pxo source')
    actual_hash = hashlib.sha256(project.read_bytes()).hexdigest()
    if actual_hash != original.get('source_sha256'):
        raise HandoffError('Pixelorama .pxo changed since export; regenerate poses')
    if len(pngs) != int(original.get('frame_count', -1)):
        raise HandoffError('Pixelorama clip frame count differs from actual CLI export')
    sheet_file = pngs[0].parent / 'pixelorama_sheet.png'
    if not sheet_file.is_file():
        raise HandoffError('Missing real Pixelorama CLI-exported spritesheet')
    w, h = map(int, box[2:]); count = len(pngs)
    with Image.open(sheet_file) as file:
        if file.format != 'PNG' or file.mode not in ('RGBA', 'P'):
            raise HandoffError('Pixelorama source spritesheet needs PNG with alpha')
        full = file.convert('RGBA')
    W, H = full.size
    if W % w or H % h:
        raise HandoffError(f'Invalid Pixelorama sheet cell geometry: {W}x{H} not divisible by {w}x{h}')
    cols, rows = W // w, H // h
    capacity = cols * rows
    if capacity < count or capacity - count >= cols:
        raise HandoffError(f'Invalid Pixelorama sheet: {capacity} slots for {count} frames')
    for i in range(count, capacity):
        extra = full.crop(((i % cols)*w, (i//cols)*h, (i%cols+1)*w, (i//cols+1)*h))
        if extra.getchannel('A').getbbox():
            raise HandoffError(f'Extra nonempty drawing in Pixelorama padding cell {i}')
    for i, frame in enumerate(pngs):
        extracted = full.crop(((i % cols)*w, (i//cols)*h, (i%cols+1)*w, (i//cols+1)*h))
        if extracted.tobytes() != _validate_pose_file(frame, box).tobytes():
            raise HandoffError(f'Pixelorama spritesheet mismatch on cel {i}; source export cannot be trusted')
    return sheet_file, actual_hash


def compile_and_handoff(scene_path, out_dir, pixelorama_binary=None):
    """Returns (compiled_scene, files_to_pack, bridge_metadata).

    The OpenToonz bridge MUST already run before this function. The original
    Pixelorama compiler runs headless here only when .pxo projects are present.
    """
    out_dir = Path(out_dir).resolve()
    scene_file = Path(compile_pixelorama(Path(scene_path).resolve(), out_dir, pixelorama_binary)).resolve()
    root = scene_file.parent
    scene = json.loads(scene_file.read_text('utf8'))
    exchange = out_dir / 'interchange_2d'
    files = []
    entries = []
    for actor in scene.get('actors', []):
        aid = _safe(actor['id'])
        box = actor['box']
        for ix, clip in enumerate(actor.get('clips', [])):
            origin = 'pixelorama' if clip.get('pixelorama_source') else 'opentoonz' if clip.get('opentoonz_source') else None
            if origin is None:
                continue
            frames = clip.get('frames', [])
            if len(frames) < 12:
                raise HandoffError(f'{aid}: animation source needs >=12 real cels per action')
            folder = f'{ix:02d}_{_safe(clip.get("action", "action"))}'
            paths = [_inside(root, f.get('png')) for f in frames]
            for path in paths:
                _validate_pose_file(path, box)
            supports = clip.get('support_sequence')
            if supports is not None:
                if len(supports) != len(frames) or any(x not in ('left','right','double','flight') for x in supports):
                    raise HandoffError(f'{aid}/{folder}: support_sequence must have one valid grounded-foot marker per cel')
                for i, frame in enumerate(frames):
                    if 'support' in frame and frame['support'] != supports[i]:
                        raise HandoffError('Contact annotation conflicts with source support_sequence')
                    frame['support'] = supports[i]
            record = {'actor_id':actor['id'], 'action':clip.get('action'), 'index':ix,
                      'origin':origin,'fps':24,'cell_size':list(map(int,box[2:])),
                      'frame_count':len(paths),'pose_sha256':[hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]}
            if origin == 'pixelorama':
                sheet, pxo_hash = _verify_exported_pxo_sheet(root, clip, paths, box)
                record['source_sha256'] = pxo_hash
                record['source_sheet_sha256'] = hashlib.sha256(sheet.read_bytes()).hexdigest()
                # OpenToonz recognizes numbered image sequences as distinct cels.
                level_root = exchange/'opentoonz_levels'/aid/folder
                level_root.mkdir(parents=True, exist_ok=True)
                for i, src in enumerate(paths, start=1):
                    target = level_root / f'{aid}.{i:04d}.png'
                    shutil.copy2(src,target)
                    files.append(target)
                record['opentoonz_level'] = f'opentoonz_levels/{aid}/{folder}/{aid}.0001.png'
                # Preserve the exact exported sheet for future Pixelorama editing.
                raw_sheet = exchange/'pixelorama_original_sheets'/aid/f'{folder}.png'
                raw_sheet.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(sheet,raw_sheet)
                files.append(raw_sheet)
            else:
                # OpenToonz frame order becomes a Pixelorama importable grid.
                dest = exchange/'pixelorama_import'/aid/f'{folder}.png'
                cols, rows = _save_sheet(paths,box,dest)
                files.append(dest)
                record['pixelorama_import'] = f'pixelorama_import/{aid}/{folder}.png'
                record['grid'] = {'columns':cols,'rows':rows,'direction':'forward-row-major'}
            entries.append(record)
    if not entries:
        return scene_file, [], {'interchange_clips':0}
    manifest = exchange/'interchange.json'
    manifest.write_text(json.dumps({'schema':1,'source':'actual OpenToonz/Pixelorama authored cels',
                                    'no_character_deformation':True,'entries':entries},ensure_ascii=False,indent=2),'utf8')
    files.append(manifest)
    # The handoff only inserts manually provided support annotations; no poses changed.
    scene_file.write_text(json.dumps(scene,ensure_ascii=False,indent=2),'utf8')
    return scene_file, files, {'interchange_clips':len(entries), 'pixelorama_clips':sum(x['origin']=='pixelorama' for x in entries),
                               'opentoonz_clips':sum(x['origin']=='opentoonz' for x in entries)}
