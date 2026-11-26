import assert from 'node:assert/strict';import '../runtime/infinite-world.js';import '../runtime/visual-quality.js';
const W=HeroInfiniteWorld,world=W.create();let allocated=0,disposed=0;
const allocate=()=>{allocated++;return {};},dispose=()=>disposed++;
world.update(0,0,allocate,dispose);assert.equal(world.chunks.size,49);
const original=JSON.stringify(W.describe(-3,2));
for(const [x,z] of [[-500,0],[500,0],[0,-500],[0,500],[1e8,-1e8],[0,0]]){world.update(x,z,allocate,dispose);assert.equal(world.chunks.size,49);assert(world.chunks.has(Math.floor(x/24)+','+Math.floor(z/24)));}
assert.equal(allocated-disposed,49);assert.equal(JSON.stringify(W.describe(-3,2)),original);
for(const camera of [-.8,0,.8]){assert.equal(HeroVisualQuality.selectView(camera-Math.PI/2,camera,4),'left');assert.equal(HeroVisualQuality.selectView(camera+Math.PI/2,camera,4),'right');assert.equal(HeroVisualQuality.selectView(camera+Math.PI,camera,4),'back');assert.equal(HeroVisualQuality.selectView(camera,camera,4),'front');}
console.log('PASS deterministic positive/negative distant chunks, bounded/disposed cache, four screen-facing views at three camera angles');
