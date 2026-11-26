// Do not decode unverified JWTs. Ask the configured Nakama authority directly.
export async function verifyNakamaAccount(token,origin,request=fetch){
 if(typeof token!=='string'||token.length>8192||!/^[-_\w]+\.[-_\w]+\.[-_\w]+$/.test(token)||!origin)return false;
 try{
  const base=new URL(origin);
  if(!['http:','https:'].includes(base.protocol)||base.username||base.password||base.search||base.hash)return false;
  // HTTP is allowed only for trusted private network deployment, never public ingress.
  const response=await request(new URL('/v2/account',base),{headers:{Authorization:`Bearer ${token}`,Accept:'application/json'},redirect:'error',signal:AbortSignal.timeout(4000)});
  if(!response.ok)return false;
  const {user}=await response.json();
  if(typeof user?.id!=='string'||!/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(user.id))return false;
  return {userId:user.id};
 }catch{return false;}
}
