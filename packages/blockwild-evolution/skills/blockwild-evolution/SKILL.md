---
name: blockwild-evolution
description: "BLOCKWILD Evolution: improve the user-supplied compiled Unity BLOCKWILD → standalone HTML game using existing authored skills; identify bottlenecks, research compatible open-source, integrate real improvements, improve this skill's own reproducible pipeline. Sprite stacking first, original-content protection and measurable progress."
---

# BLOCKWILD EVOLUTION — адаптивный строитель игры, v0.7.0

## Триггеры
«Улучши BLOCKWILD», «продолжи перенос ZIP в HTML», «сделай максимум через sprite stacking», «найди следующий open-source для BLOCKWILD», «повышай процент», «развивай свой скилл». Используй самые свежие исходные ZIP, HTML и правки владельца. Не создавай новую игрушку с тем же названием вместо восстановления текущей.

## Миссия
Проверять реальные источники → находить главное узкое место → привлекать **наши существующие авторские скиллы** → при нехватке возможностей исследовать новый open-source → воспроизводимо интегрировать и улучшать BLOCKWILD, а затем обновлять **этот же** скилл, если новая функция помогает будущим итерациям. **Каждый вызов должен завершаться готовым применённым улучшением, если доступны исходники/инструменты**, а не рекомендацией. При блокере прямо сообщать, что именно не удалось; не имитировать внедрение.

## Источники и текущая база (перепроверять при каждом вызове)
- Вход: пользовательский `BLOCKWILD_v0.32.1_Windows(2).zip` и наиболее поздний `BLOCKWILD_v9_NATIVE_BLOCKS_STACKING_OFFLINE.html` либо более поздние файлы. Пользовательская прикреплённая версия приоритетнее любой версии GitHub.
- В Windows ZIP присутствует `BLOCKWILD/BLOCKWILD_Data/Managed/BW.Runtime.dll`. Есть Unity `resources.assets` и исходные бинарные данные мира. Не путать этот ZIP с одноимённым публичным OSS `RedLynx101/Blockwild`: они **не взаимозаменяемы**.
- В v9: 14 505 исходных участков проиндексированы; блоки доступны из встроенных данных; отрисовывается подмножество. «100% встроенных данных» ≠ «100% геймплея». C# оригинальной игры и Unity-персонажи в HTML пока не восстановлены.
- Исходное состояние измерять повторно: `python scripts/diagnose.py --zip INPUT.zip --html GAME.html --json OUT.json`. Не объявлять проценты по неоценённым компонентам.

## Основной цикл: 1 запуск = 1 устранённое узкое место
1. Найти реальные файлы и доступ к GitHub/установленным скиллам. Для каждого файла вычислить SHA256, обнаружить Unity Mono/IL2CPP, texture/model archives и сцену HTML. Никакие исходники не изменять.
2. Выполнить `scripts/diagnose.py` и `scripts/cycle.py`; учитывать реальные ошибки запуска, размер HTML, визуальную идентичность, FPS, доступность 7 регионов, NPC, коллизии, ввод ПК/телефона, офлайн-запуск и сохранения. Применять одно самое важное исправление.
3. Перед реализацией прочитать соответствующие актуальные `skills://plugins/...` через `skills__read`; не дублировать другие игровые движки, не выдумывать вызовы отсутствующих инструментов. Операционную маршрутизацию см. `assets/skill-routes.json`.
4. Если проблема превышает возможности скиллов, выполнить `scripts/oss_scout.py --diagnosis OUT.json --online --json candidates.json`; исследовать GitHub, происхождение, лицензию, устаревание, SHA, API, платформу и стоимость исполнения. Результаты непроверенной сети ≠ установленные зависимости.
5. Выбрать **одну** подходящую OSS-интеграцию: в отдельном адаптере с версией/SHA и лицензией, совместимую с текущим Three.js/WebGL2/одним RAF. Никаких скачиваний/исполнения недоверенных репозиториев только из-за их поиска. Сначала локальная изоляция и сравнение с v9.
6. Реально изменить игру: код, оригинальную геометрию, текстуры, поведение или анимацию. Не ограничиваться постановкой задач. Сохранить старый HTML; новый файл должен запускаться из `file://` без CDN, внешнего fetch и сервера, если он заявлен автономным.
7. Проверить синтаксис и запуск реальным Chromium/WebGL2, поворот телефона (390×844/844×390), движение и действия, семирегионный мир, 8 ракурсов stacked объектов, FPS/память и внешний вид. Если запуск недоступен, статус «НЕ ПРОВЕРЕНО» без PASS.
8. Если OSS исправил **повторяющийся** недостаток конвейера, добавить к этому плагину адаптер + контракт ввода/вывода + пин SHA + license + защиту идентичности + регрессионный сценарий. Обновить тот же плагин ChatGPT посредством Plugin Creator и собственный каталог `mpaykin1/skills` только после валидации; не делать копию нового скилла.
9. Предоставить **ссылку на реально созданную игру** и при запросе краткий измеренный прогресс. Не писать отчёты/тесты/handoff/evidence без просьбы.

## Распределение ответственности между авторскими скиллами
- **Godot + Unity → HTML**: AssetRipper/UnityPy → оригинальные сцены, материалы, 3D-модели, текстуры; ILSpy для **BW.Runtime.dll** → восстановление структур C# и правил игры. C# не превращается автоматически в JS; Unity Editor WebGL при полном исходном проекте, иначе явная адаптация.
- **Voxel Game Creator**: чанки, greedy meshing/RLE, оригинальная палитра материалов, генерация коллизий и стриминг. `voxel-game-creator-blockwild` относится к отдельному публичному MIT-проекту и НЕ заменяет пользовательский ZIP.
- **Sprite Stacking Grunge Horror** + **META GAME FUSION**: подлинные горизонтальные RGBA-срезы из исходных вокселей/GLB; детали архитектуры, листвы, механизмов и окружения. Коллизии, туман, вода, объёмный свет — отдельные подсистемы, не фальшивые плоские «объёмы».
- **Hero Animator / Living Image Animator**: только исходные или утверждённые персонажи, одна идентичность, независимые полноценные наборы кадров 8 направлений, idle/walk/run/jump/death/attack когда подтверждены. Отсутствующие движения не выдумывать.
- **Blender Model Animation Enhancer**: чистка/UV/rig/GLB, не менять узнаваемость или фактуру.
- **Voxel Atmosphere Engine** + **Game Style Forge**: погода, свет, тени, GPU постэффекты, биомы и атмосфера, без второго рендера/второго цикла.
- **Skill Nexus (skill-synergy-manager)**: связывает существующие навыки проверенными форматами PNG, GLB, VOX, `stack.json`, JSON scene, HTML; проверяет SHA256, права и версии без подмены.

## Процедура самоулучшения через open-source
Технические пробелы обнаруживать из свежей диагностики, отсутствующих операций в адаптерах, ошибок инсталляции и профиля кадров. Для каждого пробела генерировать англоязычный GitHub запрос **по способности**, а не по названию модного пакета. Сопоставить 2–5 кандидатов; брать только с доказанным выигрышем, актуальными исходниками, явной лицензией и стабильной интеграцией. Критерии `references/OSS_ADMISSION.md`.

**Никакого бесконтрольного self-modifying code**: автоматическая разведка и подготовка кандидатов допустима; новое исполнение / изменение зависимостей / публикация собственного скилла выполняется через проверяемый адаптер и подтверждённую задачу владельца. Не запускаться в фоне сам по себе: только в текущем чате или по специально назначенной автоматизации.

## Границы и сохранность
- `mpaykin1/meta6` только чтение. Новые игровые улучшения — отдельные версии и PR в `mpaykin1/meta6-lab`, если есть явный путь. Авторские skill-файлы — `mpaykin1/skills`. Не изменять `meta6-lab/symphonia` при работе над BLOCKWILD.
- Запрещены платные сервисы, чужие исходники без прав, GPL-перенос внутрь закрытого HTML без анализа лицензии, неавторизованные бинарные ZIP/Unity данные в публичных репозиториях.
- Один реальный герой, управляется игроком; действующие NPC, отдельная фаза каждого, без подмены фигурами и без паттернов. Мобильный UI заполняет viewport, joystick закреплён на экране.
- Только обоснованные проценты: `source files archived`, `voxel records addressable`, `assets actually extracted`, `playable logic restored`, `sprite-stacking coverage`, `browser-verified behavior` — независимые величины.

## Визуальный конвейер Sunlit Courtyard (v0.3.0)
При запросах «улучши графику под солнечную изометрическую диораму» прочитай `references/SUNLIT_SPRITE_STACKING.md`. Его исполняемые стадии: `scripts/build_sunlit_volume_sprites.py` (оригинальные послойные объёмы), `scripts/stackstrip_bridge.py` (реальный PNG slice strip interop с `danielwh2/sprite-stacking`), `templates/sunlit_courtyard.js` (сцена без внешних CDN), `scripts/assemble_sunlit_html.py` (исходный HTML + слои → новая автономная версия). **Графический стиль v12 отличается от оригинала Unity; это дополнительный режим, а не реконструкция исходных персонажей.** Не заменять встроенные исходные бинарные данные или код. Процент 18.0 относится только к расстоянию цветового распределения до предоставленного пользователем эскиза. Для следующего этапа рекомендуется оригинальная GLB/мультиракурсная авторская графика и реальная реконструкция срезов четырёх видов — пока не реализовано.


## BLOCKWILD v13 Golden Garden — deterministic source-preserving graphic upgrade
- Use `python skills/blockwild-evolution/scripts/upgrade_golden_garden.py --source BLOCKWILD_v12_SUNLIT_COURTYARD_SPRITE_STACKING_OFFLINE.html --out BLOCKWILD_v13_GOLDEN_GARDEN_STACKED_ATMOSPHERE_OFFLINE.html`. Needs only Python standard library. The original entire v12 HTML, original compressed world geometry, world switch, animations, and source sprite layers remain in the output.
- The upgrade enhances the existing **authored** Sunlit Courtyard, not restored Unity renderer. Renderer ownership unchanged: 3D source-volume RGBA baked sprite stacks are source of architecture/characters; Canvas2D renders these perspective stacks and 3D-projected walkable floor; single original RAF and inputs; no additional downloaded runtime libraries.
- Changes: deterministic fine paving grout/gold medallions and ground moss, additional existing volumetric vegetation objects, tree-cast light-shaft shadows, water-plane-clipped animated caustics, cinematic grading. All changes are in the existing art renderer, not a separate bitmap over gameplay.
- Benchmark via official BLOCKWILD Visual Benchmark LPIPS only if official model weights are actually available; otherwise use OpenCV matched-frame captures and **name the metric**. Example Chromium art-renderer results: detailed texture Laplacian variance +26.43% portrait, +22.06% landscape (mean +24.2%) against v12 at same scene/camera; Lab palette reference distance decrease +0.90% portrait only. Neither number equals objective overall graphics improvement. Browser full native 45MB startup/WebGL2 unverified, do not call full game PASS.
- Highest-impact next task is recover user-authorized original Unity texture/mesh/rig data, then Blender + Hero Animator identity-locked eight-view authored character rigs, bake true multi-pose RGBA slices, and swap into **same** display pipeline; avoid false four-view hallucinations and preserve original collision logic.


## v0.4 — 8-direction Living Garden (v14) / SciPy × original RGBA volume source
- Applied to the v13 visual mode with no changes to the complete original v13 native-world prefix: 45,164,667 pre-art characters stay byte-identical; original geometry archive, original music and world switch remain embedded. v14 is **authored alternate art**, not Unity's original character rig.
- Input/ownership: `scripts/build_sunlit_volume_sprites.py` owns base 3D voxel models; `scripts/build_blockwild_v14_actors.py` builds enhanced 3D coherent characters and foliage, rotates the **same** 3D voxel volumes using SciPy `ndimage.rotate` (BSD-3-Clause, build-time only). Output JSON is `{SPRITE_NAME:{uri,base,size,layers}}` compatible with the v12/v13 renderer and `stackstrip_bridge.py`. All 8 directions ×5 poses ×4 persistent character variants =160 actual RGBA volume-rendered poses; plus 8 source-volume architecture/vegetation sets =168. No copying or repainting user-owned original Unity models. Hero identity remains same through all views; player actions stay input-locked; NPCs independently move and gesture.
- `python scripts/build_blockwild_v14_actors.py --source-model-script scripts/build_sunlit_volume_sprites.py --out /tmp/bw14_assets.json` (requires numpy, Pillow, SciPy in isolated build Python; no runtime game dependency).
- `python scripts/upgrade_blockwild_v14.py --source BLOCKWILD_v13_GOLDEN_GARDEN_STACKED_ATMOSPHERE_OFFLINE.html --probe-in art-probe-v13.html --assets /tmp/bw14_assets.json --out BLOCKWILD_v14_EIGHT_VIEW_LIVING_GARDEN_STACKING_OFFLINE.html --probe-out art-probe-v14.html`. The probe is a small HTML with the exact same artist scene renderer; do not claim it represents original Unity or the full 47MB HTML startup.
- Upgrades: 8 physical viewing angles, full-body walk left/right gesture/jump variants from coherent 3D voxel anatomy; four persistent actor visual identities; richer tree canopy, column relief, full-screen walkable paving, garden planters and flowers. Uses the SAME existing RAF, canvas compositor and physics/controls. No new external CDN, effect compositor or second gameplay loop. The source game code/voxels remain unchanged.
- Performance: 168 image textures are decoded once; do not rebuild volumes at runtime. Mobile portrait/landscape should be checked for decoded texture budget and frame stability before claiming full release. WebGL2 native original mode has NOT been verified by the isolated art probe.
- **Measured** matched Chromium Canvas2D art-only frames: OpenCV Laplacian variance increased +53.2% portrait and +11.75% landscape (arithmetic mean +32.5% against v13). Matched reference Lab histogram Hellinger distance decreases 1.21% portrait, 0.96% landscape (mean 1.09%). These are specific bounded image metrics, NOT overall artistic quality %, not full 3D quality %, not animation smoothness and not LPIPS.
- `scripts/measure_blockwild_v14.py` accepts two exact viewport pairs and optional authorized reference. LPIPS still needs real installed official weights; no fabricated LPIPS result. An image-quality gain is not an engine-feature or original fidelity gain.
- Interop: `blender-model-animation-enhancer`/Hero Animator author identical rig + action poses as GLB; `godot-game-to-html` captures authorized Unity original; `meta-game-fusion` converts approved watertight static geometry to true volume stacks; this skill consumes identical RGBA stack-sheet/PNG + SHA and bakes 8-view renderer poses; `voxel-atmosphere-engine` controls lighting/postfx alone; `skill-synergy-manager` checks format/rights; BLOCKWILD Visual Benchmark compares matched render states. Do not claim upstream Blender or direct GLB asset extraction happened in this v14 stage.
- **Highest next graphic step**: author a complete photoreal-stylized 3D GLB hero+stone/plants in Blender (or recover source-authentic Unity assets with AssetRipper, legally), with normal/roughness/PBR maps, calibrated 3-point light and AO, bake view-consistent true RGBA slices, replace these voxel placeholders with original detailed assets. Validate 8 angles, browser screenshots and stable FPS; only then quantify artistic reference proximity.


## v0.5 — CPU PBR source-volume relight + measured style transfer

For BLOCKWILD v15 and comparable authored 3D sprite-stacking games, read `references/V15_VOLUME_RELIGHT.md`. Reuse the same single-identity eight-direction source volumes and batch-bake 3D ambient/diffuse normals with `scripts/volumetric_relight.py`. Blend source voxels back into relit sprites to preserve facial details and leaf material texture, then use `scripts/build_v15_relief_atlas.py` and `scripts/assemble_v15.py` to publish one offline HTML without touching the original source-world header or gzip chunks. Existing skills retain ownership of rig, sprite canon, visual style and benchmark; do not create a competing game loop.

Measurements must be real matched Chromium portrait/landscape frames. Reference histogram distance is not a percentage of subjective artistic quality. Do not claim full standalone native/WebGL2 validated when browser policy blocks opening 49MB source HTML. Latest tested **art-only** renderer loaded 178 RGBA sets in both orientations without JS errors; full HTML browser startup remains unverified.


## v0.6 — Royal Volume Garden: verified full runtime

Use `references/V16_MATERIAL_WORLD.md` before upgrading any newer BLOCKWILD project.
Actual generated pipelines: `build_v16_volume_props.py` creates 11 wholly source-volume authored RGBA props; `make_stone_albedo.py` samples only stones from the owner-authorized art reference, never retains the original screenshot in the skill; `assemble_v16.py` embeds this albedo and props into the preserved standalone v15 source HTML and can reproduce the exact v16 artifact. 189 RGBA sprite atlases include 160 previous identity-preserved hero/NPC pose views and 11 new object families (178→189). Single animation loop. Source game binaries remain owner-only.

Full game was actually loaded in Chromium's software 2.5D mode, with actual keyboard player movement, world-style toggle, zero JS errors and all 189 sprites ready. **Original WebGL2 3D pipeline and source chunk streaming not fully verified**. Measured matched screenshot Laplacian-variance change +29.37% averaged across portrait and landscape; this is only image detail change, not artistic improvement percent. Do not claim source Unity Mesh/Texture2D were extracted: AssetRipper and UnityPy were not available in the build environment. Next external source recovery requires both a source-rights gate and actual tool execution.


## 27.11.2026 — v0.7 Living Light Garden

New CPU-authored true occupied-volume props, silhouette-based soft sunlight shadows,
physically projected stone-paving bevels, caustic glints on world-space water,
and seven independently animated pre-existing 3D-baked butterfly sprites.
Use `references/V17_LIGHT_VOLUME.md` and scripts `build_v17_volumes.py`,
`assemble_v17.py` plus `templates/v17_sunlit_volume.js` to reproduce the v17
standalone HTML. Retain the original archived world/data, the same player ID,
all 160 character frames, one renderer and one requestAnimationFrame loop.
The authoring pipeline uses source volumes, while the sunlit display currently
renders their baked sprite projections via Canvas2D, not an authentic GPU
three-dimensional renderer. Next priority: actual AssetRipper/UnityPy Unity
models/textures when accessible; then a genuine GPU sprite-slice renderer with
normal-based lighting and captured browser comparison. Source art always wins.


## 0.8.0 — GPU source-volume bridge with normal maps

Use `references/V18_WEBGL_VOLUMES.md` for real 43-source atlas generation and 183/193 authored-view coverage. `scripts/build_v18_gpu_atlases.py` and `scripts/assemble_v18.py` are the canonical reproducible tools. Reuse the 193 existing sprite identities and 160 authored full-body poses; do not replace with procedural character impostors or claim these to be original Unity models. Exactly one art RAF, no CDN, WebGL2 `drawArraysInstanced`+depth+GLSL normals, and native Canvas2D fallback. All original chunks/audio remain byte-identical. A graphics-percentage claim requires a common camera/viewport and actual GPU WebGL2 screenshots; 94.8% counts prepared sprite types, not perceived quality. Real GPU rendering has not been verified in headless Chromium (no WebGL2 context). If hardware WebGL2 is unavailable, do not claim success and leave fallback active.
