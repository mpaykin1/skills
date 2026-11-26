import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
const ORDER=['roles_conflict','refresh','repair','verify','integrate','stalled','finish','eligible'];
const terminal=new Set(['success','failure','cancelled','timed_out','action_required','skipped','neutral']);
export function decide(s){
 const result=(state,reason,owner='Скилы-4')=>({state,reason,owner,allowNewOSS:state==='eligible',head:s?.head??null});
 if(!s||!/^[a-f0-9]{40}$/i.test(s.head??'')) return result('refresh','Missing exact current HEAD','Skill Nexus');
 if(s.roles?.gameWriter!==':36'||s.roles?.nexus!==':48'||s.roles?.contradictions?.length) return result('roles_conflict','Resolve role conflict; :36 sole writer; :48 supervisor','Skill Nexus');
 if(s.checks?.head!==s.head||!Array.isArray(s.checks.required)||!s.checks.required.length||!Array.isArray(s.modules)||!Array.isArray(s.stages)||s.stages.length!==14||new Set(s.stages.map(x=>x.id)).size!==14||s.stages.some(x=>!Number.isInteger(x.id)||x.id<1||x.id>14))return result('refresh','Missing current checks, module consumers or 14-stage inventory','Skill Nexus');
 const failed=s.checks.required.filter(c=>terminal.has(c.conclusion)&&c.conclusion!=='success');
 if(failed.length)return result('repair',failed.map(c=>`${c.name}: ${c.conclusion}${c.jobId?' #'+c.jobId:''}`).join('; '));
 const pending=s.checks.required.filter(c=>c.conclusion!=='success');
 if(pending.length)return result('verify',pending.map(c=>c.name).join('; '));
 if(s.modules.some(m=>!m.path||!['integrated','pending','unknown'].includes(m.status)))return result('refresh','Module provenance missing','Skill Nexus');
 const debt=s.modules.find(m=>m.status!=='integrated'||m.consumerHead!==s.head||!m.consumerPath||m.runtimeVerified!==true);
 if(debt)return result('integrate',debt.path);
 const history=Array.isArray(s.runs)?s.runs.filter(r=>r.completed===true&&typeof r.id==='string'&&r.id):[];
 const last=[...new Map(history.map(r=>[r.id,r])).values()].slice(-2);
 if(last.length===2&&last.every(r=>r.stageDelta===0))return result('stalled','Two distinct completed runs without a closed stage');
 const next=[...s.stages].sort((a,b)=>a.id-b.id).find(x=>x.accepted!==true||x.acceptedHead!==s.head);
 if(next)return result('finish',`Stage ${next.id}: ${next.name??''}`);
 return result('eligible','All current milestones accepted; select next project need','Skill Nexus');
}
export async function route(s){
 const decision=decide(s);
 try{
  const {createMachine,createActor}=await import('xstate');
  const machine=createMachine({id:'nexus-progress',initial:'route',states:{route:{always:ORDER.map(state=>({target:state,guard:()=>decision.state===state}))},...Object.fromEntries(ORDER.map(state=>[state,{type:'final'}]))}});
  const actor=createActor(machine).start();const value=actor.getSnapshot().value;actor.stop();
  if(value!==decision.state)throw new Error('XState routing mismatch');
  return {...decision,engine:'xstate'};
 }catch(error){if(error.code!=='ERR_MODULE_NOT_FOUND')throw error;return {...decision,engine:'deterministic-fallback',dependency:'xstate not installed'};}
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){const input=JSON.parse(readFileSync(process.argv[2],'utf8'));console.log(JSON.stringify(await route(input),null,2));}
