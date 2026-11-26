import argparse, hashlib, json, tempfile, shutil
if not __debug__: raise RuntimeError("Run without -O")
from pathlib import Path
from pack_sparse import decode,sha,MAX

def audit(root):
    m=json.loads((root/'volume.json').read_text());s=json.loads((root/'sparse.json').read_text());L=4
    assert m['schema']=='openvdb-fire-v1' and 16<=m['frames']<=64 and len(m['size'])==3
    for x in m['size']:
        assert type(x)==int and 2<=x<=64;L*=x
    assert L*m['frames']<=MAX and s['schema']=='meta-rgba-rle-v1' and s['source_sha256']==m['sha256'] and s['frame_bytes']==L and len(s['frames'])==m['frames']
    assert (root/'frames.bin').stat().st_size<=L*m['frames'];b=(root/'frames.bin').read_bytes();assert len(b)==s['bytes'] and sha(b)==s['sha256']
    h=hashlib.sha256();pos=0
    with tempfile.TemporaryDirectory() as tmp:
        dst=Path(tmp)
        with (dst/'volume.rgba').open('wb') as f:
            for e in s['frames']:
                assert e['offset']==pos and 0<e['length']<=L and e['mode'] in ('rle','raw');x=b[pos:pos+e['length']];pos+=len(x);x=decode(x,L) if e['mode']=='rle' else x;assert len(x)==L and sha(x)==e['sha256'];h.update(x);f.write(x)
        assert pos==len(b) and h.hexdigest()==m['sha256'];shutil.copyfile(root/'volume.json',dst/'volume.json');shutil.copyfile(root/'fallback.png',dst/'fallback.png')
        # Existing source audit must pass: motion, seam and fallback.
        import sys
        sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'openvdb-fire'/'scripts'))
        from audit_volume import audit as original_audit
        original_audit(dst)
    return {'packed_bytes':len(b),'raw_bytes':L*m['frames'],'decode_bytes':L}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('pack',type=Path);print(audit(p.parse_args().pack))
