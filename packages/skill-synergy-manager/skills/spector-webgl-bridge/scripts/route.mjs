import {readFile} from "node:fs/promises";
const c=JSON.parse(await readFile(process.argv[2],"utf8"));
if(!Array.isArray(c.commands)||!c.commands.length)throw Error("missing real command list");
const counts={draw:0,texture:0,shader:0,framebuffer:0};
for(const x of c.commands){
 const n=String(x.name??"");
 if(/^draw(Arrays|Elements|RangeElements)|^multiDraw/.test(n))counts.draw++;
 if(/^(tex|compressedTex|copyTex)/.test(n))counts.texture++;
 if(/^(compileShader|linkProgram|shaderSource)$/.test(n))counts.shader++;
 if(/^(bindFramebuffer|framebufferTexture|checkFramebufferStatus)/.test(n))counts.framebuffer++;
}
const routes=[];
if(counts.shader||counts.framebuffer)routes.push("game-style-forge: inspect shader and framebuffer state");
if(counts.texture)routes.push("sprite-stacking-grunge / GIMP: inspect actual texture formats and alpha");
if(counts.draw)routes.push("meta-game-fusion / Blender: inspect draw batching and geometry");
console.log(JSON.stringify({commands:c.commands.length,counts,routes,note:"Command counts are inspection hints, not detected defects or measured FPS. Compare actual states and uninstrumented frames."},null,2));
