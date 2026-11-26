// Uses the host game's exact Three.js release and its matching Basis transcoder.
import * as THREE from 'three';
import { applyTextureRole } from './runtime_color.mjs';
import { KTX2Loader } from 'three/addons/loaders/KTX2Loader.js';

export async function loadRuntimeAtlas(manifestURL, renderer, {transcoderPath, approvedKtx2 = false} = {}) {
  const url = new URL(manifestURL, document.baseURI);
  const response = await fetch(url); if (!response.ok) throw Error('Runtime atlas manifest unavailable');
  const m = await response.json(); if (m.schema !== 'cover-pack-runtime-atlas/1') throw Error('Invalid runtime atlas');
  const png = new THREE.TextureLoader();
  const ktx = approvedKtx2 && transcoderPath ? new KTX2Loader().setTranscoderPath(transcoderPath).detectSupport(renderer) : null;
  const textures = [];
  try {
    for (const page of m.pages) {
      let texture;
      if (ktx && page.ktx2) {
        try { texture = await ktx.loadAsync(new URL(page.ktx2,url).href); }
        catch { texture = null; }
      }
      texture ??= await png.loadAsync(new URL(page.png,url).href);
      if (texture.image.width !== page.size[0] || texture.image.height !== page.size[1]) { texture.dispose(); throw Error('Atlas dimensions differ'); }
      texture.flipY = false; applyTextureRole(texture,'base-color');
      texture.minFilter = texture.magFilter = THREE.NearestFilter; texture.generateMipmaps = false;
      texture.wrapS = texture.wrapT = THREE.ClampToEdgeWrapping; texture.needsUpdate = true;
      textures.push(texture);
    }
    return {manifest:m,textures,layer(i){const x=m.layers[i];if(!x||x.layer!==i)throw Error('Invalid layer');return {texture:textures[x.page],uv:x.uvTopLeft,rect:x.rectXYWH};},dispose(){textures.forEach(t=>t.dispose());}};
  } catch (e) { textures.forEach(t=>t.dispose()); throw e; }
  finally { ktx?.dispose(); }
}
