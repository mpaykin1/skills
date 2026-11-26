# PixiJS v8.23.0 — offline sprite runtime

- Upstream MIT: https://github.com/pixijs/pixijs. Browser UMD distribution: `pixi.js@8.23.0/dist/pixi.min.js`; used as `globalThis.PIXI` from **inline** script. Pin exact version.
- The application uses `const app = new PIXI.Application(); await app.init({resizeTo:window, preference:'webgl'})`. Do not use Pixi v7 sync initialization. The `canvas` is `app.canvas`.
- Sprite images embedded as `data:image/png;base64,...` are decoded into HTMLImageElement and passed to `PIXI.Texture.from(img)`; no runtime HTTP request or relative resources.
- Frames are **separate original full images**, not image distortion. `PIXI.AnimatedSprite(frameTextures)` uses `fps/60` animation speed on the 60Hz normalized ticker. No automatic actions for sprites with only one frame.
- Sprite layer ordering uses root Container with sortableChildren, explicit zIndex by layer. One scene graph / one Pixi renderer; do not add another canvas per sprite.
- UnityPy manifest → catalog, explicitly labelled NOT reconstruction. To recover Unity layout, use original Unity project scene transforms and export metadata.
- No runtime C#/GDScript interpreter, physics, audio replacement, shader translation or fake game. Native engine WebGL stays as game. Three.js is used **only** for original 3D GLB; PixiJS is for original 2D images.
- Supported inputs: PNG, WebP, JPG and GIF first static frame; use explicit extracted frame PNGs for animation. No HTML audio is synthesized. Memory and total data-size limits apply.
