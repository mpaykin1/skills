import {valid,createAvatarBuffer} from './protocol.mjs';
export function createTransport({joinRoom,gameId,roomId,sample,onState=()=>{},onLeave=()=>{},onError=()=>{}}){
  if(typeof joinRoom!=='function'||typeof sample!=='function'||!/^[-a-z0-9]{1,80}$/i.test(gameId)||!/^[-a-z0-9]{1,128}$/i.test(roomId))throw new Error('Invalid transport settings');
  const room=joinRoom({appId:`mpaykin1.github.io/meta-mp-v1/${gameId}`,maxUsers:4},roomId);
  const channel=room.makeAction('avatar-v1'), buffer=createAvatarBuffer({onState,onLeave});
  let seq=0,closed=false,busy=false;
  const off=[room.onError(onError),channel.onMessage((p,{userId})=>{
    if(!closed) buffer.push(userId,p);
  }),room.onUserLeave(({userId})=>{buffer.remove(userId);})];
  const tick=async()=>{if(closed||busy)return;busy=true;try{const raw=sample();const p={v:1,seq:seq++,x:raw.x,y:raw.y,z:raw.z,yaw:raw.yaw,anim:raw.anim,phase:raw.phase};if(valid(p))await channel.send(p);}catch(e){if(!closed)onError(e);}finally{busy=false;}};
  const timer=setInterval(tick,1000/15);
  return {room,ready:room.getSelf(),getInterpolated:buffer.getInterpolated,async leave(){if(closed)return;closed=true;clearInterval(timer);for(const unsubscribe of off)if(typeof unsubscribe==='function')unsubscribe();buffer.clear();await room.leave();}};
}
