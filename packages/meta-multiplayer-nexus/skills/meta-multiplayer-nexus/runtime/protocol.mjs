const actions = new Set(['idle','walk','run','jump','crouch','roll','attack','hit','death']);
const finite = n => typeof n === 'number' && Number.isFinite(n);
export const valid = p => p && p.v===1 && Number.isSafeInteger(p.seq) && p.seq>=0 && ['x','y','z'].every(k=>finite(p[k])&&Math.abs(p[k])<=100000) && finite(p.yaw) && Math.abs(p.yaw)<=Math.PI*2 && actions.has(p.anim) && finite(p.phase) && p.phase>=0 && p.phase<=1;
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
export const validGameId = x => typeof x==='string' && /^[-a-z0-9]{1,80}$/i.test(x);
export const validInput = p => p && p.v===1 && Number.isSafeInteger(p.seq) && p.seq>=0 && finite(p.dx) && finite(p.dz) && Math.abs(p.dx)<=1 && Math.abs(p.dz)<=1;
export function createAvatarBuffer({onState=()=>{},onLeave=()=>{}}={}){
 const peers=new Map();
 return {push(id,p,now=performance.now()){
  if(typeof id!=='string'||id.length>128||!valid(p))return false;
  const old=peers.get(id);if(old&&p.seq<=old.next.seq)return false;
  const next={v:1,seq:p.seq,x:p.x,y:p.y,z:p.z,yaw:p.yaw,anim:p.anim,phase:p.phase};
  const teleport=old&&Math.hypot(next.x-old.next.x,next.y-old.next.y,next.z-old.next.z)>10;
  peers.set(id,{prev:old&&!teleport?old.next:next,next,at:now});onState(id,next);return true;
 },remove(id){if(peers.delete(id))onLeave(id);},clear(){for(const id of peers.keys())onLeave(id);peers.clear();},
 getInterpolated(id,now=performance.now()){
  const item=peers.get(id);if(!item)return null;const {prev,next,at}=item,t=clamp((now-at)/(1000/15),0,1),lerp=(a,b)=>a+(b-a)*t;
  const d=Math.atan2(Math.sin(next.yaw-prev.yaw),Math.cos(next.yaw-prev.yaw));
  return {...next,x:lerp(prev.x,next.x),y:lerp(prev.y,next.y),z:lerp(prev.z,next.z),yaw:prev.yaw+d*t};
 }};
}
