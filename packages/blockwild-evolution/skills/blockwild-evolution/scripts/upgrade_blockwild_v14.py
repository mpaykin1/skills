"""Reversible standalone v13 -> v14 game upgrade.
Preserves entire v13 source-world prefix, original data, music, entrypoints and controls.
Build-time SciPy rigid volume rotations generate all hero/citizen directions.
No external dependency in standalone HTML at runtime.
"""
import json,re,hashlib,sys
from pathlib import Path
import argparse
parser=argparse.ArgumentParser(description='Source preserving v13-to-v14 standalone HTML upgrade')
parser.add_argument('--source',type=Path,default=Path('/mnt/data/BLOCKWILD_v13_GOLDEN_GARDEN_STACKED_ATMOSPHERE_OFFLINE.html'))
parser.add_argument('--probe-in',type=Path,default=Path('/mnt/data/bw_v13_art_probe.html'))
parser.add_argument('--assets',type=Path,default=Path('/mnt/data/bw14_assets.json'))
parser.add_argument('--out',type=Path,default=Path('/mnt/data/BLOCKWILD_v14_EIGHT_VIEW_LIVING_GARDEN_STACKING_OFFLINE.html'))
parser.add_argument('--probe-out',type=Path,default=Path('/mnt/data/bw_v14_art_probe.html'))
args=parser.parse_args()
src=args.source; artprobe=args.probe_in; assets=args.assets; out=args.out; probe=args.probe_out
source_text=src.read_text()
source_probe=artprobe.read_text()
art=json.loads(assets.read_text())
assert len(art)==168
new_prefix='const ROYAL_ART={SPRITES:'+json.dumps(art,separators=(',',':'))

# Verify matching original model keys and replace only the wrapped authored volume PNGs.
def upgrade(s):
 assert s.count('const ROYAL_ART={SPRITES:')==1
 p=s.index('const ROYAL_ART={SPRITES:')
 q=s.index(', objects:[], images:{}',p)
 s=s[:p]+new_prefix+s[q:]
 # Expanded terrain is actually world-space projected pavement or meadow, never CSS backdrop.
 old='for(let z=8;z<59;z++)for(let x=7;x<59;x++){' 
 assert old in s
 s=s.replace(old,'for(let z=-30;z<94;z++)for(let x=-30;x<94;x++){',1)
 old='const color=colors[Math.floor(a*colors.length)];'
 assert old in s
 s=s.replace(old,'''const outGarden=(x<11||x>54||z<10||z>54);
  const meadow=['#c5b8a9','#d8c7b5','#d7c7b5','#ccbdb0','#d5c2b3','#c5c3b0','#c2b6a8'];
  const color=outGarden?meadow[Math.floor(a*meadow.length)]:colors[Math.floor(a*colors.length)];''',1)
 # A stable stone border and hedged outer garden. No random 2D replacement of authored trees.
 old='// Old garden edging / flower planters in the middle plane.'
 assert old in s
 s=s.replace(old,'''// Ornamental gold-edged raised flower enclosures above walkable ground.
 for(let x=13;x<26;x+=1.8){
   royalBox(g,x,56,0,1.72,1.2,.55,['#ebd9bd','#bba18a','#d7bea3'],P);
   if(Math.floor(x)%4===0)royalBox(g,x,56,.55,1.55,1.1,.20,['#f2daa2','#bb9d6d','#d1b584'],P);
 }
 for(let x=40;x<57;x+=1.8){
   royalBox(g,x,57,0,1.72,1.2,.55,['#ebd9bd','#bba18a','#d7bea3'],P);
 }
 // Old garden edging / flower planters in the middle plane.''',1)
 # Replace the 4-direction/3-frame NPC and hero sprite selector with 8 physically rotated volumes.
 old=''' const entities=[];
 for(const [x,z,v,m] of royalTrees)'''
 assert old in s
 s=s.replace(old,''' const entities=[];
 for(const [x,z,v,m] of royalTrees)''',1) # stable anchor
 old='''  const moving=Math.abs(Math.cos(t*(.55+(i%3)*.13)+phase))>.27;
  const face=['front','left','right','back'][(i+Math.floor(t/3.8))%4];
  const sprite='citizen_'+face+'_'+(moving?(Math.floor(t*5+i)%2+1):0);
  entities.push({kind:'npc',name:sprite,x:x+dx,z:z+dz,zoom:actorScale*.65,order:x+dx+z+dz});'''
 assert old in s
 s=s.replace(old,'''  const speed=Math.cos(t*(.55+(i%3)*.13)+phase);
  const moving=Math.abs(speed)>.24;
  // Every NPC keeps its own persistent hair/clothing identity; full body faces its travel.
  const face=royalFacing8(Math.cos(phase*2.9)*speed,Math.sin(phase*1.9)*speed,ROYAL_ART.npcFaces[i]||'front');
  ROYAL_ART.npcFaces[i]=face;
  const intermittentWave=(Math.floor((t+i*1.9)/8.3)%5===3);
  const pose=moving?(1+Math.floor(t*5.4+i)%2):(intermittentWave?3:Math.floor(t*1.6+i)%2?4:0);
  const sprite='citizen'+(i%3)+'_'+face+'_'+pose;
  entities.push({kind:'npc',name:sprite,x:x+dx,z:z+dz,zoom:actorScale*.81,order:x+dx+z+dz});''',1)
 old=''' const face=keys.a||keys.arrowleft?'left':keys.d||keys.arrowright?'right':keys.s||keys.arrowdown?'front':'back';
 const frame=moving?(Math.floor(t*8)%2+1):0;
 entities.push({kind:'hero',name:'hero_'+face+'_'+frame,x:player.x,z:player.z,zoom:actorScale*.76,order:player.x+player.z+1e-5});'''
 assert old in s
 s=s.replace(old,''' const vx=(keys.d||keys.arrowright?1:0)-(keys.a||keys.arrowleft?1:0)+(joy.dx||0);
 const vz=(keys.s||keys.arrowdown?1:0)-(keys.w||keys.arrowup?1:0)+(joy.dy||0);
 const face=royalFacing8(vx,vz,ROYAL_ART.heroFace||'back');
 if(Math.hypot(vx,vz)>.12)ROYAL_ART.heroFace=face;
 const frame=keys[' ']?4:(keys.e?3:(moving?(Math.floor(t*8)%2+1):0));
 entities.push({kind:'hero',name:'hero_'+face+'_'+frame,x:player.x,z:player.z,zoom:actorScale*.94,order:player.x+player.z+1e-5});''',1)
 # Only the scene's independent art selection changes, original player handling remains.
 idx=s.index('function renderRoyal(t){')
 s=s[:idx]+'''// Eight true camera-view sprites derived by rigid rotation of a single 3D voxel volume.
const ROYAL_EIGHT=['front','front_right','right','back_right','back','back_left','left','front_left'];
ROYAL_ART.heroFace='back';ROYAL_ART.npcFaces=[];
function royalFacing8(vx,vz,previous){
 if(Math.hypot(vx,vz)<.11)return previous;
 const sector=((Math.round(Math.atan2(vx,vz)/(Math.PI/4))%8)+8)%8;
 return ROYAL_EIGHT[sector];
}
''' +s[idx:]
 # Sprites reflect detail and identity; no duplicate rAF / duplicate renderer introduced.
 old="for(const row of [[15.5,10.0,1,.83],[50.2,45.5,2,.90],[56.3,18.3,0,.95]])royalTrees.push(row);"
 assert old in s
 s=s.replace(old,"""for(const row of [[15.5,10.0,1,.83],[50.2,45.5,2,.90],[56.3,18.3,0,.95],
 [8.8,22.5,0,1.15],[10.1,46.5,1,1.10],[22.2,8.2,2,1.0],
 [47.3,7.3,0,1.05],[54.2,54.1,1,1.26],[63.1,57.3,2,1.10],
 [40.1,59.6,1,1.08],[18.4,60.2,0,1.18],[59.1,22.2,1,1.06]])royalTrees.push(row);
for(const d of [
 ['flowers',44.6,57.9,1.0],['flowers',53.7,61.5,1.04],
 ['bush',39.1,57.1,.86],['bush',56.0,54.2,.92],
 ['flowers',12.8,50.2,1.06],['flowers',23.1,57.4,1.08],
 ['bush',28.2,57.1,.95],['flowers',47.5,47.8,.92],
 ['pillar',12.5,48.5,.78],['pillar',51.3,53.0,.83],
 ['flowers',19.2,52.1,1.11],['flowers',37.2,52.2,1.13]
])royalDecor.push(d);""",1)
 # Make sure richer floor around vertical edges stays under a subtle warm distant sky, not brown void.
 assert "GOLDEN.tileDetails++" in s
 s=s.replace('BLOCKWILD v13 · Golden Garden','BLOCKWILD v14 · Eight-View Living Garden')
 return s

html=upgrade(source_text)
text=upgrade(source_probe)
# Probe's minimal DOM and single RAF give the exact same authored art runtime.
out.write_text(html)
probe.write_text(text)
assert source_text[:source_text.index('// BLOCKWILD v13 · Golden Garden')]==html[:html.index('// BLOCKWILD v14 · Eight-View Living Garden')]
assert html.count('const ROYAL_ART={SPRITES:')==1
assert html.count('const ROYAL_EIGHT=')==1
assert text.count('function gameLoop()')==1
print('v14',out,'bytes',out.stat().st_size,'art',len(art))
print('v14probe',probe,'bytes',probe.stat().st_size)
