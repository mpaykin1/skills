import {createAvatarBuffer, validInput, valid, validGameId} from './protocol.mjs';
export async function createServerTransport({client,gameId,roomId,sampleInput,onState,onLeave,onError=()=>{},onSelf=()=>{},onDisconnect=()=>{}}){
 if(!validGameId(gameId)||typeof sampleInput!=='function')throw Error('Invalid server options');
 const opts={gameId,protocol:1};
 const room=roomId?await client.joinById(roomId,opts):await client.create('meta-v1',opts);
 const buffer=createAvatarBuffer({onState,onLeave});let seq=0,closed=false,lastTick=-1;const seen=new Set();
 room.onMessage('snapshot-v1',msg=>{
  if(closed||!msg||!Number.isSafeInteger(msg.tick)||msg.tick<=lastTick||!Array.isArray(msg.players)||msg.players.length>4)return;
  if(!msg.players.every(p=>p&&typeof p.id==='string'&&valid(p)))return;
  lastTick=msg.tick;const current=new Set();
  for(const p of msg.players){if(p.id===room.sessionId){onSelf(p);continue;}current.add(p.id);buffer.push(p.id,p);}
  for(const id of seen)if(!current.has(id))buffer.remove(id);seen.clear();for(const id of current)seen.add(id);
 });
 const timer=setInterval(()=>{if(closed)return;try{const a=sampleInput();const p={v:1,seq:seq++,dx:a.dx,dz:a.dz};if(validInput(p))room.send('input-v1',p);}catch(e){onError(e);}},1000/15);
 function cleanup(){if(closed)return false;closed=true;clearInterval(timer);buffer.clear();seen.clear();return true;}
 room.onError((code,message)=>{if(!closed)onError(Error(`${code}: ${message}`));});
 room.onLeave(code=>{if(cleanup())onDisconnect(code);});
 return {room,roomId:room.roomId,ready:Promise.resolve(room.sessionId),getInterpolated:buffer.getInterpolated,async leave(){if(cleanup())await room.leave();}};
}
