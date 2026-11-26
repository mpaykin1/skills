/* Deterministic, bounded terrain streaming. Global coordinates never wrap. */
(function(root){
 const SIZE=24,RADIUS=3;
 function hash(x,z,n=0){let h=Math.imul(x|0,374761393)^Math.imul(z|0,668265263)^Math.imul(n+31,1274126177);h=Math.imul(h^(h>>>13),1274126177);return ((h^(h>>>16))>>>0)/4294967296;}
 function describe(cx,cz){const props=[];for(let i=0;i<2;i++){const x=(cx+hash(cx,cz,i*3))*SIZE,z=(cz+hash(cx,cz,i*3+1))*SIZE;const choice=hash(cx,cz,i*3+2),type=['tree_ash_oak','tree_ash_elm','tree_ash_twisted'][Math.floor(choice*3)];props.push({x,z,type,size:8.5+hash(cx,cz,i+20)*3.5});}return {cx,cz,key:cx+','+cz,props};}
 function create(){const chunks=new Map();let center='';return {chunks,update(x,z,allocate,dispose){const cx=Math.floor(x/SIZE),cz=Math.floor(z/SIZE),key=cx+','+cz;if(key===center)return false;center=key;const wanted=new Set();for(let dz=-RADIUS;dz<=RADIUS;dz++)for(let dx=-RADIUS;dx<=RADIUS;dx++){const k=(cx+dx)+','+(cz+dz);wanted.add(k);if(!chunks.has(k)){const c=describe(cx+dx,cz+dz);c.mesh=allocate(c);chunks.set(k,c);}}for(const [k,c] of chunks)if(!wanted.has(k)){dispose(c.mesh);chunks.delete(k);}return true;},snapshot(){return {center,active:chunks.size,limit:49,size:SIZE,keys:[...chunks.keys()]};}};}
 root.HeroInfiniteWorld=Object.freeze({SIZE,RADIUS,hash,describe,create});
})(globalThis);
