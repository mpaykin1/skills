import {readFileSync} from 'node:fs';
const states=['refresh','repair','verify','stalled','finish','complete'];
const hex=s=>typeof s==='string'&&/^[a-f0-9]{40}$/i.test(s);
const repos=['mpaykin1/meta6-lab','mpaykin1/World_server'];
export function decide(plan,s){
 const groups=plan?.groups||[], all=groups.flatMap(g=>g.tasks||[]),ids=new Set(all.map(t=>t.id));
 if(plan?.schema!=='telegram-meta-games-plan-v1'||groups.length!==7||all.length!==34||ids.size!==34||groups.some(g=>!g.tasks?.length||!Number.isFinite(g.weight)||g.weight<=0)||groups.reduce((a,g)=>a+g.weight,0)!==100)throw Error('Invalid canonical 34-task plan');
 const rows=Array.isArray(s?.tasks)?s.tasks:[],heads=s?.heads||{}, map=new Map(rows.map(r=>[r.id,r]));
 if(map.size!==rows.length||rows.some(r=>!ids.has(r.id)))throw Error('Invalid task snapshot');
 const current=r=>r&&repos.includes(r.repo)&&hex(r.sha)&&r.sha===heads[r.repo];
 const checks=r=>Array.isArray(r?.requiredChecks)&&r.requiredChecks.length>0&&r.requiredChecks.every(c=>c.sha===r.sha&&typeof c.name==='string'&&c.name.length>0);
 const accepted=t=>{const r=map.get(t.id);return current(r)&&checks(r)&&r.status==='accepted'&&r.criteriaVerified===true&&r.independentReview===true&&Array.isArray(r.verificationRefs)&&r.verificationRefs.some(v=>typeof v==='string'&&v.length>0)&&r.requiredChecks.every(c=>c.conclusion==='success');};
 const summary=groups.map(g=>{const n=g.tasks.filter(accepted).length;return{id:g.id,accepted:n,total:g.tasks.length,weight:g.weight,points:g.weight*n/g.tasks.length}});
 const percent=Math.round(summary.reduce((a,g)=>a+g.points,0)*10)/10;
 const result=(state,next,reason)=>({state,next,reason,percent,accepted:all.filter(accepted).length,total:34,groups:summary});
 if(!repos.every(r=>hex(heads[r])))return result('refresh',null,'Fetch exact current HEAD for both repos');
 const failed=rows.find(r=>current(r)&&checks(r)&&r.requiredChecks.some(c=>['failure','cancelled','timed_out','action_required'].includes(c.conclusion)));
 if(failed)return result('repair',failed.id,'Repair required CI without weakening it');
 const claimed=rows.find(r=>r.status==='accepted'&&!accepted({id:r.id}));if(claimed)return result('verify',claimed.id,'Revalidate acceptance on exact HEAD');
 const waiting=rows.find(r=>current(r)&&checks(r)&&r.requiredChecks.some(c=>c.conclusion!=='success'));if(waiting)return result('verify',waiting.id,'Required checks not green');
 const runs=[...new Map((s.runs||[]).filter(r=>r.completed===true&&typeof r.id==='string'&&r.id).map(r=>[r.id,r])).values()].slice(-2);
 if(runs.length===2&&runs.every(r=>r.acceptedDelta===0))return result('stalled',all.find(t=>!accepted(t))?.id||null,'Change blocker-resolution approach');
 const next=all.find(t=>!accepted(t));return next?result('finish',next.id,next.title):result('complete',null,'All 34 criteria accepted');
}
export async function route(plan,s){const d=decide(plan,s);let x;try{x=await import('xstate')}catch(e){if(e.code!=='ERR_MODULE_NOT_FOUND')throw e;return {...d,engine:'deterministic-fallback',dependency:'xstate not installed'}}const machine=x.createMachine({id:'telegram-progress',initial:'route',states:{route:{always:states.map(state=>({target:state,guard:()=>d.state===state}))},...Object.fromEntries(states.map(state=>[state,{type:'final'}]))}});const a=x.createActor(machine).start(),v=a.getSnapshot().value;a.stop();if(v!==d.state)throw Error('XState route mismatch');return {...d,engine:'xstate'}}
if(process.argv[2]&&process.argv[3])console.log(JSON.stringify(await route(JSON.parse(readFileSync(process.argv[2],'utf8')),JSON.parse(readFileSync(process.argv[3],'utf8'))),null,2));
