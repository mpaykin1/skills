#!/usr/bin/env python3
"""Pair Khronos KTX candidates with *identical* PNG bytes embedded in a GLB.

Never modify the original GLB. Keep original PNGs as glTF fallback; add
KHR_texture_basisu sidecars only on SHA256 exact matches, never by filename.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
from pathlib import Path
import struct
import sys

KTX_MAGIC = b'\xabKTX 20\xbb\r\n\x1a\n'
PNG_MAGIC = b'\x89PNG\r\n\x1a\n'
JSON_CHUNK = 0x4E4F534A
BIN_CHUNK = 0x004E4942


def align4(data: bytes) -> bytes:
    return data + b'\0' * ((-len(data)) % 4)


def unpack_glb(path: Path):
    raw = path.read_bytes()
    if len(raw) < 20 or raw[:4] != b'glTF' or struct.unpack_from('<II',raw,4) != (2,len(raw)):
        raise ValueError('Expected complete GLB 2.0')
    jlen,jtype=struct.unpack_from('<II',raw,12)
    if jtype != JSON_CHUNK or jlen > 32*1024*1024 or 20+jlen>len(raw):
        raise ValueError('Invalid GLB JSON chunk')
    gltf=json.loads(raw[20:20+jlen])
    pos=20+jlen
    binary=b''
    if pos<len(raw):
        if pos+8>len(raw):raise ValueError('Truncated GLB BIN chunk')
        blen,btype=struct.unpack_from('<II',raw,pos)
        if btype!=BIN_CHUNK or pos+8+blen!=len(raw):raise ValueError('Malformed GLB BIN chunk')
        binary=raw[pos+8:]
    return gltf,binary


def image_data(image:dict, gltf:dict, binary:bytes)->bytes|None:
    if 'bufferView' in image:
        v=gltf['bufferViews'][image['bufferView']]
        if v['buffer']!=0:return None
        start=v.get('byteOffset',0)
        length=v['byteLength']
        if start<0 or length<1 or start+length>len(binary):
            raise ValueError('Invalid GLB image buffer view')
        return binary[start:start+length]
    uri=image.get('uri','')
    if uri.startswith('data:image/png;base64,'):
        return base64.b64decode(uri.split(',',1)[1],validate=True)
    return None


def embed(source:Path, manifest:Path, output:Path)->dict:
    source=source.expanduser().resolve(strict=True)
    manifest=manifest.expanduser().resolve(strict=True)
    output=output.expanduser().resolve()
    if output in (source,manifest):raise ValueError('Never overwrite source or KTX manifest')
    if output.exists():raise ValueError('Output exists; refuse overwrite: '+str(output))
    gltf,binary=unpack_glb(source)
    if len(binary) > 1024*1024*512:raise ValueError('GLB BIN exceeds 512 MiB limit')
    if not gltf.get('buffers') or len(gltf['buffers'])!=1 or gltf['buffers'][0].get('uri'):
        raise ValueError('Only self-contained one-BIN GLB files supported')
    manifest_obj=json.loads(manifest.read_text(encoding='utf8'))
    candidates={}
    for item in manifest_obj.get('textures',[]):
        if item.get('status')=='candidate' and item.get('validated_gltf_basisu') is True:
            digest=item.get('sha256')
            rel=item.get('output')
            if not isinstance(digest,str) or len(digest)!=64 or not isinstance(rel,str):continue
            ktx=(manifest.parent / rel).resolve(strict=True)
            if manifest.parent.resolve() not in ktx.parents:raise ValueError('KTX candidate escapes manifest directory')
            payload=ktx.read_bytes()
            if len(payload)<80 or payload[:12]!=KTX_MAGIC:
                raise ValueError('Invalid KTX2 candidate: '+str(ktx))
            existing=candidates.get(digest)
            if existing and existing[0]!=payload:
                raise ValueError('Conflicting KTX candidates for identical PNG hash '+digest)
            candidates[digest]=(payload,str(ktx))
    if not candidates:raise ValueError('Manifest contains no validated KTX2 candidates')
    png_to_ktx={}
    for i,img in enumerate(gltf.get('images',[])):
        raw=image_data(img,gltf,binary)
        if raw is None or raw[:8]!=PNG_MAGIC:continue
        digest=hashlib.sha256(raw).hexdigest()
        if digest not in candidates:continue
        width,height=struct.unpack_from('>II',raw,16)
        ktx,filename=candidates[digest]
        kw,kh=struct.unpack_from('<II',ktx,20)
        if (width,height)!=(kw,kh):raise ValueError(f'KTX dimension mismatch for GLB image {i}')
        png_to_ktx[i]=(ktx,filename)
    if not png_to_ktx:
        raise ValueError('No exact SHA256 match between original embedded PNG bytes and validated KTX2 candidates; nothing changed')
    # Preserve the original source PNG as core glTF texture fallback.
    original_texture_count=len(gltf.get('textures',[]))
    if original_texture_count==0:raise ValueError('Original GLB has no texture references')
    newbin=bytearray(binary)
    buffer_views=gltf.setdefault('bufferViews',[])
    images=gltf['images']
    mapped={}
    linked=[]
    for ti,tex in enumerate(gltf['textures']):
        original_img_index=tex.get('source')
        if original_img_index not in png_to_ktx:continue
        if (tex.get('extensions') or {}).get('KHR_texture_basisu'):
            continue
        if original_img_index not in mapped:
            ktx,ktx_path=png_to_ktx[original_img_index]
            offset=(len(newbin)+3)&~3
            newbin.extend(b'\0'*(offset-len(newbin)))
            newbin.extend(ktx)
            view_index=len(buffer_views)
            buffer_views.append({'buffer':0,'byteOffset':offset,'byteLength':len(ktx)})
            image_index=len(images)
            images.append({'name':images[original_img_index].get('name',f'image_{original_img_index}')+'_BasisU',
                           'bufferView':view_index,'mimeType':'image/ktx2'})
            mapped[original_img_index]=image_index
        tex.setdefault('extensions',{})['KHR_texture_basisu']={'source':mapped[original_img_index]}
        linked.append({'texture_index':ti,'png_image_index':original_img_index,
                       'ktx_image_index':mapped[original_img_index]})
    if not linked:raise ValueError('No original textures use SHA-matched PNG images')
    used=gltf.setdefault('extensionsUsed',[])
    if 'KHR_texture_basisu' not in used:used.append('KHR_texture_basisu')
    # Extension is NOT required: PNG fallback remains in texture.source.
    gltf['buffers'][0]['byteLength']=len(newbin)
    json_bytes=json.dumps(gltf,ensure_ascii=False,separators=(',',':')).encode('utf8')
    json_bytes=json_bytes+b' '*((-len(json_bytes))%4)
    bin_bytes=align4(bytes(newbin))
    total=12+8+len(json_bytes)+8+len(bin_bytes)
    data=(struct.pack('<4sII',b'glTF',2,total)
        +struct.pack('<II',len(json_bytes),JSON_CHUNK)+json_bytes
        +struct.pack('<II',len(bin_bytes),BIN_CHUNK)+bin_bytes)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_bytes(data)
    return {'glb':str(output),'textures':len(linked),'ktx_images':len(mapped),
            'original_glb_preserved':True,'png_fallback_preserved':True}


def main():
    p=argparse.ArgumentParser(description='Embed verified Khronos KTX2 candidates into original GLB, keeping PNG fallback')
    p.add_argument('glb',type=Path)
    p.add_argument('--manifest',type=Path,required=True,help='ktx2-candidates.json from ktx2_textures.py')
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(embed(a.glb,a.manifest,a.out),ensure_ascii=False))

if __name__=='__main__':
    try:main()
    except (OSError,ValueError,KeyError,IndexError,TypeError,json.JSONDecodeError) as exc:
        sys.exit('ERROR: '+str(exc))
