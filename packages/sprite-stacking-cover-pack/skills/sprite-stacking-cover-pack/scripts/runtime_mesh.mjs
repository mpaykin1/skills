// Use the exact Three.js version of the game; only explicit reviewed hashes permit optimized models.
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';
export async function loadRuntimeMesh(manifestURL, {approvedSHA256, ktx2Loader} = {}) {
  const url = new URL(manifestURL, document.baseURI);
  const response = await fetch(url); if (!response.ok) throw Error('Missing mesh manifest');
  const m = await response.json(); if (m.schema !== 'cover-pack-runtime-mesh/1') throw Error('Invalid mesh manifest');
  const loader = new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
  if (ktx2Loader) loader.setKTX2Loader(ktx2Loader);
  async function load(record) {
    const asset = new URL(record.path, url);
    if (asset.origin !== url.origin || !asset.href.startsWith(new URL('.',url).href)) throw Error('Unsafe mesh path');
    const r=await fetch(asset); if (!r.ok) throw Error('Missing GLB');
    const bytes=await r.arrayBuffer();
    if (globalThis.crypto?.subtle) {
      const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join('');
      if (hash!==record.sha256) throw Error('GLB hash mismatch');
    } else if (record===m.candidate) throw Error('Cannot verify candidate hash');
    return loader.parseAsync(bytes,new URL('.',asset).href);
  }
  if (approvedSHA256 && approvedSHA256===m.candidate?.sha256 && MeshoptDecoder.supported) {
    try { await MeshoptDecoder.ready; return {gltf:await load(m.candidate),variant:'optimized'}; } catch { /* canonical fallback */ }
  }
  return {gltf:await load(m.source),variant:'source'};
}
