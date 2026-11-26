#!/usr/bin/env python3
"""Organic PNG-derived foundation geometry for exported GLB buildings.

All assets come from source painted texture or deterministic mesh generation.
Scene nodes are named for animation by runtime foundation_effects.mjs.

No hard cut is accepted; generated skirt hides the bottom source mask seam.
"""
import math
import numpy as np
from PIL import Image, ImageEnhance
import trimesh
from trimesh.visual.material import PBRMaterial
from trimesh.visual.texture import TextureVisuals


def _stone_image(painting):
    im = painting.convert('RGBA')
    w,h = im.size
    # Sample the original lower facade: do not replace by unrelated stone art.
    crop = im.crop((0, int(h*.63), w, h))
    bg = Image.new('RGBA', crop.size, (11,25,42,255))
    bg.alpha_composite(crop)
    sample = bg.convert('RGB').resize((256,256), Image.Resampling.BICUBIC)
    return ImageEnhance.Brightness(sample).enhance(.78)


def _triangles(name, points, tris, uvs, texture, double_sided=True, alpha=False):
    mesh=trimesh.Trimesh(vertices=np.asarray(points,float),faces=np.asarray(tris,int),process=False)
    mesh.visual=TextureVisuals(uv=np.asarray(uvs,float), material=PBRMaterial(
        name=name, baseColorTexture=texture, metallicFactor=.02,
        roughnessFactor=.98, doubleSided=double_sided,
        alphaMode='BLEND' if alpha else 'OPAQUE'))
    return mesh


def _add_stone_mesh(scene,name,v,f,uv,paint):
    if f: scene.add_geometry(_triangles(name,v,f,uv,paint),node_name=name,geom_name=name)


def _rock(scene, w,h,d,paint,seed,drop=.39):
    """Real 3D asymmetrical inverted geological base; no flat bottom."""
    rng=np.random.default_rng(seed)
    y0=-h*.5
    R=9
    rings=[]
    for k,fac in enumerate([1.0,.94,.75,.50,.27,.075]):
        y=y0-h*drop*([0,.12,.33,.57,.81,1][k])
        ring=[]
        for j in range(R):
            a=2*math.pi*j/R
            jag=1.0+rng.uniform(-.13,.13)
            x=math.cos(a)*w*.52*fac*jag
            z=math.sin(a)*max(d*.55,w*.16)*fac*jag
            x+=math.sin(k*2.3+j)*w*.018*fac
            ring.append([x,y,z])
        rings.append(ring)
    v=np.asarray(rings).reshape((-1,3)).tolist(); uv=[]
    for k in range(len(rings)):
        for j in range(R): uv.append((j/R,1-k/(len(rings)-1)))
    f=[]
    for k in range(len(rings)-1):
        for j in range(R):
            a=k*R+j;b=k*R+(j+1)%R;c=(k+1)*R+j;e=(k+1)*R+(j+1)%R
            f.extend(((a,b,c),(b,e,c)))
    f.extend([(0,i+1,i) for i in range(1,R-1)])
    _add_stone_mesh(scene,'finish_rock_tapered',v,f,uv,paint)


def _box_uv(scene,name,position,size,paint):
    box=trimesh.creation.box(extents=size)
    box.apply_translation(position)
    box.unmerge_vertices()
    a=np.asarray(box.vertices)
    # UVs follow source surface proportion instead of blank colored faces.
    uv=np.stack(((a[:,0]-a[:,0].min())/max(np.ptp(a[:,0]),.001),
                 (a[:,1]-a[:,1].min())/max(np.ptp(a[:,1]),.001)),axis=-1)
    box.visual=TextureVisuals(uv=uv,material=PBRMaterial(
        name=name,baseColorTexture=paint,roughnessFactor=.95, metallicFactor=.02))
    scene.add_geometry(box,geom_name=name,node_name=name)


def _masonry(scene,w,h,d,paint):
    # An entire continuation section must never stop at a new flat unsupported edge.
    # A stepped profile merges into taper or arches below.
    y=-h*.5
    for i in range(3):
        drop=h*(.075 if i==0 else .065)
        span=w*(1.04-0.075*i)
        depth=d*(1.06-0.06*i)
        _box_uv(scene,f'finish_cornice_{i}',(0,y-drop*.48,0),(span,drop,depth),paint)
        y-=drop*.93
    return y


def _arch_rib(scene,name,x_center,y_center,radius,depth,paint):
    # Curved extruded stone band; opening is REAL empty geometry, not dark texture.
    verts=[];uv=[];faces=[]
    n=18
    # U-shaped arch band sampled from 0..pi (top semicircle), extruded front/back.
    for zidx,z in enumerate((-depth*.5,depth*.5)):
        for outer,rad in enumerate((radius*.78,radius)):
            for t in range(n+1):
                a=math.pi*t/n
                verts.append([x_center+rad*math.cos(a),y_center+rad*math.sin(a),z]);
                uv.append([t/n, outer*.5+zidx*.45])
    ring=n+1
    for zidx in range(2):
        b=zidx*2*ring
        for j in range(n):
            a=b+j; c=b+ring+j
            faces.extend(((a,c,a+1),(a+1,c,c+1)))
    for j in range(n):
        for k in range(2):
            a=k*2*ring+j; b=a+1; c=(1-k)*2*ring+j; e=c+1
            if k==0:faces.extend(((a,b,c),(b,e,c)))
    _add_stone_mesh(scene,name,verts,faces,uv,paint)


def _arches(scene,w,h,d,paint):
    """Counterfort piers, architectural arches and non-flat staggered lower tips."""
    base=-h*.5
    count=max(2,min(7,int(w/3)))
    span=w/count
    length=h*.22
    for j in range(count+1):
        x=-w*.5+span*j
        # Unequal lengths deliberately avoid the visually cropped horizontal edge.
        droop=length*(.80+.2*math.sin(j*2.1))
        _box_uv(scene,f'finish_pier_{j}',(x,base-droop*.46,0),
                (max(.12,w*.045),droop,max(.20,d*.94)),paint)
    for j in range(count):
        center=-w*.5+span*(j+.5)
        radius=span*.48
        _arch_rib(scene,f'finish_arch_{j}',center,base-length*.88,radius,d*.8,paint)


def _fragments(scene,w,h,d,paint,seed,n=13):
    rng=np.random.default_rng(seed+67)
    base=-h*.5
    for j in range(n):
        x=float(rng.uniform(-w*.55,w*.55)); z=float(rng.uniform(-d*.65,d*.65))
        y=base-h*float(rng.uniform(.12,.52))
        size=h*float(rng.uniform(.012,.044))
        shard=trimesh.creation.icosphere(subdivisions=0,radius=size)
        shard.apply_scale([rng.uniform(.6,1.5),rng.uniform(.5,2.3),rng.uniform(.5,1.4)])
        shard.apply_transform(trimesh.transformations.random_rotation_matrix())
        shard.apply_translation([x,y,z])
        shard.unmerge_vertices()
        verts=np.asarray(shard.vertices)
        uv=np.stack(((verts[:,0]-verts[:,0].min())/max(np.ptp(verts[:,0]),.001),
                     (verts[:,1]-verts[:,1].min())/max(np.ptp(verts[:,1]),.001)),axis=-1)
        shard.visual=TextureVisuals(uv=uv,material=PBRMaterial(name='SOURCE_DERIVED_SHARDS',baseColorTexture=paint,roughnessFactor=.86))
        name=f'finish_floating_shard_{j:02d}'
        scene.add_geometry(shard,geom_name=name,node_name=name)


def add_foundation(scene,painting,width,height,depth,mode='auto',seed=17):
    """Add source-derived 3D lower architecture; return runtime effect settings.

    Modes: 'rock', 'arches', 'masonry', 'fragments', 'mist', 'auto', 'none'.
    All modes except 'none' conceal the abrupt bottom with a physical cornice.
    The mist mode ALSO requires depth-aware runtime fog and softly dithered fade.
    """
    types={'auto','rock','arches','masonry','fragments','mist','none'}
    if mode not in types: raise ValueError(f'Unknown foundation {mode}')
    if mode=='none':return {'mode':'none','warning':'Unfinished PNG edge may remain visible'}
    paint=_stone_image(painting)
    # Core architectural foot hides the hard, straight edge of the source crop.
    _masonry(scene,width,height,depth,paint)
    chosen = ('rock' if height/width<1.1 else 'arches') if mode=='auto' else mode
    if chosen=='rock':_rock(scene,width,height,depth,paint,seed)
    if chosen=='arches':_arches(scene,width,height,depth,paint)
    if chosen=='masonry':_rock(scene,width,height,depth,paint,seed,drop=.19)
    if chosen=='fragments':
        _rock(scene,width,height,depth,paint,seed,drop=.13)
        _fragments(scene,width,height,depth,paint,seed,n=19)
    if chosen=='mist':
        _rock(scene,width,height,depth,paint,seed,drop=.16)
        _fragments(scene,width,height,depth,paint,seed,n=7)
    return {'mode':chosen,'source':'derived from original PNG',
            'glb_groups': ['finish_cornice_*','finish_rock_tapered','finish_pier_*','finish_arch_*','finish_floating_shard_*'],
            'runtime':{'fog':True,'blue_energy':True,'floating_fragments': chosen in ('fragments','mist'),
                       'volumetric_fade': chosen=='mist','require_no_flat_silhouette':True}}
