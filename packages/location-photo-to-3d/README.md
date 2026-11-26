# ЛОКАЦИЯ v0.4.0

Одна фотография → MoGe-2 ViT-S + Depth Anything V2 Small + MobileSAM ViT-T + OpenCV 4 → оригинальная текстура и 3D-геометрия → **автономный HTML**.

Модели поддерживают **CPU**. Первоначальная установка `bash scripts/setup_cpu.sh` (Windows: `scripts\setup_cpu.ps1`) скачивает исходники из официальных репозиториев; веса впервые скачиваются при запуске. Веса и сторонние исходники в архиве не распространяются.

Запуск:

```sh
.venv/bin/python scripts/build_location.py photo.jpg -o location.html
```

MobileSAM выделяет на изображении отдельные области объектов (не распознаёт категории «дерево», «здание» и т. д.). На границах этих областей ограничивается только добавочная коррекция Depth Anything V2, чтобы удержать MoGe-геометрию от растяжений на швах. Внутри областей уточнение глубины выполняется как прежде. Исходная текстура и топология MoGe сохраняются.

CPU оптимизация: `--segment-grid 6 --resize 448 --resolution 1 --depth-input-size 392`.
Ранее вычисленные маски: `--segment-map mask_labels.npz`.
Без MobileSAM: `--segment-mode off`.
Только MoGe: `--segment-mode off --depth-mode off`.

HTML не запрашивает сеть после сборки. Из одного фото нельзя достоверно восстановить скрытые поверхности. Детали: `skills/location/SKILL.md` и `reference/MOBILESAM.md`.

## OpenCV 4 integration (fourth upstream)

OpenCV 4 runs CPU Canny + HoughLinesP on the same input photo. Long image lines yield a per-pixel confidence raster protecting scene-structural seams from **only** the added DA-V2 displacement; MobileSAM instance boundary guards are combined through the minimum of both confidence values. MoGe vertices and textures are never replaced. The Hough stage detects visible 2D segments rather than reconstructing hidden 3D geometry.

Default: `scripts/build_location.py photo.jpg -o location.html` uses all four projects. For precomputed inputs use `--opencv-map cache/structure.npz`. For explicit off mode pass `--opencv-mode off` (and disable segmentation if no masks/photo). Tuning options: `--opencv-guard-pixels 5 --opencv-max-side 1024 --opencv-min-line-fraction .09 --opencv-max-lines 250`. All OpenCV outputs are optional preprocessed data, never bundled model weights.

OpenCV upstream: https://github.com/opencv/opencv ; Python headless wheel https://pypi.org/project/opencv-python-headless/ ; Apache-2.0 for OpenCV 4.5+. See `reference/OPENCV.md`.
