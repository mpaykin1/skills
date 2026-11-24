# Реальная интеграция трёх ZIP-библиотек — v1.4.0

В `runtime/vendor/` физически вложены **исходники**, полученные из предоставленных пользователем архивов:

- `three-bvh-csg@0.0.18` — JS исходники MIT, `vendor/three-bvh-csg/src/`.
- `three.quarks@0.18.0` вместе с его обязательным `quarks.core@0.18.0` — исходники TypeScript MIT и скомпилированный (transpiled) JS `dist/` обоих модулей. Транспиляция не гарантирует рабочую связку без движка Three.js.
- `postprocessing@6.39.6` — исходники JS Zlib, `vendor/postprocessing/src/`.

Все три библиотеки физически находятся в архиве плагина; они не просто упомянуты в npm manifest. Контрольные SHA-256 исходных ZIP записаны в `runtime/vendor-provenance.json`. Лицензии сохранены рядом с каждым пакетом. Исходные PNG и игры не изменены.

**Runtime status:** чтобы использовать их в Three.js сцене, необходимы внешние зависимости `three@0.187.0`, `three-mesh-bvh@0.9.18` и сборщик `esbuild@0.27.0`. Они отсутствовали среди пользовательских архивов; при недоступном npm нельзя утверждать, что полная сборка runtime выполнена.

Проверка локального исходного слоя без интернета: `node skills/png-living-3d-city/runtime/verify-vendor.mjs`

Полная сборка, когда npm доступен: `python skills/png-living-3d-city/runtime/install_runtime.py`. Сначала подтверждаются локальные исходники, затем npm создаёт ссылки `file:` на копии, подтягивает движок и esbuild, и генерирует единый браузерный bundle. В `package.json` зафиксированы именно локальные `file:` зависимости на три присланных пакета, а не пустые заглушки и не удалённые версии.

`advanced_effects.mjs` предоставляет `buildGothicArcade` (CSG), `installMagicDebris` (Quarks), `createCityComposer` (postprocessing), `installPremiumFoundation` (композиция). Ранее существовавший `foundation_effects.mjs` остаётся резервом на время недоступности runtime. Все эффекты должны быть встроены в готовый автономный HTML без CDN/fetch/import.
