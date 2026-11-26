# Upstream LPIPS and attribution

- Upstream: https://github.com/richzhang/PerceptualSimilarity
- PyPI: https://pypi.org/project/lpips/ (0.1.4)
- Copyright (c) 2018 Richard Zhang, Phillip Isola, Alexei A. Efros, Eli Shechtman, Oliver Wang.
- License: BSD-2-Clause, https://github.com/richzhang/PerceptualSimilarity/blob/master/LICENSE
- Usage: `import lpips; model=lpips.LPIPS(net='alex', version='0.1')`; RGB tensors shape Nx3xHxW normalized to [-1,+1]; lower is closer.
- The plugin ships only our original adapter. It does not bundle the upstream code, checkpoints, torch, torchvision or executable model weights. Upstream requires pretrained model weights and their own dependency licensing in the execution environment.
- Source metadata changes require a recheck of upstream license and code before pin updates. No automatic unreviewed installs.

## Scientific limits
LPIPS measures deep-feature perceptual **distance to supplied reference frames**, not a grounded percentage of graphics quality, audience preference, number of 3D assets recovered or animation quality. Color grading, camera offset, stochastic weather and inconsistent captured time can dominate results. Valid change percentages refer to *distance reduction* under exactly matched capture conditions.
