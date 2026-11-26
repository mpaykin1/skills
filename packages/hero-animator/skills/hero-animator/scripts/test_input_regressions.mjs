import assert from 'node:assert/strict';import '../runtime/visual-quality.js';
const target=new EventTarget(),doc=new EventTarget();doc.hidden=false;globalThis.document=doc;
const q=HeroVisualQuality,input=q.createInput({target,buttons:null,map:{ArrowLeft:'left',ArrowRight:'right',ArrowUp:'up',ArrowDown:'down',KeyJ:'attack',KeyW:'up'}});
function key(type,props){const e=new Event(type,{cancelable:true});for(const [k,v] of Object.entries(props))Object.defineProperty(e,k,{value:v});target.dispatchEvent(e);return e;}
for(const [keyName,action] of [['ArrowLeft','left'],['ArrowRight','right'],['ArrowUp','up'],['ArrowDown','down']]){
 for(const props of [{code:keyName},{key:keyName,code:''},{key:keyName.replace('Arrow',''),code:'Unidentified'},{keyCode:{left:37,right:39,up:38,down:40}[action]}]){
  assert(key('keydown',props).defaultPrevented);assert(input.held(action));assert(input.pressed(action));input.endFrame();key('keyup',props);assert(!input.held(action));
 }
}
key('keydown',{code:'ArrowUp'});key('keydown',{code:'KeyW'});key('keyup',{code:'ArrowUp'});assert(input.held('up'));key('keyup',{code:'KeyW'});assert(!input.held('up'));
key('keydown',{code:'KeyJ'});assert(input.pressed('attack'));input.endFrame();for(let n=0;n<20;n++){key('keydown',{code:'KeyJ',repeat:true});assert(!input.pressed('attack'));}key('keyup',{code:'KeyJ'});
key('keydown',{code:'ArrowLeft'});key('keydown',{code:'KeyJ'});target.dispatchEvent(new Event('blur'));assert(!input.held('left'));assert(!input.pressed('attack'));assert(!input.held('attack'));
input.dispose();console.log('PASS arrows code/key/legacy aliases, prevent scroll, W+Up ownership, one attack per physical edge, blur clears actions');
