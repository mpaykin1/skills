import {Client} from '@heroiclabs/nakama-js';
import {createSession} from './session.mjs';
import {validGameId} from './protocol.mjs';
const uuid=/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i;
export function createSocial({host,port='443',serverKey,secure=true}){
 if(!host||!serverKey||(!secure&&!['localhost','127.0.0.1'].includes(host)))throw Error('Configure a trusted HTTPS Nakama endpoint');
 const client=new Client(serverKey,host,String(port),secure);let session=null;
 function current(){if(!session)throw Error('Sign in first');return session;}
 return {
  async signInDevice(deviceId,{create=true,username}={}){
   // Generate and retain an opt-in random device UUID, not a hardware fingerprint.
   if(!uuid.test(deviceId))throw Error('Use a random device UUID');
   session=await client.authenticateDevice(deviceId,create,username);
   return this.account();
  },
  async account(){const a=await client.getAccount(current());return {id:a.user.id,username:a.user.username};},
  async friends(){return client.listFriends(current(),0,100);},
  async addFriend(username){if(typeof username!=='string'||!username.trim()||username.length>128)throw Error('Invalid username');return client.addFriends(current(),[],[username.trim()]);},
  async load(gameId){if(!validGameId(gameId))throw Error('Invalid game');const a=await this.account();const r=await client.readStorageObjects(current(),{object_ids:[{collection:'meta_casual',key:gameId,user_id:a.id}]});return r.objects?.[0]??null;},
  async save(gameId,value,version){
   if(!validGameId(gameId)||!value||typeof value!=='object'||Array.isArray(value)||JSON.stringify(value).length>16000)throw Error('Invalid casual save');
   if(typeof version!=='string'||!version)throw Error('Use existing version or * for first save');
   // Casual settings/progress only; never currency, competitive results or authoritative unlocks.
   return client.writeStorageObjects(current(),[{collection:'meta_casual',key:gameId,value,permission_read:1,permission_write:1,version}]);
  },
  async openAccountRoom({client:colyseus,matchmaking=false,...options}){
   if(!colyseus?.auth)throw Error('Dedicated Colyseus client required');
   // Only use a dedicated client pointed at a configured trusted Colyseus origin.
   if(colyseus.auth.token)throw Error('Use a new dedicated Colyseus client');
   const s=current();await client.getAccount(s);colyseus.auth.token=s.token;
   try{return await createSession({...options,mode:'server',client:colyseus,accountRoom:true,matchmaking});}
   finally{colyseus.auth.token=undefined;}
  },
  async leaderboard(id){if(typeof id!=='string'||!/^[-_a-z0-9]{1,100}$/i.test(id))throw Error('Invalid leaderboard');return client.listLeaderboardRecords(current(),id,[],25);},
  clearLocalSession(){session=null;}
 };
}
export function makeInvite(page,{gameId,mode,roomId,queue='invite'}){
 if(!validGameId(gameId)||!['p2p','server'].includes(mode)||typeof roomId!=='string'||!/^[-_a-z0-9]{1,128}$/i.test(roomId)||!['invite','public'].includes(queue))throw Error('Invalid invite');
 const url=new URL(page);if(url.protocol!=='https:'||url.username||url.password)throw Error('HTTPS game URL required');
 // Do not propagate unrelated query strings, fragments, tokens or device IDs.
 url.search='';url.hash='';url.searchParams.set('game',gameId);url.searchParams.set('mp',mode);url.searchParams.set('room',roomId);url.searchParams.set('queue',queue);return url.toString();
}
