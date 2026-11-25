import {chooseVariation,validateMotifs} from './hybrid.mjs';
import {generatePiece,STYLES,ROOTS,MODES,makeTimeMap,performNotes,pedalledEnds} from './vendor/composer.js';
export {STYLES,ROOTS,MODES};
export function compose({style='nocturne',root='C',mode='minor',seed=1,tempo,melodySeed,leftSeed}={}) {
 if(!Object.hasOwn(STYLES,style)||!ROOTS.includes(root)||!MODES.includes(mode)) throw new RangeError('Unsupported style/root/mode');
 for(const s of [seed,melodySeed,leftSeed]) if(s!==undefined&&(!Number.isInteger(s)||s<0||s>0xffffffff)) throw new RangeError('Seed must be uint32');
 if(tempo!==undefined&&(!Number.isFinite(tempo)||tempo<30||tempo>220)) throw new RangeError('Tempo 30–220');
 return generatePiece({style,root,mode,seed,tempo,melodySeed,leftSeed});
}
export function performance(piece){
 const map=makeTimeMap(piece), offsets=performNotes(piece), ends=pedalledEnds(piece);
 const notes=piece.notes.map((n,i)=>({pitch:n.pitch,hand:n.hand,velocity:n.velocity,start:Math.max(0,map.toSeconds(n.time)+offsets[i]),end:Math.max(0.01,map.toSeconds(ends[i])+offsets[i])}));
 return {notes,totalSeconds:Math.max(map.totalSeconds,...notes.map(n=>n.end))};
}
const states={calm:['nocturne',60,'minor'],explore:['barcarolle',84,'minor'],danger:['elegy',78,'minor'],combat:['etude',144,'minor'],victory:['polonaise',108,'major']};
export class AdaptiveMusic{
 constructor({root='C',seed=1,motifBank=null}={}){this.motifBank=motifBank?validateMotifs(motifBank):null;this.root=root;this.seed=seed;this.state='calm';this.pending='calm';}
 request(event){if(!Object.hasOwn(states,event))throw new RangeError('Unknown event');this.pending=event;}
 next(){this.state=this.pending;const [style,tempo,mode]=states[this.state];const opts={style,tempo,mode,root:this.root,seed:this.seed};const hybrid=this.motifBank?chooseVariation(compose,opts,this.motifBank):null;const piece=hybrid?hybrid.piece:compose(opts);this.seed=(this.seed+(hybrid?hybrid.candidates:1))>>>0;return {state:this.state,piece,...performance(piece),motifDistance:hybrid?.distance??null};}
}
