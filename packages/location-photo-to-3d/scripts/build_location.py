#!/usr/bin/env python3
"""MoGe-2 ViT-S CPU -> exact source-textured GLB -> single-file offline WebGL2 location.

Production requires upstream MoGe. --from-glb reuses real exported geometry, no hallucinated data.
"""
from __future__ import annotations
import argparse, base64, io, json, os, subprocess, sys, tempfile
from pathlib import Path


def b64(data): return base64.b64encode(data).decode('ascii')


def prepared_scene(glb_path: Path, max_triangles: int, depth_map=None, depth_strength=0.35, segmentation_labels=None, seam_pixels=4, opencv_confidence=None):
    import numpy as np
    import trimesh
    from PIL import Image
    scene = trimesh.load(str(glb_path), force='scene', process=False)
    meshes = []
    all_bounds = []
    sky = None
    refinement_applied = False
    segmentation_applied = False
    opencv_applied = False
    for m in scene.dump():
        if not isinstance(m, trimesh.Trimesh) or len(m.faces) == 0:
            continue
        if max_triangles > 0 and len(m.faces) > max_triangles:
            # Use evenly sampled original triangles. Preserve UVs and vertices as-is.
            keep = np.linspace(0, len(m.faces)-1, max_triangles, dtype=np.int64)
            selected = m.faces[keep]
            unique, inverse = np.unique(selected.reshape(-1), return_inverse=True)
            vertices = m.vertices[unique]
            uvs = m.visual.uv[unique] if m.visual.kind == 'texture' and m.visual.uv is not None else None
            faces = inverse.reshape(-1,3)
        else:
            vertices = m.vertices
            uvs = m.visual.uv if m.visual.kind == 'texture' and m.visual.uv is not None else None
            faces = m.faces
        vertices = np.asarray(vertices, dtype=np.float32)
        if depth_map is not None and uvs is not None:
            from depth_fusion import refine_vertices
            confidence = None
            if segmentation_labels is not None:
                from segmentation_fusion import boundary_confidence
                confidence = boundary_confidence(segmentation_labels, uvs, seam_pixels)
                segmentation_applied |= bool(np.any(confidence < 0.999))
            if opencv_confidence is not None:
                # Opencv confidence uses the source photo's top-left image origin.
                # Existing DA sample_bilinear accounts for GLB bottom-left UV origin.
                from depth_fusion import sample_bilinear
                cv_guard = np.clip(sample_bilinear(opencv_confidence, uvs), 0., 1.).astype(np.float32)
                opencv_applied |= bool(np.any(cv_guard < .999))
                # At a structure seam, preserve MoGe irrespective of MobileSAM label.
                confidence = cv_guard if confidence is None else np.minimum(confidence, cv_guard)
            vertices, applied = refine_vertices(vertices, uvs, depth_map, depth_strength,
                                                vertex_confidence=confidence)
            refinement_applied |= applied
        if not np.isfinite(vertices).all():
            raise ValueError('Invalid non-finite vertices in MoGe geometry')
        if uvs is None:
            raise RuntimeError('MoGe geometry has no UV coordinates; original texture cannot be preserved')
        uvs = np.asarray(uvs, dtype=np.float32)
        if len(uvs) != len(vertices):
            raise ValueError('UV count mismatch')
        packed = np.ascontiguousarray(np.concatenate([vertices, uvs], axis=1), dtype='<f4')
        indices = np.ascontiguousarray(faces.reshape(-1), dtype='<u4')
        mat = getattr(m.visual, 'material', None)
        texture = getattr(mat, 'baseColorTexture', None)
        if texture is None:
            raise RuntimeError('GLB missing original image texture; cannot silently replace it')
        if not isinstance(texture, Image.Image):
            texture = Image.fromarray(np.array(texture))
        if texture.mode not in ('RGB', 'RGBA'):
            texture = texture.convert('RGB')
        # JPEG generally keeps outputs small; preserve original photo visually.
        pic = io.BytesIO(); texture.convert('RGB').save(pic, format='JPEG', quality=91, optimize=True)
        px = np.array(texture.convert('RGB').resize((16, 16)))
        sky = np.mean(px[0:3, :, :], axis=(0,1)).astype(float) / 255.0
        meshes.append({'positions_uvs': b64(packed.tobytes()), 'indices': b64(indices.tobytes()),
                       'index_count': int(len(indices)), 'texture': 'data:image/jpeg;base64,'+b64(pic.getvalue())})
        all_bounds.append([np.min(vertices,axis=0), np.max(vertices,axis=0)])
    if not meshes: raise ValueError('No nonempty textured meshes in the GLB')
    mi=np.min([x[0] for x in all_bounds],axis=0)
    ma=np.max([x[1] for x in all_bounds],axis=0)
    # MoGe GLB OpenGL coordinates: camera at [0,0,0], forward -Z.
    far=float(max(3, np.linalg.norm(ma-mi)))
    return {'meshes':meshes,'camera':[0,0,0], 'fov':70,'fog':[float(x) for x in sky],
            'depth_refined': bool(refinement_applied),
            'segmentation_guided': bool(refinement_applied and segmentation_applied),
            'opencv_guided': bool(refinement_applied and opencv_applied),
            'fog_range':[far*.4,far*2.0], 'bounds':[mi.tolist(),ma.tolist()]}


def make_html(glb_path: Path, output: Path, max_triangles: int, depth_map=None, depth_strength=0.35, segmentation_labels=None, seam_pixels=4, opencv_confidence=None):
    scene = prepared_scene(glb_path, max_triangles, depth_map, depth_strength,
                           segmentation_labels, seam_pixels, opencv_confidence)
    fov_path = glb_path.parent / 'fov.json'
    if fov_path.exists():
        try:
            fov_y = float(json.loads(fov_path.read_text(encoding='utf8'))['fov_y'])
            if 15 < fov_y < 145: scene['fov'] = fov_y
        except (KeyError, ValueError, json.JSONDecodeError): pass
    top=scene['fog']
    rgb=[int(max(0,min(255,round(c*255)))) for c in top]
    dark=[int(v*.46) for v in rgb]
    sky='rgb('+','.join(map(str,dark))+')'
    light='rgb('+','.join(map(str,rgb))+')'
    template=(Path(__file__).resolve().parent/'viewer_template.html').read_text(encoding='utf8')
    code=json.dumps(scene,ensure_ascii=True,separators=(',',':')).replace('<','\\u003c')
    html=template.replace('__SCENE_DATA__',code).replace('__SKY_LIGHT__',light).replace('__SKY__',sky)
    mode = 'MoGe-2 + Depth Anything V2' if scene['depth_refined'] else 'MoGe-2'
    if scene['segmentation_guided']:
        mode += ' + MobileSAM'
    if scene['opencv_guided']:
        mode += ' + OpenCV'
    html=html.replace('__DEPTH_MODE__', mode)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(html,encoding='utf8')
    print(f'Autonomous location: {output} ({output.stat().st_size/1024/1024:.2f} MiB)')
    return output


def infer_moge(photo: Path, workspace: Path, opts):
    # MoGe-2 official CLI; model weights downloaded by upstream once and cached.
    cmd=[sys.executable,'-m','moge.scripts.infer','--input',str(photo),
         '--version','v2','--pretrained','Ruicheng/moge-2-vits-normal',
         '--device','cpu','--output',str(workspace),'--resize',str(opts.resize),
         '--resolution_level',str(opts.resolution),'--threshold',str(opts.threshold),'--glb','--maps']
    if opts.fov is not None: cmd.extend(['--fov_x',str(opts.fov)])
    try:
        subprocess.run(cmd,check=True)
    except ModuleNotFoundError as e:
        raise RuntimeError('MoGe is not installed. See README.md for CPU setup.') from e
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f'MoGe CPU inference failed with exit code {e.returncode}; no synthetic fallback') from e
    files=list(workspace.rglob('mesh.glb'))
    if not files: raise RuntimeError('MoGe did not produce mesh.glb; cannot build faithful output')
    return max(files,key=lambda x:x.stat().st_mtime)


def infer_depth_anything(photo: Path, workspace: Path, opts):
    output = workspace / 'depth_anything_v2.npy'
    worker = Path(__file__).resolve().parent / 'depth_anything_cpu.py'
    command = [sys.executable, str(worker), str(photo), '--output', str(output),
               '--input-size', str(opts.depth_input_size)]
    if opts.depth_weights is not None:
        command += ['--weights', str(opts.depth_weights.resolve())]
    if opts.depth_repo is not None:
        command += ['--repo', str(opts.depth_repo.resolve())]
    subprocess.run(command, check=True)
    return output


def infer_mobile_sam(photo: Path, workspace: Path, opts):
    output = workspace / 'mobile_sam_labels.npz'
    worker = Path(__file__).resolve().parent / 'mobile_sam_cpu.py'
    command = [sys.executable, str(worker), str(photo), '--output', str(output),
               '--points-per-side', str(opts.segment_grid)]
    if opts.segment_weights is not None:
        command += ['--weights', str(opts.segment_weights.resolve())]
    if opts.segment_repo is not None:
        command += ['--repo', str(opts.segment_repo.resolve())]
    subprocess.run(command, check=True)
    return output



def infer_opencv(photo: Path, workspace: Path, opts):
    from opencv_structure import run
    output = workspace / 'opencv_structure.npz'
    return run(photo, output, opts.opencv_guard_pixels, opts.opencv_max_side,
               opts.opencv_min_line_fraction, opts.opencv_max_lines)

def load_segments(path):
    import numpy as np
    with np.load(path, allow_pickle=False) as data:
        if set(data.files) != {'labels'}:
            raise RuntimeError('MobileSAM segmentation .npz must contain exactly labels')
        labels = data['labels']
    if labels.ndim != 2 or labels.dtype.kind not in 'ui' or min(labels.shape) < 2:
        raise RuntimeError('Invalid MobileSAM label map; expected unsigned 2D labels')
    if not np.any(labels):
        raise RuntimeError('MobileSAM segmentation map contains no objects')
    return labels


def load_depth(path):
    import numpy as np
    m = np.load(path, allow_pickle=False)
    if m.ndim != 2 or not np.isfinite(m).all():
        raise RuntimeError('Invalid Depth Anything V2 map (expected finite 2D .npy)')
    return np.asarray(m, dtype=np.float32)


def cli():
    p=argparse.ArgumentParser(description='Photo -> MoGe-2 + Depth Anything V2 + MobileSAM + OpenCV CPU -> offline HTML')
    p.add_argument('photo', nargs='?', type=Path, help='Input JPG/PNG photograph')
    p.add_argument('-o','--output',type=Path,default=Path('location.html'))
    p.add_argument('--from-glb',type=Path,help='Use existing genuine MoGe GLB, skip MoGe inference')
    p.add_argument('--depth-mode',choices=['refine','off'],default='refine',help='Default: run DA-V2 Small CPU to refine MoGe; off: MoGe-only')
    p.add_argument('--depth-map',type=Path,help='Previously computed raw DA-V2 .npy, skips DA inference')
    p.add_argument('--depth-strength',type=float,default=0.35,help='Bounded residual blend [0,1]')
    p.add_argument('--segment-mode',choices=['edges','off'],default='edges',
                   help='Default: MobileSAM CPU masks limit DA-V2 displacement near object edges')
    p.add_argument('--segment-map',type=Path,help='Previously computed MobileSAM labels .npz')
    p.add_argument('--segment-repo',type=Path,help='Cloned upstream MobileSAM repo')
    p.add_argument('--segment-weights',type=Path,help='Official mobile_sam.pt')
    p.add_argument('--segment-grid',type=int,default=10,help='CPU prompt grid per side 4..32')
    p.add_argument('--seam-pixels',type=int,default=4,help='Safety width near mask edges 1..40')
    p.add_argument('--opencv-mode',choices=['lines','off'],default='lines',
                   help='Default: CPU OpenCV structural-line guards limit DA-V2 corrections')
    p.add_argument('--opencv-map',type=Path,help='Previously computed OpenCV structure .npz (confidence + lines)')
    p.add_argument('--opencv-guard-pixels',type=int,default=5,help='Safety radius near long structural lines, 1..40')
    p.add_argument('--opencv-max-side',type=int,default=1024,help='OpenCV processing image max side, 128..4096')
    p.add_argument('--opencv-min-line-fraction',type=float,default=.09,help='Min line length / short photo dimension, .03..5')
    p.add_argument('--opencv-max-lines',type=int,default=250,help='Max protected structural lines, 1..1000')
    p.add_argument('--depth-repo',type=Path,help='Path to cloned Depth-Anything-V2 upstream')
    p.add_argument('--depth-weights',type=Path,help='Path to official Depth Anything V2 Small ViT-S .pth')
    p.add_argument('--depth-input-size',type=int,default=518,help='DA-V2 CPU inference input resolution')
    p.add_argument('--resize',type=int,default=640,help='MoGe output maximum dimension')
    p.add_argument('--resolution',type=int,default=3,help='MoGe inference resolution level 0-9')
    p.add_argument('--threshold',type=float,default=.04,help='MoGe mesh edge masking threshold')
    p.add_argument('--fov',type=float,help='Known horizontal field of view, degrees')
    p.add_argument('--max-triangles',type=int,default=0,help='Optional geometry budget; 0 preserves all triangles')
    a=p.parse_args()
    if a.from_glb is None and (a.photo is None or not a.photo.is_file()): p.error('Provide an image or --from-glb')
    if a.from_glb is not None and not a.from_glb.is_file(): p.error('--from-glb file missing')
    if a.depth_map is not None and not a.depth_map.is_file(): p.error('--depth-map missing')
    if a.segment_map is not None and not a.segment_map.is_file(): p.error('--segment-map missing')
    if a.opencv_map is not None and not a.opencv_map.is_file(): p.error('--opencv-map missing')
    if a.opencv_mode == 'off' and a.opencv_map is not None: p.error('Cannot use --opencv-map with --opencv-mode off')
    if a.opencv_mode != 'off' and a.depth_mode == 'off':
        p.error('OpenCV edge protection requires depth refinement; use --opencv-mode off')
    if a.opencv_mode != 'off' and a.photo is None and a.opencv_map is None:
        p.error('--opencv-mode lines with --from-glb needs photo or --opencv-map; use --opencv-mode off to skip')
    if not 1 <= a.opencv_guard_pixels <= 40: p.error('--opencv-guard-pixels must be in 1..40')
    if not 128 <= a.opencv_max_side <= 4096: p.error('--opencv-max-side must be in 128..4096')
    if not .03 <= a.opencv_min_line_fraction <= .5: p.error('--opencv-min-line-fraction must be in .03..5')
    if not 1 <= a.opencv_max_lines <= 1000: p.error('--opencv-max-lines must be in 1..1000')
    if a.segment_mode == 'off' and a.segment_map is not None: p.error('Cannot use --segment-map with --segment-mode off')
    if a.segment_mode != 'off' and a.depth_mode == 'off': p.error('MobileSAM seam guidance requires depth refinement; use --segment-mode off')
    if not 4 <= a.segment_grid <= 32: p.error('--segment-grid must be in 4..32')
    if not 1 <= a.seam_pixels <= 40: p.error('--seam-pixels must be in 1..40')
    if a.segment_mode != 'off' and a.photo is None and a.segment_map is None:
        p.error('--segment-mode edges with --from-glb needs a photo or --segment-map; use --segment-mode off to skip')
    if not 0 <= a.depth_strength <= 1: p.error('--depth-strength must be in [0,1]')
    if a.depth_mode == 'off' and a.depth_map is not None: p.error('Use --depth-mode refine with --depth-map')
    if a.max_triangles < 0 or (a.max_triangles and a.max_triangles < 200): p.error('--max-triangles must be 0 or >=200')
    if a.from_glb is not None and a.depth_mode == 'refine' and a.depth_map is None and a.photo is None:
        p.error('Use --depth-map or supply photo to run DA-V2; otherwise --depth-mode off')
    with tempfile.TemporaryDirectory(prefix='location-3d-') as tmp:
        work=Path(tmp)
        glb=a.from_glb if a.from_glb else infer_moge(a.photo.resolve(),work/'moge',a)
        depth=None
        if a.depth_mode == 'refine':
            depth_path=a.depth_map if a.depth_map is not None else infer_depth_anything(a.photo.resolve(),work,a)
            depth=load_depth(depth_path)
        segments=None
        if a.segment_mode == 'edges':
            seg_path=a.segment_map if a.segment_map is not None else infer_mobile_sam(a.photo.resolve(),work,a)
            segments=load_segments(seg_path)
        opencv_guard=None
        if a.opencv_mode == 'lines':
            from opencv_structure import load_structure
            guard_path=a.opencv_map if a.opencv_map is not None else infer_opencv(a.photo.resolve(),work,a)
            opencv_guard=load_structure(guard_path)
        return make_html(glb,a.output,a.max_triangles,depth,a.depth_strength,
                         segments,a.seam_pixels,opencv_guard)

if __name__=='__main__': cli()
