import assert from 'node:assert/strict';import '../runtime/ash-adventure.js';
const held=new Set(['up','run']);const input={held:k=>held.has(k),pressed:()=>false};const g=HeroAdventure.create({blocked:()=>false});g.begin();
let mismatch=null,exhaustedSeen=false,recovered=false;
for(let i=0;i<900;i++){
 const before={z:g.player.z,time:g.time};g.update(1/60,input);const speed=Math.abs(g.player.z-before.z)/(g.time-before.time);
 if(g.player.action==='run'&&speed<4){mismatch={frame:i,stamina:g.player.stamina,action:g.player.action,speed};break;}
 if(g.player.action==='walk'&&g.player.stamina<20)exhaustedSeen=true;
 if(exhaustedSeen&&g.player.action==='run'&&g.player.stamina>=19)recovered=true;
}
assert.equal(mismatch,null,JSON.stringify(mismatch));assert(exhaustedSeen,'exhaustion must switch to walk');assert(recovered,'sprint must recover after hysteresis threshold');
console.log('PASS: actual speed matches walk/run clip; exhausted sprint recovers without frame-to-frame toggling');
