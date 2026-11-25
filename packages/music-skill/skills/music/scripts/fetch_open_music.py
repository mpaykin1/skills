#!/usr/bin/env python3
"""Fetch verified original Open Music 0.3.0 sources by immutable Git blob hash."""
import base64, hashlib, json, pathlib, urllib.request
ROOT=pathlib.Path(__file__).resolve().parent/'open_music'
FILES={'package.json':'99ca8fcec072ed906d48f3b6c9c674110d7fd357','LICENSE':'8377f4ae5896fbbf1a23f7780f72ad513e3b6b5d','src/arrangement.js':'022d875f921baa3287fbd1f200b626c29bff1b34','src/synth.js':'54556e42274db690e68a11d472b2748e5468fcf9','src/dsp.js':'a465dd74bae1942d96e30da07347959eb446a455','src/theory.js':'035a423f6253ea20cd58eab632ead97a9ea7b2a3','src/midi.js':'0e86168229327d13de245483baf00010811a6800','src/cli.js':'f223a86a379c3678e867abbe4c251fe563fb9f1b','src/presets/symphony.js':'4bc920b2844c9a78f399e2aad5cfea51053c2fdd','src/presets/dark-fantasy.js':'8953449019a3eae5988a61cbc575c0553c10e377','src/presets/galactic.js':'f70a9cbf9d3f6f145e64738867261cfa76190045','src/presets/bound-soul.js':'55b6b1cab7860ac91dd1f7e8b4d3385b8d2d1dfa','src/presets/soviet-march.js':'be15514c5a436d1c84535a60a2425a4b68ce46de'}
def digest(data): return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
def main():
    for name,sha in FILES.items():
        dest=ROOT/name
        if dest.exists() and digest(dest.read_bytes())==sha: continue
        req=urllib.request.Request('https://api.github.com/repos/jdsalasca/open-music/git/blobs/'+sha,headers={'User-Agent':'META-MUSIC-Skill','Accept':'application/vnd.github+json'})
        with urllib.request.urlopen(req,timeout=30) as response: data=base64.b64decode(json.load(response)['content'])
        if digest(data)!=sha: raise ValueError('Unexpected Git blob SHA: '+name)
        dest.parent.mkdir(parents=True,exist_ok=True); dest.write_bytes(data)
if __name__=='__main__': main()
