#!/usr/bin/env node
// Bundle Three.js and Khronos GLTFLoader to ONE HTML with ONE original GLB.
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { build } from 'esbuild';

const base = path.dirname(fileURLToPath(import.meta.url));
const [input, output, title = 'Original 3D Scene'] = process.argv.slice(2);
if (!input || !output) {
  console.error('Usage: node build-three-html.mjs model.glb output.html [title]');
  process.exit(2);
}
const bytes = await fs.readFile(input);
function validateGlb(buf) {
  if (buf.length < 20 || buf.toString('ascii', 0, 4) !== 'glTF' || buf.readUInt32LE(4) !== 2 || buf.readUInt32LE(8) !== buf.length)
    throw new Error('Input must be a complete GLB 2.0 file');
  const len = buf.readUInt32LE(12);
  if (buf.readUInt32LE(16) !== 0x4e4f534a || len > 32 * 1024 * 1024 || len > buf.length - 20)
    throw new Error('GLB JSON chunk invalid');
  const gltf = JSON.parse(buf.subarray(20, 20 + len).toString('utf8'));
  for (const k of ['images', 'buffers']) {
    for (const entry of gltf[k] || []) {
      if (entry.uri && !entry.uri.startsWith('data:')) {
        throw new Error(`External ${k} URI is not autonomous: ${entry.uri}`);
      }
    }
  }
  const supported = new Set(['KHR_texture_basisu','KHR_materials_clearcoat','KHR_materials_unlit','KHR_materials_transmission','KHR_materials_volume','KHR_materials_ior','KHR_materials_specular','KHR_materials_sheen','KHR_materials_emissive_strength','KHR_materials_iridescence','KHR_materials_dispersion','KHR_lights_punctual','KHR_texture_transform','EXT_meshopt_compression','KHR_mesh_quantization','KHR_draco_mesh_compression','KHR_mesh_gpu_instancing']);
  const unsupportedRequired = (gltf.extensionsRequired || []).filter(x => !supported.has(x));
  if (unsupportedRequired.length) throw new Error(`Unsupported required glTF extensions: ${unsupportedRequired.join(', ')}`);
  if ((gltf.extensionsUsed || []).includes('KHR_draco_mesh_compression')) throw new Error('Draco decoder not embedded: convert to uncompressed GLB first');
  if ((gltf.extensionsUsed || []).includes('KHR_animation_pointer')) throw new Error('KHR_animation_pointer animation requires separate verified Three.js support; not packaging as playable animation');
  if ((gltf.extensionsUsed || []).includes('KHR_materials_variants')) throw new Error('KHR_materials_variants interactive selection not supported in this minimal visual viewer');
  return gltf;
}
const gltf = validateGlb(bytes);
const threeLicense = await fs.readFile(path.join(base,'node_modules','three','LICENSE'),'utf8');
const hasBasis = (gltf.extensionsUsed || []).includes('KHR_texture_basisu')
  || (gltf.textures || []).some(t => t.extensions?.KHR_texture_basisu);
// All transcoder data is obtained from the pinned local `three` npm package,
// not from a CDN. Do not download anything when opening the final HTML.
let basisJs = null, basisWasm = null, basisLicense = '';
if (hasBasis) {
  const lib = path.join(base, 'node_modules', 'three', 'examples', 'jsm', 'libs', 'basis');
  basisJs = await fs.readFile(path.join(lib, 'basis_transcoder.js'));
  basisWasm = await fs.readFile(path.join(lib, 'basis_transcoder.wasm'));
  if (basisWasm.length < 8 || basisWasm.subarray(0, 4).toString('hex') !== '0061736d')
    throw new Error('Pinned Three.js Basis Universal WASM missing or invalid');
  basisLicense = await fs.readFile(path.join(base, 'basis-apache-2.0.txt'), 'utf8');
}
const offlineBasisLoaderPlugin = {
  name: 'strip-ktx2-loader-network-defaults',
  setup(b) {
    b.onLoad({filter: /[\\/]KTX2Loader\.js$/}, async ({path: filename}) => {
      let source = await fs.readFile(filename, 'utf8');
      // KTX2Loader constructs these URLs at module initialization. In an IIFE
      // there is no import.meta.url; our local LoadingManager supplies Blob URLs.
      const regex = /new URL\(\s*'\.\.\/libs\/basis\/(basis_transcoder\.(?:wasm|js))',\s*import\.meta\.url\s*\)\.toString\(\)/g;
      let replaced = 0;
      source = source.replace(regex, (_, name) => { replaced++; return JSON.stringify('embedded:///' + name); });
      if (replaced !== 2) throw new Error('Three KTX2Loader URL API changed; refusing unverified bundling');
      return {contents: source, loader: 'js'};
    });
  }
};
const bundled = await build({
  entryPoints: [path.join(base, 'visual-runtime.mjs')],
  bundle: true, write: false, format: 'iife', platform: 'browser', minify: true,
  target: ['es2020'], charset: 'utf8', logLevel: 'warning',
  legalComments: 'none', define: {'__HAS_BASIS__': hasBasis ? 'true' : 'false'},
  plugins: [offlineBasisLoaderPlugin]
});
const js = bundled.outputFiles[0]?.text;
if (!js) throw new Error('esbuild did not return bundled JavaScript');
const safe = value => String(value).replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const basisTags = hasBasis
  ? `<script id="basis-js" type="application/octet-stream">${basisJs.toString('base64')}</script><script id="basis-wasm" type="application/octet-stream">${basisWasm.toString('base64')}</script><script id="basis-license" type="text/plain">${basisLicense.replace(/<\/script/gi, '<\\/script')}</script>`
  : '';
const html = `<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,viewport-fit=cover"><title>${safe(title)}</title>
<style>
:root{color-scheme:dark;font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}*{box-sizing:border-box}body{margin:0;background:#080d13;color:#edf5fb;overflow:hidden}#scene{width:100vw;height:100dvh;touch-action:none}#scene canvas{width:100%;height:100%;display:block}header{position:absolute;top:0;left:0;right:0;z-index:2;padding:18px 24px;background:linear-gradient(#07111dda,transparent);pointer-events:none}h1{font-size:14px;letter-spacing:.12em;text-transform:uppercase;margin:0 0 6px;font-weight:600}#status{font-size:11px;color:#afc8d5;letter-spacing:.07em}#loading{position:absolute;inset:0;display:grid;place-items:center;font-size:12px;letter-spacing:.15em;color:#bdcad2;pointer-events:none}#controls{position:absolute;bottom:20px;left:50%;transform:translateX(-50%);display:flex;align-items:center;gap:9px;max-width:calc(100% - 24px);padding:10px;border:1px solid #ffffff30;border-radius:14px;background:#07121cda;box-shadow:0 16px 40px #0008;backdrop-filter:blur(15px)}#controls[hidden],#loading[hidden]{display:none}button,select{font:inherit;font-size:12px;color:#e9f6ff;background:#182d39;border:1px solid #63808d55;border-radius:8px;padding:9px 12px}select{min-width:110px;max-width:42vw}button{cursor:pointer;white-space:nowrap}button:disabled{opacity:.45}footer{position:absolute;bottom:8px;right:12px;color:#8b9eae;font-size:10px;pointer-events:none}@media(max-width:500px){header{padding:12px}#controls{bottom:16px}footer{display:none}}</style></head><body>
<div id="scene"></div><header><h1>${safe(title)}</h1><div id="status">Исходная 3D-сцена · без переноса игровой логики</div></header><div id="loading">ЗАГРУЗКА ОРИГИНАЛЬНОЙ СЦЕНЫ</div><div id="controls" hidden><select id="clip" aria-label="Анимация"></select><button id="play" type="button">Пауза</button><button id="reset" type="button">Камера</button></div><footer>THREE.JS · ORIGINAL GLB · VISUAL PREVIEW</footer>
<script id="asset-glb" type="application/octet-stream">${bytes.toString('base64')}</script>${basisTags}<script id="three-license" type="text/plain">${threeLicense.replace(/<\/script/gi,'<\\/script')}</script><script>${js.replace(/<\/script/gi,'<\\/script')}</script></body></html>`;
await fs.mkdir(path.dirname(output), {recursive: true});
await fs.writeFile(output, html);
console.log(JSON.stringify({output,bytes:Buffer.byteLength(html),meshes:(gltf.meshes||[]).length,animations:(gltf.animations||[]).length,nodeCount:(gltf.nodes||[]).length,embeddedBasis:hasBasis},null,2));
