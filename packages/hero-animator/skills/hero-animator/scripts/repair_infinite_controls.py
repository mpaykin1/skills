#!/usr/bin/env python3
"""Repair input in an existing standalone Ash Frontier without needing the deleted original.
Recognized runtime only. Preserve every embedded original asset and every hero frame.
"""
import argparse,hashlib,re,json
from pathlib import Path
from infinite_ash_game import TOUCH_UI,TOUCH_CSS
from repair_environment_props import repair as repair_environment

def repair(src,base):
    if "HeroInfiniteWorld" not in src or "const keyboard=VQ.createInput({map:" not in src:
        raise ValueError('Expected the existing infinite-world game with the old input adapter')
    def embedded(text,name):
        m=re.search(r'window\.'+name+r'=(.*?);</script>',text,re.S)
        if not m:raise ValueError('Missing actual embedded '+name)
        return m[1]
    before={k:embedded(src,k) for k in ['ASSETS','HERO_PACK']}
    found=set()
    def update_script(m):
        s=m[1]
        if 'root.HeroVisualQuality=Object.freeze' in s:
            found.add('quality');s=(base/'runtime/visual-quality.js').read_text(encoding='utf8')
        elif 'root.HeroAdventure=Object.freeze' in s:
            found.add('adventure');s=(base/'runtime/ash-adventure.js').read_text(encoding='utf8')
        elif 'root.HeroInfiniteWorld=Object.freeze' in s and 'root.HeroInvisibleControls=Object.freeze' in s:
            found.add('controls');s='\n'.join((base/('runtime/'+n)).read_text(encoding='utf8') for n in ['infinite-world.js','invisible-controls.js'])
        return '<script>'+s+'</script>'
    src=re.sub(r'<script>(.*?)</script>',update_script,src,flags=re.S)
    if found!={'quality','adventure','controls'}:raise ValueError('Unsupported runtime '+str(found))
    def once(old,new):
        nonlocal src
        if src.count(old)!=1:raise ValueError('Expected one exact input adapter: '+old[:90])
        src=src.replace(old,new,1)
    once('const keyboard=VQ.createInput({map:', 'const keyboard=VQ.createInput({canvas,buttons:null,map:')
    once("window.addEventListener('keydown',()=>unlockAudio(),{once:true});", "window.addEventListener('keydown',()=>unlockAudio(),{once:true,capture:true});")
    once('<canvas id="gl" aria-label="Пепельный предел — игра">', '<canvas id="gl" tabindex="0" role="application" aria-label="Пепельный предел — игра. Стрелки или WASD: движение. J: удар, пробел: прыжок.">')
    once('</style>', 'canvas{outline:none}'+TOUCH_CSS+'</style>')
    once('</canvas>', '</canvas>'+TOUCH_UI)
    if any(embedded(src,k)!=v for k,v in before.items()):raise ValueError('Embedded artwork changed')
    return repair_environment(src,json.loads((base/'assets/complete-ash-props.json').read_text(encoding='utf8')),(base/'runtime/infinite-world.js').read_text(encoding='utf8'))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    if a.input.resolve()==a.output.resolve():p.error('Keep the previous HTML, write a new output')
    result=repair(a.input.read_text(encoding='utf8'),Path(__file__).resolve().parent.parent)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(result,encoding='utf8')
    print('Built '+str(a.output)+' SHA256 '+hashlib.sha256(a.output.read_bytes()).hexdigest())
if __name__=='__main__':main()
