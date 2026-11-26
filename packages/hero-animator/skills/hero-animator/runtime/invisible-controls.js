/* Invisible left joystick + explicit right action buttons. No scene-tap actions or timers. */
(function(root){'use strict';
 function create(canvas,keyboard,{audio=()=>{},camera=()=>{},buttons=globalThis.document?.getElementById('touchActions')}={}){
  const pointers=new Map(),edges=new Set(),heldButtons=new Map(),cleanups=[];
  const axis={x:0,z:0};let stick=null;
  const listen=(el,type,fn,options)=>{el?.addEventListener(type,fn,options);cleanups.push(()=>el?.removeEventListener(type,fn,options));};
  const focus=()=>canvas.focus?.({preventScroll:true});canvas.tabIndex=0;canvas.style.touchAction='none';
  function clear(){pointers.clear();heldButtons.clear();edges.clear();stick=null;axis.x=axis.z=0;keyboard.clear();}
  listen(canvas,'contextmenu',e=>e.preventDefault());
  listen(canvas,'pointerdown',e=>{if(e.button!==undefined&&e.button!==0)return;e.preventDefault();focus();audio();
   const kind=e.pointerType==='touch'&&e.clientX<innerWidth*.5?(stick===null?'stick':'ignored'):'camera';
   pointers.set(e.pointerId,{kind,x:e.clientX,y:e.clientY,sx:e.clientX,sy:e.clientY});
   if(kind==='stick'){stick=e.pointerId;axis.x=axis.z=0;}canvas.setPointerCapture?.(e.pointerId);
  });
  listen(canvas,'pointermove',e=>{const p=pointers.get(e.pointerId);if(!p)return;
   if(p.kind==='stick'){const dx=e.clientX-p.sx,dy=e.clientY-p.sy,l=Math.hypot(dx,dy),m=l<=9?0:Math.min(1,(l-9)/47);axis.x=l?dx/l*m:0;axis.z=l?-dy/l*m:0;}
   else if(p.kind==='camera')camera((e.clientX-p.x)*.006);p.x=e.clientX;p.y=e.clientY;
  });
  function end(e){if(e.pointerId===stick){stick=null;axis.x=axis.z=0;}pointers.delete(e.pointerId);heldButtons.delete(e.pointerId);}
  for(const ev of ['pointerup','pointercancel','lostpointercapture']){listen(canvas,ev,end);listen(buttons,ev,end);}
  const touchMode=()=>globalThis.matchMedia?.('(pointer: coarse) and (hover: none)').matches??false;
  const buttonHeld=a=>[...heldButtons.values()].includes(a);
  listen(buttons,'pointerdown',e=>{const b=e.target.closest?.('[data-hero-key]');if(!b||!touchMode()||!b.getClientRects().length||e.button!==0)return;
   e.preventDefault();e.stopPropagation();focus();audio();const action=b.dataset.heroKey;
   if(!buttonHeld(action)&&!keyboard.held(action))edges.add(action);heldButtons.set(e.pointerId,action);b.setPointerCapture?.(e.pointerId);
  });
  listen(buttons,'click',e=>{e.preventDefault();e.stopPropagation();});
  listen(window,'blur',clear);listen(document,'visibilitychange',()=>{if(document.hidden)clear();});
  const media=globalThis.matchMedia?.('(pointer: coarse) and (hover: none)');listen(media,'change',clear);
  const held=a=>keyboard.held(a)||buttonHeld(a)||(a==='run'&&Math.hypot(axis.x,axis.z)>.96)||(a==='left'&&axis.x<-.05)||(a==='right'&&axis.x>.05)||(a==='up'&&axis.z>.05)||(a==='down'&&axis.z<-.05);
  return {held,pressed:a=>keyboard.pressed(a)||edges.has(a),axes(){return stick===null?null:{...axis};},endFrame(){keyboard.endFrame();edges.clear();},clear,
   snapshot(){return {stick:stick!==null,axes:{...axis},pointers:pointers.size,buttons:[...heldButtons.values()],keyboard:keyboard.snapshot?.(),invisible:true,touchMode:touchMode(),sceneTapActions:false};},
   dispose(){clear();cleanups.forEach(f=>f());}};
 }
 root.HeroInvisibleControls=Object.freeze({version:'0.18.3',create});
})(globalThis);

