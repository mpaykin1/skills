# Контракты форматов

## Original source → Unity extraction
Вход: архив Unity `resources.assets`, `sharedassets*`, `*.bundle`, `*.dll` (только чтение). Выход: `assets_manifest.json` с SHA256 оригинала, авторскими Texture2D/Sprite/Mesh/AnimationClip/MonoBehaviour и исходными ссылками. Отдельная папка извлечённых оригинальных текстур/мешей только там, где владелец разрешил восстановление и распространение.

## Unity meshes / original voxels → real sprite stacks
Вход: валидные GLB/VOX с исходным material palette, transform. Выход: `stack.json` + `layers/000.png..N.png` с RGBA, +X вправо, +Y вперёд, +Z вверх, фиксированным pivot и единым размером. Разные срезы должны реально отражать сечения объёма. Не заменять skinned actors статическим коллажем.

## Game scene bridge
Согласованные атрибуты `asset_id`, `original_sha256`, `type`, `position`, `rotation`, `scale`, `collision_source`, `render_source`, `animation_clip` и `license`. Сохранение/загрузка игровых состояния и физики принадлежит единственному gameplay runtime. Визуальные sprite stacks не создают отдельные коллизии.

## Render and validation
Один RAF/WebGL2. Camera yaw все 8 направлений, pitch сверху/снизу. На iPhone адаптировать DPR и качество, не менять идентичность источника. FPS и % покрытия считать только после фактических измерений/сверки.
