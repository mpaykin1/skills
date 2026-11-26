// Match the host game's Three.js version. No automatic AgX/OCIO equivalence claim.
import * as THREE from 'three';
export function applyTextureRole(texture, role) {
  if (['base-color','emission-color'].includes(role)) texture.colorSpace=THREE.SRGBColorSpace;
  else if (['alpha','normal','roughness','metallic','ao','height','density'].includes(role)) texture.colorSpace=THREE.NoColorSpace;
  else throw Error('Unknown texture role');
  texture.needsUpdate=true; return texture;
}
export function displayCoverMaterial(texture) {
  // Already display-referred sRGB image: decode once, encode once, no tone mapping.
  applyTextureRole(texture,'base-color');
  return new THREE.MeshBasicMaterial({map:texture,transparent:true,toneMapped:false});
}
export function setCoverOutput(renderer) { renderer.outputColorSpace=THREE.SRGBColorSpace; }
// Gameplay tone mapping/exposure are authored separately and must be calibrated against
// real rendered views; do not set global toneMapping or approximate arbitrary OCIO LUTs.
