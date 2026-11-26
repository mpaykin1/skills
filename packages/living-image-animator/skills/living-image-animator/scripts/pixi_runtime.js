/* PixiJS v8: source-registered 2D + authored 2.5D planes and intact full-cel flipbooks.
   No skeletal transformations, optical-flow, canvas surrogate figures, or generated poses.
   Browser timing is 60Hz-capable; authored cels advance at project 24+ FPS. */
(async function main() {
  'use strict';
  const notice = document.getElementById('err');
  const fail = (e) => {
    notice.textContent = 'Не удалось запустить сцену PixiJS: ' + String(e && e.message || e);
    notice.style.display = 'flex';
  };
  try {
    if (!window.PIXI || !PIXI.Application || !PIXI.ImageSource) {
      throw new Error('PixiJS v8 не загружен. Для сетевой сборки требуется интернет; для автономной — встроенный PixiJS.');
    }
    const S = LIVING_SCENE;
    if (S.schema !== 'lia-pixijs-1' || !S.valid_gate || !S.no_deformation) {
      throw new Error('Сцена не подтверждена проверкой покадровой анимации.');
    }
    const app = new PIXI.Application();
    await app.init({resizeTo: window, backgroundColor: 0x080e17,
       antialias: false, preference: 'webgl', autoDensity: true,
       resolution: Math.min(2, window.devicePixelRatio || 1) });
    document.body.appendChild(app.canvas);
    app.canvas.style.imageRendering = 'pixelated';
    const world = new PIXI.Container();
    world.sortableChildren = true;
    app.stage.addChild(world);

    async function sourceFromData(uri) {
      const im = new Image();
      im.decoding = 'async';
      im.src = uri;
      if (im.decode) await im.decode();
      else await new Promise((resolve, reject) => {im.onload=resolve;im.onerror=reject;});
      return new PIXI.ImageSource({resource: im, scaleMode: 'nearest',
        autoGenerateMipmaps: false});
    }
    function sprite(source, rect) {
      const tex = rect ? new PIXI.Texture({source, frame:new PIXI.Rectangle(...rect)})
        : new PIXI.Texture({source});
      const s = new PIXI.Sprite(tex);
      s.roundPixels = true;
      return s;
    }
    const background = sprite(await sourceFromData(S.background));
    background.zIndex = -10000;
    world.addChild(background);
    const planes = [];
    for (const layer of S.layers) {
      const obj=sprite(await sourceFromData(layer.data));
      obj.zIndex=layer.z;
      world.addChild(obj);
      planes.push({object:obj,parallax:layer.parallax});
    }
    const avatars=[];
    for (const a of S.actors) {
      const sources=[];
      for (const data of a.sheets) sources.push(await sourceFromData(data));
      const [, ,w,h] = a.box;
      const tiles = a.frames.map(([page,x,y]) =>
        new PIXI.Texture({source:sources[page],frame:new PIXI.Rectangle(x,y,w,h)}));
      const figure=new PIXI.Sprite(tiles[a.phase]);
      figure.roundPixels=true;
      figure.zIndex=a.z;
      figure.position.set(a.box[0],a.box[1]);
      world.addChild(figure);
      avatars.push({figure,actor:a,tiles});
    }
    // Optional truly ambient particle stratum; no particle is a proxy for a moving character.
    let weather=[];
    if (S.weather === 'snow' || S.weather === 'rain') {
      const count=S.weather==='snow'?90:145;
      const group=new PIXI.Container();group.zIndex=10000;world.addChild(group);
      for(let i=0;i<count;i++){
        const r=S.weather==='snow'?(i%4===0?1.25:.8):.45;
        const p=new PIXI.Graphics();
        if (S.weather==='snow') p.circle(0,0,r).fill({color:0xe0edf8,alpha:.24+(i%5)*.07});
        else p.rect(0,0,.9,3+(i%5)).fill({color:0xabc6da,alpha:.12+(i%6)*.045});
        group.addChild(p);
        weather.push({sprite:p,x:((i*4093)%997)/997*S.W,
          y:((i*1741)%991)/991*S.H, speed:8+(i*53)%23});
      }
    }
    const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
    let mx=0,my=0;
    window.addEventListener('pointermove', ev => {
      mx=clamp(ev.clientX/Math.max(1,innerWidth)*2-1,-1,1);
      my=clamp(ev.clientY/Math.max(1,innerHeight)*2-1,-1,1);
    },{passive:true});
    const bounds={scale:1,offsetX:0,offsetY:0};
    function resize(){
      const k=Math.min(innerWidth/S.W,innerHeight/S.H);
      bounds.scale=k;
      bounds.offsetX=(innerWidth-S.W*k)/2;
      bounds.offsetY=(innerHeight-S.H*k)/2;
      app.stage.scale.set(k);
      app.stage.position.set(bounds.offsetX,bounds.offsetY);
    }
    window.addEventListener('resize',resize,{passive:true}); resize();

    function sample(path, t) {
      if(!path || path.length<2)return [0,0];
      if(t<=path[0].frame)return [path[0].dx,path[0].dy];
      for(let j=1;j<path.length;j++){
        const b=path[j],a=path[j-1];
        if(t<=b.frame){let u=(t-a.frame)/(b.frame-a.frame);u=u*u*(3-2*u);
          return [a.dx+(b.dx-a.dx)*u,a.dy+(b.dy-a.dy)*u];}
      }
      const last=path[path.length-1];return [last.dx,last.dy];
    }
    const launched=performance.now();
    app.ticker.add(()=>{
      // Continuous time and fixed integer frame index avoid frame skipping tied to monitor rate.
      const elapsed=(performance.now()-launched)/1000;
      const ix=Math.floor((elapsed % S.seconds)*S.fps);
      const shiftX=Math.sin(elapsed*.16)*Math.min(4,S.W*.005)+mx*Math.min(6,S.W*.008);
      const shiftY=Math.sin(elapsed*.11)*Math.min(3,S.H*.005)+my*Math.min(4,S.H*.006);
      background.x=shiftX*.15;background.y=shiftY*.15;
      for(const pl of planes){pl.object.x=shiftX*pl.parallax;pl.object.y=shiftY*pl.parallax;}
      for(const v of avatars){
        const a=v.actor,frame=(ix+a.phase)%v.tiles.length;
        const offset=sample(a.path,frame);
        v.figure.texture=v.tiles[frame];
        v.figure.x=a.box[0]+offset[0]+shiftX;
        v.figure.y=a.box[1]+offset[1]+shiftY;
      }
      for(const p of weather){
        p.sprite.x=(p.x+elapsed*(S.weather==='snow'?6:16))%(S.W+16)-8;
        p.sprite.y=(p.y+elapsed*p.speed)%(S.H+16)-8;
      }
    });
    document.addEventListener('visibilitychange',()=>{app.ticker.started=!document.hidden;});
    window.__livingScene = {app,actors:avatars.length,authoredFps:S.fps,pixiVersion:S.version};
  } catch (err) { fail(err); }
})();
