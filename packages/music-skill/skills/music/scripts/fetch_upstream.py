#!/usr/bin/env python3
"""Fetch immutable upstream Git blobs, verifying Git SHA-1 before writing."""
import hashlib, base64, json, pathlib, urllib.request
ROOT=pathlib.Path(__file__).resolve().parent/'vendor'
FILES={'composer.js':'42df242faa68dd34c37da60ee2d9bad99fddf5d3','midi.js':'63b6b0e1fcce9fe1bffaefb0342b1e89c29e3e5a','musicxml.js':'dcb63a0b5255f4d54e4e9b9617d1c133947d3cf2','LICENSE':'11dcb3b00aa51592ea88c079aa826c6d51ebe55e'}
def digest(data): return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
if __name__=='__main__':
    ROOT.mkdir(exist_ok=True)
    for name,sha in FILES.items():
        dest=ROOT/name
        if dest.exists() and digest(dest.read_bytes())==sha: continue
        req=urllib.request.Request('https://api.github.com/repos/stmn/piano-music-generator/git/blobs/'+sha,headers={'User-Agent':'META-MUSIC-Skill','Accept':'application/vnd.github+json'})
        with urllib.request.urlopen(req,timeout=30) as response: data=base64.b64decode(json.load(response)['content'])
        if digest(data)!=sha: raise ValueError('Unexpected Git blob SHA: '+name)
        dest.write_bytes(data)
    (ROOT/'package.json').write_text('{"type":"module"}\n')
