#!/usr/bin/env python3
"""Convert one user-owned facade PNG/JPEG cutout to a real textured GLB volume.
Requires: numpy, Pillow, opencv-python-headless, trimesh.
Works without Blender/network. The front retains original painting; rear and sides use distinct source-derived PNG art.
"""
import argparse
import io
from pathlib import Path
import numpy as np
from PIL import Image, ImageOps, ImageEnhance
import cv2
import trimesh
from trimesh.visual.material import PBRMaterial
from trimesh.visual.texture import TextureVisuals
from finish_edges import add_foundation


def cutout_rgba(im, white_bg):
    rgba = np.asarray(im.convert('RGBA')).copy()
    if white_bg:
        rgb = rgba[:, :, :3].astype(np.float32)
        # White JPG atlas: remove white and subpixel fringes, not dark or cyan artwork.
        white = np.min(rgb, axis=2)
        a = np.clip((255. - white) / 26., 0, 1)
        # Remove near-white chroma leftovers around glossy watercolor outlines.
        a *= np.clip((255. - np.mean(rgb, axis=2)) / 14., 0, 1)
        rgba[:, :, 3] = np.uint8(a * rgba[:, :, 3])
        # Unmatte formerly-white edge colors to avoid white outlining in 3D.
        safe = np.maximum(a, 0.02)[:, :, None]
        raw = (rgb - (1 - a[..., None]) * 255.) / safe
        rgba[:, :, :3] = np.clip(raw, 0, 255).astype('uint8')
    return rgba


def crop_to_alpha(rgba, border=2):
    ys, xs = np.where(rgba[:, :, 3] > 65)
    if not len(xs):
        raise ValueError('No opaque pixels. Check bounding box or transparency.')
    a, b = max(0, int(xs.min())-border), min(rgba.shape[1],int(xs.max())+border+1)
    c, d = max(0, int(ys.min())-border), min(rgba.shape[0],int(ys.max())+border+1)
    return rgba[c:d, a:b]


def paint_missing_views(front):
    """Produce distinct artistically INFERRED side/rear PNGs from supplied painted pixels.

    This is deliberate facade re-use, not claiming true photogrammetric recovery.
    The PNGs are first-class authored/inspectable artifacts, not flat shader colors.
    """
    src = front.convert('RGBA')
    W, H = src.size
    pix = np.asarray(src)
    opaque = pix[:, :, 3] > 96
    colors = pix[opaque, :3] if np.any(opaque) else np.array([[26, 51, 85]])
    stone = np.percentile(colors, 37, axis=0).astype('uint8')

    # Rear uses the original silhouette and palette but rearranges architectural
    # strips, creating a different (inferred) rear view, never an untextured plane.
    rear = ImageOps.mirror(src).copy()
    stripw = max(4, W // 12)
    for j in range(2, 10, 3):
        x = int(j * W / 12)
        patch = src.crop((max(0, x - stripw // 2), 0,
                          min(W, x + stripw // 2), H))
        if patch.width:
            rear.alpha_composite(patch, (max(0, W - x - patch.width), 0))
    rear.putalpha(ImageOps.mirror(src.getchannel('A')))
    # Side is built from ORIGINAL artwork bands; no generic boxes or flat color.
    target_w = max(128, min(768, W // 2))
    left = src.crop((max(0, W // 9), 0, max(1, W // 3), H))
    right = src.crop((max(0, 2 * W // 3), 0, max(1, 8 * W // 9), H))
    bands = [b for b in (left, right) if b.width > 0]
    side = Image.new('RGBA', (target_w, H), tuple(map(int, stone)) + (255,))
    x = 0
    k = 0
    while x < target_w:
        band = bands[k % len(bands)]
        patch = Image.new('RGBA', band.size, tuple(map(int, stone)) + (255,))
        patch.alpha_composite(band)
        side.alpha_composite(patch, (x, 0))
        x += band.width
        k += 1
    side = ImageEnhance.Brightness(side).enhance(0.78)
    # Left and right keep the same architectural language, but have different
    # original-pixel bands and opening arrangements.
    left_side = side.copy()
    right_side = ImageOps.mirror(side)
    right_side = ImageEnhance.Brightness(right_side).enhance(1.08)
    # A distinct roof bitmap reuses the hand-painted upper facade / finial art.
    roof_crop = src.crop((0, 0, W, max(1, H // 5)))
    roof = Image.new('RGBA', (target_w, max(64, H // 6)), tuple(map(int, stone)) + (255,))
    roof.alpha_composite(roof_crop.resize(roof.size, Image.Resampling.BICUBIC))
    return left_side, right_side, rear, roof


def textured_quad(width, height, z, image, back=False):
    w, h = width / 2, height / 2
    verts = np.array([[-w,-h,z],[w,-h,z],[w,h,z],[-w,h,z]], dtype=np.float64)
    if not back:
        faces = np.array([[0,1,2],[0,2,3]])
        uv = [[0,0],[1,0],[1,1],[0,1]]
    else:
        faces = np.array([[2,1,0],[3,2,0]])
        uv = [[1,1],[0,1],[0,0],[1,0]]
    material = PBRMaterial(name='SOURCE_PNG_FACADE', baseColorTexture=image,
                           alphaMode='BLEND', doubleSided=False,
                           metallicFactor=0., roughnessFactor=.94)
    mesh = trimesh.Trimesh(vertices=verts,faces=faces,process=False)
    mesh.visual = TextureVisuals(uv=np.array(uv),material=material)
    return mesh


def contour_walls(rgba, width, height, thickness, simplify, textures):
    """Actual extruded surfaces, UV-mapped from distinct left/right/roof PNGs."""
    H, W = rgba.shape[:2]
    mask = np.uint8(rgba[:, :, 3] > 96) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    groups = {k: {'verts':[], 'faces':[], 'uv':[]} for k in ('left', 'right', 'roof')}
    cutoff_area = max(9, .00005 * W * H)
    for contour in contours:
        if abs(cv2.contourArea(contour)) < cutoff_area:
            continue
        contour = cv2.approxPolyDP(contour, simplify, True).reshape(-1, 2)
        if len(contour) < 3:
            continue
        for i in range(len(contour)):
            x0, y0 = contour[i]
            x1, y1 = contour[(i+1) % len(contour)]
            a = (x0 / W * width - width/2, height/2 - y0 / H * height)
            b = (x1 / W * width - width/2, height/2 - y1 / H * height)
            if np.linalg.norm(np.array(a) - np.array(b)) < .025:
                continue
            horizontal = abs(x1 - x0) > abs(y1 - y0) * 1.3
            kind = ('roof' if horizontal and (y0+y1)/2 < H*.55
                    else 'left' if (x0+x1)/2 < W/2 else 'right')
            group = groups[kind]
            j = len(group['verts'])
            group['verts'].extend([[a[0],a[1],thickness/2],
                                   [b[0],b[1],thickness/2],
                                   [b[0],b[1],-thickness/2],
                                   [a[0],a[1],-thickness/2]])
            group['faces'].extend([[j,j+1,j+2],[j,j+2,j+3]])
            v0, v1 = 1.0 - float(y0)/H, 1.0 - float(y1)/H
            group['uv'].extend([[0.0,v0],[0.0,v1],[1.0,v1],[1.0,v0]])
    result = {}
    for kind,g in groups.items():
        if not g['faces']:
            continue
        mesh = trimesh.Trimesh(vertices=g['verts'],faces=g['faces'],process=False)
        mesh.visual = TextureVisuals(uv=np.asarray(g['uv'], dtype=float),
            material=PBRMaterial(name=f'SOURCE_DERIVED_{kind.upper()}_PNG',
                baseColorTexture=textures[kind], metallicFactor=.08,
                roughnessFactor=.90, doubleSided=True))
        result[kind] = mesh
    if not result:
        raise ValueError('No contour surfaces found in facade image.')
    return result


def build(input_path, output_path, bbox=None, height=12, depth=1.8,
          white_bg=False, simplify=1.5, foundation="auto", foundation_seed=17):
    src = Image.open(input_path).convert('RGBA')
    if bbox:
        if bbox[2]<=bbox[0] or bbox[3]<=bbox[1]: raise ValueError('Invalid bbox')
        src = src.crop(tuple(bbox))
    rgba = crop_to_alpha(cutout_rgba(src,white_bg))
    H,W = rgba.shape[:2]
    width=height*W/H
    image = Image.fromarray(rgba,'RGBA')
    left_png, right_png, back_png, roof_png = paint_missing_views(image)
    scene=trimesh.Scene()
    front=textured_quad(width,height,depth/2,image,False)
    back=textured_quad(width,height,-depth/2,back_png,True)
    surfaces=contour_walls(rgba,width,height,depth,simplify,
        {'left':left_png,'right':right_png,'roof':roof_png})
    scene.add_geometry(front,geom_name='original_png_front',node_name='facade_front')
    scene.add_geometry(back,geom_name='original_png_back',node_name='facade_back')
    for kind, mesh in surfaces.items():
        scene.add_geometry(mesh,geom_name=f'original_png_derived_{kind}',node_name=f'gothic_{kind}_volumetric_surfaces')
    finish = add_foundation(scene, image, width, height, depth, mode=foundation, seed=foundation_seed)
    Path(output_path).parent.mkdir(parents=True,exist_ok=True)
    scene.export(output_path,file_type='glb')
    png=Path(output_path).with_suffix('.png')
    image.save(png)
    left_png.save(Path(output_path).with_name(Path(output_path).stem + '_left.png'))
    right_png.save(Path(output_path).with_name(Path(output_path).stem + '_right.png'))
    roof_png.save(Path(output_path).with_name(Path(output_path).stem + '_roof.png'))
    back_png.save(Path(output_path).with_name(Path(output_path).stem + '_back.png'))
    import json
    Path(output_path).with_suffix(".foundation.json").write_text(json.dumps(finish, indent=2), encoding="utf8")
    return width,height,depth,output_path,png


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source'); p.add_argument('output')
    p.add_argument('--bbox',type=int,nargs=4,metavar=('LEFT','TOP','RIGHT','BOTTOM'))
    p.add_argument('--height',type=float,default=12)
    p.add_argument('--depth',type=float,default=1.8)
    p.add_argument('--white-bg',action='store_true',help='Remove white atlas background')
    p.add_argument('--simplify',type=float,default=1.5)
    p.add_argument("--foundation", choices=["auto","rock","arches","masonry","fragments","mist","none"],default="auto")
    p.add_argument("--foundation-seed",type=int,default=17)
    a=p.parse_args()
    res=build(a.source,a.output,a.bbox,a.height,a.depth,a.white_bg,a.simplify,a.foundation,a.foundation_seed)
    print(f'GLB: {res[-2]} | transparent PNG: {res[-1]} | units: {res[0]:.2f}x{res[1]:.2f}x{res[2]:.2f}')

if __name__=='__main__':main()
