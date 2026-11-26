"""Lossless per-frame RGBA run packing; not NanoVDB file format."""
import argparse, hashlib, json, pathlib, shutil, struct
MAX=32*1024*1024

def encode(raw):
    words=memoryview(raw).cast('I'); n=len(words); out=bytearray(); i=0
    while i<n:
        j=i+1
        while j<n and j-i<128 and words[j]==words[i]: j+=1
        if j-i>=2:
            out.append(128+j-i-1); out.extend(raw[4*i:4*i+4]); i=j
        else:
            j=i+1
            while j<n and j-i<128 and not (j+1<n and words[j]==words[j+1]): j+=1
            out.append(j-i-1);out.extend(raw[4*i:4*j]);i=j
    return bytes(out)
def decode(blob,length):
    out=bytearray(); i=0
    while i<len(blob):
        tag=blob[i];i+=1;n=(tag&127)+1;k=4 if tag&128 else n*4
        if i+k>len(blob) or len(out)+n*4>length: raise ValueError('invalid run')
        out.extend(blob[i:i+k]*n if tag&128 else blob[i:i+k]);i+=k
    if len(out)!=length: raise ValueError('frame length')
    return bytes(out)
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('source',type=pathlib.Path);p.add_argument('out',type=pathlib.Path);a=p.parse_args()
    m=json.loads((a.source/'volume.json').read_text()); size=m['size']; n=m['frames']; L=4
    if m['schema']!='openvdb-fire-v1' or m['source']!='blender-mantaflow-openvdb' or len(size)!=3 or not all(type(x)==int and 2<=x<=64 for x in size) or not 16<=n<=64: raise ValueError('invalid source')
    for x in size:L*=x
    if L*n>MAX or (a.source/'volume.rgba').stat().st_size!=L*n:raise ValueError('size')
    raw=(a.source/'volume.rgba').read_bytes(); png=(a.source/'fallback.png').read_bytes()
    if sha(raw)!=m['sha256'] or sha(png)!=m['atlas_sha256']:raise ValueError('hash')
    data=bytearray(); index=[]
    for i in range(n):
        f=raw[i*L:(i+1)*L]; c=encode(f);mode='rle' if len(c)<len(f) else 'raw';b=c if mode=='rle' else f
        if (decode(b,L) if mode=='rle' else b)!=f:raise ValueError('roundtrip')
        index.append(dict(offset=len(data),length=len(b),mode=mode,sha256=sha(f)));data.extend(b)
    a.out.mkdir(parents=True,exist_ok=False); (a.out/'frames.bin').write_bytes(data);shutil.copyfile(a.source/'fallback.png',a.out/'fallback.png');(a.out/'volume.json').write_text(json.dumps(m,indent=2));(a.out/'sparse.json').write_text(json.dumps(dict(schema='meta-rgba-rle-v1',source_sha256=m['sha256'],sha256=sha(data),bytes=len(data),frame_bytes=L,frames=index),indent=2))
if __name__=='__main__':main()
