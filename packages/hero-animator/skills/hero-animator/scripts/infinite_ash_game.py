#!/usr/bin/env python3
"""Repair the recognized original with the seven world/input/art requirements.
Uses the real 44x8 art pack and existing legacy renderer; never invents approvals.
"""
import argparse,hashlib,json,re
from pathlib import Path
import complete_ash_game as previous
from repair_environment_props import repair as repair_environment

def build(original,pack,base,canonical_hash):
    quality=(base/'runtime/visual-quality.js').read_text(encoding='utf8')
    adventure=(base/'runtime/ash-adventure.js').read_text(encoding='utf8')
    src=previous.build(original,pack,quality,adventure,canonical_hash)
    def replace(old,new):
        nonlocal src
        if src.count(old)!=1:raise ValueError('Unsupported source: '+old[:100])
        src=src.replace(old,new,1)
    modules='\n'.join((base/('runtime/'+n)).read_text(encoding='utf8') for n in ['infinite-world.js','invisible-controls.js'])
    replace('<script>window.HERO_PACK=', '<script>'+modules+'</script><script>window.HERO_PACK=')
    replace('const input=VQ.createInput(', 'const keyboard=VQ.createInput(')
    replace('const keyboard=VQ.createInput({map:', 'const keyboard=VQ.createInput({canvas,buttons:null,map:')
    a=src.index('const obstacles=');b=src.index('let best=null;',a)
    src=src[:a]+"function blocked(){return false;}\n"+src[b:]
    a=src.index('let pointer=null;');b=src.index('function start()',a)
    src=src[:a]+"const input=HeroInvisibleControls.create(canvas,keyboard,{audio:unlockAudio,camera:delta=>{mouseYaw=VQ.clamp(mouseYaw+delta,-.96,.96);}});\n"+src[b:]
    a=src.index('function start()');b=src.index('// A ground decal',a)
    src=src[:a]+"game.begin();\nfunction updateHUD(){}\nwindow.addEventListener('keydown',()=>unlockAudio(),{once:true,capture:true});\n"+src[b:]
    replace('version:HeroAdventure.version,facing:', 'version:HeroAdventure.version,world:world.snapshot(),controls:input.snapshot(),npcArt:\'same-full-body-44-clip-pack\',facing:')
    # Correct screen-facing convention without flipping the asymmetric character.
    replace("heroFacing=VQ.selectView(player.yaw,heroYaw,4,heroFacing)","heroFacing=VQ.selectView(player.yaw,heroYaw,4,heroFacing)")
    a=src.index('for(const e of game.enemies){',src.index('function render(now)'));b=src.index('// Ground shadow:',a)
    src=src[:a]+src[b:]
    replace("for(let [x,y,z,w,h,d] of primitives)draw(box,HERO_PACK.ground?'earth_ground':'earth',model(x,y,z,w,h,d,0),{uv:[0,0,1,1],fog:.8,shade:.9});",'// No primitive box models are rendered.')
    # Streamed geometry is local to each chunk, allocated only on chunk transitions.
    a=src.index('let tile=[],grid=34;');b=src.index('function boxGeometry()',a)
    src=src[:a]+WORLD+src[b:]
    replace("draw(ground,HERO_PACK.ground?'earth_ground':'earth',model(0,0,0,1,1,1),{uv:[0,0,1.8,1.8],fog:.5,shade:.85,ground:1});", "for(const c of world.chunks.values())draw(c.mesh,HERO_PACK.ground?'earth_ground':'earth',model(c.cx*24,0,c.cz*24,1,1,1),{uv:[0,0,1,1],fog:.65,shade:.85,ground:1});")
    replace('const oldX=player.x,oldZ=player.z;', 'world.update(player.x,player.z,allocateChunk,mesh=>gl.deleteBuffer(mesh.buf));renderOrigin=[Math.floor(player.x/24)*24,Math.floor(player.z/24)*24];\nconst oldX=player.x,oldZ=player.z;')
    # Floating origin is applied before Float32 model/view matrices are formed.
    replace('function model(x,y,z,sx,sy,sz=1,yaw=0){', 'function model(x,y,z,sx,sy,sz=1,yaw=0){x-=renderOrigin[0];z-=renderOrigin[1];')
    replace('camEye=[cam.x,cam.y,cam.z];let focus=[player.x,1.9+player.y*.25,player.z-8];','camEye=[cam.x-renderOrigin[0],cam.y,cam.z-renderOrigin[1]];let focus=[player.x-renderOrigin[0],1.9+player.y*.25,player.z-8-renderOrigin[1]];')
    replace('draw(V.shadow,\'contact_shadow\',model(0,0,0,1,1,1)', "draw(V.shadow,'contact_shadow',model(renderOrigin[0],0,renderOrigin[1],1,1,1)")
    replace('return [x,terrainY(x,z)-.215,z,u,v,0,1,0]', 'return [x-renderOrigin[0],terrainY(x,z)-.215,z-renderOrigin[1],u,v,0,1,0]')
    replace("paint('original',0,-4,-72,170,56,0,1,0,0);", "paint('original',player.x,-4,player.z-80,230,70,0,1,0,0);")
    replace('const dir=[focus[0]-cam.x,focus[1]-cam.y,focus[2]-cam.z];', 'const dir=[focus[0]-camEye[0],focus[1]-camEye[1],focus[2]-camEye[2]];')
    # Decorative foreground is streamed, distant animated atmosphere follows the viewer.
    a=src.index('for(let [name,x,y,z,w,h,yaw,fog,shift,glow] of drawList)',src.index('const layers=[];'));b=src.index("layers.push(['portal',-6",a)
    src=src[:a]+SCENERY+src[b:]
    replace('for(const item of layers)paint(...item);', NPC+'\nfor(const item of layers)paint(...item);')
    # Portal light must stay at its global location after rebasing.
    replace('uniform float uLocalLight;uniform vec3 uTint;', 'uniform float uLocalLight;uniform vec3 uTint;uniform vec2 uOrigin;')
    replace("'uLocalLight','uTint']", "'uLocalLight','uTint','uOrigin']")
    replace('vW.xz-vec2(-6.,-9.)', 'vW.xz+uOrigin-vec2(-6.,-9.)')
    replace('gl.uniform3fv(loc.uTint,new Float32Array(options.tint||[1,1,1]));', 'gl.uniform2f(loc.uOrigin,renderOrigin[0],renderOrigin[1]);gl.uniform3fv(loc.uTint,new Float32Array(options.tint||[1,1,1]));')
    # Desktop stays clean; only real touch devices receive the explicit action pad.
    a=src.index('<body>');b=src.index('<script>',a)
    src=src[:a]+'''<body><canvas id="gl" tabindex="0" role="application" aria-label="Пепельный предел — игра. Стрелки или WASD: движение, J: удар, пробел: прыжок."></canvas><div hidden><div id="status"></div><div id="readout"></div></div>\n'''+TOUCH_UI+src[b:]
    replace('</style>', 'html,body{margin:0;width:100%;height:100%;overflow:hidden;background:#130c08;overscroll-behavior:none}canvas{position:fixed;inset:0;width:100vw;height:100vh;width:100dvw;height:100dvh;touch-action:none;display:block;outline:none}body>div{display:none!important}'+TOUCH_CSS+'</style>')
    # No stale implicit finite-world flags / cuboid geometry survive the build.
    a=src.index('function boxGeometry()');b=src.index('let T={}, ready=0;',a)
    src=src[:a]+src[b:]
    a=src.index('const primitives=');b=src.index('let fov=',a)
    src=src[:a]+src[b:]
    if "draw(box," in src or 'boxGeometry' in src:raise ValueError('Primitive model survived')
    # Required asset-first final stage: panorama fragments cannot enter the prop registry.
    return repair_environment(src,json.loads((base/'assets/complete-ash-props.json').read_text(encoding='utf8')),(base/'runtime/infinite-world.js').read_text(encoding='utf8'))

TOUCH_UI=r'''
<aside id="touchActions" aria-label="Действия героя">
 <button type="button" data-hero-key="attack" aria-label="Удар">УДАР</button>
 <button type="button" data-hero-key="jump" aria-label="Прыжок">ПРЫЖОК</button>
 <button type="button" data-hero-key="interact" aria-label="Взять печать или открыть портал">ВЗЯТЬ</button>
 <button type="button" data-hero-key="grab" aria-label="Удерживать для захвата, нажать удар для броска">ЗАХВАТ</button>
 <button type="button" data-hero-key="dodge" aria-label="Уклонение">УКЛОН</button>
 <button type="button" data-hero-key="roll" aria-label="Перекат">ПЕРЕКАТ</button>
 <button type="button" data-hero-key="crouch" aria-label="Удерживать чтобы присесть">ПРИСЕД</button>
 <button type="button" data-hero-key="pause" aria-label="Пауза или продолжение">ПАУЗА</button>
 <button type="button" data-hero-key="restart" aria-label="Начать заново">ЗАНОВО</button>
</aside>
'''
TOUCH_CSS=r'''
#touchActions{display:none;position:fixed;z-index:30;right:max(10px,env(safe-area-inset-right));bottom:max(12px,env(safe-area-inset-bottom));pointer-events:none;gap:6px;--action-size:clamp(46px,12.8vw,56px);grid-template-columns:repeat(3,var(--action-size));touch-action:none;user-select:none;-webkit-user-select:none}
#touchActions button{all:unset;box-sizing:border-box;display:flex;align-items:center;justify-content:center;width:var(--action-size);height:var(--action-size);border:1px solid #c8a471;background:#24180fe0;border-radius:50%;color:#ffdfac;font:600 9px/1.1 Arial,sans-serif;letter-spacing:0;opacity:.75;pointer-events:auto;touch-action:none;user-select:none;-webkit-user-select:none;-webkit-tap-highlight-color:transparent;box-shadow:0 2px 9px #0008}
#touchActions button:active{background:#704423e0;border-color:#ffdfac}
@media (pointer:coarse) and (hover:none){#touchActions{display:grid}}
'''

WORLD=r'''
let renderOrigin=[0,0];const world=HeroInfiniteWorld.create();
function allocateChunk(c){const v=[],n=6,size=24,ox=c.cx*size,oz=c.cz*size;const p=(i,j)=>{const x=i*size/n,z=j*size/n;return [x,terrainY(x+ox,z+oz)-.22,z,(x+ox)*.03,(z+oz)*.03,0,1,0];};for(let j=0;j<n;j++)for(let i=0;i<n;i++){const a=p(i,j),b=p(i+1,j),d=p(i,j+1),e=p(i+1,j+1);v.push(...a,...b,...e,...a,...e,...d);}return buffer(new Float32Array(v));}
'''
SCENERY=r'''
for(let [name,x,y,z,w,h,yaw,fog,shift,glow] of drawList){if(!['storm_clouds','burning_horizon','smoke_column','ash_hills','city_flames','ground_fog','embers'].includes(name))continue;const a=A[name];layers.push([name,x+player.x,y,z+player.z-12,w,h,Math.floor(t*1000*a.speed/180)%9,a.alpha,fog,glow,yaw]);}
for(const c of world.chunks.values())for(const p of c.props){const d=Math.hypot(p.x-player.x,p.z-player.z);if(d<6||d>62)continue;const a=A[p.type];layers.push([p.type,p.x,terrainY(p.x,p.z)-.22,p.z,p.size,p.size,Math.floor(t*1000*a.speed/180)%9,a.alpha,.75,0,Math.atan2(cam.x-p.x,cam.z-p.z)]);}
'''
NPC=r'''
for(const e of game.enemies){
 const yaw=Math.atan2(cam.x-e.x,cam.z-e.z),view=VQ.selectView(e.yaw,yaw,4),name='hero_'+view;
 const action=e.state==='dead'?'death':e.state==='windup'||e.state==='recover'?'attack':e.state==='stunned'?'hurt':e.state==='grabbed'?'grab':e.state==='chase'?'walk':'idle';
 const phase=action==='walk'?Math.floor((e.travel||0)/2.5*8)%8:action==='idle'?Math.floor(game.time*5+e.id*2.7)%8:Math.min(7,Math.floor(e.age/(action==='death'?1.1:action==='attack'?1.45:.8)*8));
 e.renderAction=action;e.renderFrame=phase;e.renderView=view;
 layers.push([name,e.x,terrainY(e.x,e.z)-.22-footInset,e.z,5,5,HeroAdventure.ACTIONS.indexOf(action)*8+phase,1,.08,0,yaw]);
 // Hostile rune halo and grounded shadow distinguish the fallen pilgrims without recolouring their art.

 if(e.state!=='dead')layers.push(['portal',e.x,terrainY(e.x,e.z)+2.7,e.z,.6,.6,Math.floor((game.time+e.id)*7)%9,e.state==='windup'?1:.6,.1,e.state==='windup'?1:.25,yaw]);
}
// Re-sort after inserting NPCs, preserving mutual occlusion with hero and scenery.
layers.sort((a,b)=>depth(b)-depth(a));
'''

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path);p.add_argument('pack',type=Path);p.add_argument('output',type=Path);p.add_argument('--canonical',type=Path,required=True);a=p.parse_args()
    if a.output.resolve()==a.input.resolve():p.error('Retain original input')
    base=Path(__file__).resolve().parent.parent
    out=build(a.input.read_text(encoding='utf8'),json.loads(a.pack.read_text(encoding='utf8')),base,hashlib.sha256(a.canonical.read_bytes()).hexdigest())
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(out,encoding='utf8');print(json.dumps({'output':str(a.output),'sha256':hashlib.sha256(a.output.read_bytes()).hexdigest(),'bytes':a.output.stat().st_size}))
if __name__=='__main__':main()

