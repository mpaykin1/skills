#!/usr/bin/env python3
"""Retrieve unmodified MIT Modular Riffs core, verified against Git blob hashes."""
import base64, hashlib, json, pathlib, urllib.request
ROOT=pathlib.Path(__file__).resolve().parent/'modular_riffs'
FILES={'LICENSE':'5d4a08cc363ae84d4baa40252cffc069e56fe64d','js/arranger.js':'a945b97dff2c26844e5300c9b5d88fc1699551c0','js/generator.js':'08e27c3264146d20a67b970db89fcb42707870d3','js/theory.js':'6157bc49faf5394119543bf5b8e0c229e40f9a92','js/library.js':'5d3944fa979395785c15ef5798c07a1da571f361','js/intensity.js':'3761de190528569c5ffbd47658605a6bac4550fa'}
def digest(data): return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
def main():
    for name,sha in FILES.items():
        dest=ROOT/name
        if dest.exists() and digest(dest.read_bytes())==sha: continue
        req=urllib.request.Request('https://api.github.com/repos/philoking/modularriffs/git/blobs/'+sha,headers={'User-Agent':'META-MUSIC-Skill','Accept':'application/vnd.github+json'})
        with urllib.request.urlopen(req,timeout=30) as response: data=base64.b64decode(json.load(response)['content'])
        if digest(data)!=sha: raise ValueError('Unexpected Git blob SHA: '+name)
        dest.parent.mkdir(parents=True,exist_ok=True); dest.write_bytes(data)
    (ROOT/'package.json').write_text('{"type":"module","private":true}\n',encoding='utf-8')
if __name__=='__main__': main()
