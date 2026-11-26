import {Room,Server} from 'colyseus';
import R from '@dimforge/rapier3d-compat';
import {validGameId,validInput} from '../protocol.mjs';
import {createPhysics,DT} from '../physics.mjs';
import {verifyNakamaAccount} from './nakama-auth.mjs';
await R.init();
// Demo walking arena; replace static geometry with a trusted server-side level manifest before production.
class MetaRoom extends Room {
 maxClients=4;players=new Map();tick=0;acc=0;
 onCreate(options){
  if(!validGameId(options.gameId)||options.protocol!==1)throw Error('Invalid game/protocol');
  this.gameId=options.gameId;this.physics=createPhysics(R);
  this.onMessage('input-v1',(client,input)=>{
   const p=this.players.get(client.sessionId),now=Date.now();
   if(!p||!validInput(input)||input.seq<=p.inputSeq||now-p.lastInput<25)return;
   p.inputSeq=input.seq;p.lastInput=now;p.dx=input.dx;p.dz=input.dz;
  });
  this.setSimulationInterval(ms=>{this.acc=Math.min(this.acc+Math.max(0,ms/1000),DT*5);while(this.acc>=DT){this.step();this.acc-=DT;}},DT*1000);
 }
 onAuth(client,options){return options.gameId===this.gameId&&options.protocol===1;}
 // Recheck room namespace even if static authentication supplied client.auth.
 onJoin(client,options){if(options.gameId!==this.gameId||options.protocol!==1)throw Error('Room mismatch');const used=new Set([...this.players.values()].map(p=>p.slot));const slot=[0,1,2,3].find(i=>!used.has(i));if(slot===undefined)throw Error('Full room');this.physics.add(client.sessionId,{x:(slot-1.5)*2,y:0.05,z:0});this.players.set(client.sessionId,{slot,dx:0,dz:0,inputSeq:-1,lastInput:0});}
 onLeave(client){this.physics.remove(client.sessionId);this.players.delete(client.sessionId);}
 onDispose(){this.physics?.dispose();this.players.clear();}
 step(){const now=Date.now();this.tick++;for(const p of this.players.values())if(now-p.lastInput>350)p.dx=p.dz=0;
  this.physics.step(this.players);
  if(this.tick%2===0)this.broadcast('snapshot-v1',{tick:this.tick,players:[...this.players.keys()].map(id=>({id,v:1,seq:this.tick,...this.physics.sample(id)}))});
 }
}
class AccountRoom extends MetaRoom {
 static async onAuth(token,options){
  if(!validGameId(options.gameId)||options.protocol!==1||!['public','invite'].includes(options.queue))return false;
  return await verifyNakamaAccount(token,process.env.NAKAMA_API_ORIGIN);
 }
 async onCreate(options){
  if(!['public','invite'].includes(options.queue))throw Error('Invalid queue');
  this.queue=options.queue;super.onCreate(options);
  if(this.queue==='invite')await this.setPrivate(true);
 }
 onJoin(client,options,auth){
  if(!auth?.userId||options.queue!==this.queue)throw Error('Account or queue mismatch');
  if([...this.players.values()].some(p=>p.userId===auth.userId))throw Error('Account already joined');
  super.onJoin(client,options);this.players.get(client.sessionId).userId=auth.userId;
 }
}
const server=new Server();server.define('meta-v1',MetaRoom);
if(process.env.NAKAMA_API_ORIGIN)server.define('meta-account-v1',AccountRoom).filterBy(['gameId','protocol','queue']);
await server.listen(Number(process.env.PORT||2567));
