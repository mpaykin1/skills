# BLOCKWILD v14 volume-identity interoperability

Inputs are the existing own-authored 3D numpy volumes at H=64,N=48, no Unity asset claims. Rotations use SciPy ndimage.rotate with nearest-neighbor order 0 around XZ at 45-degree increments; every rendered frame comes from one same-ID 3D volume, giving consistent hair and clothing. Pose index 0 idle, 1 and 2 reciprocal walking, 3 gesture and 4 raised locomotion frame; hero triggered only by keypress. Scene projection and sprite pivot are embedded in the JSON, not drawn from an arbitrary 2D source.

Pipeline: voxel+geometry recipes -> SciPy voxel rotation -> baked RGBA projected sprites -> full-screen authored scene in one game RAF -> Playwright Chromium / OpenCV comparison -> retained user original world archive. Use previous stackstrip bridge to exchange RGBA source slices with Sprite Stacking Grunge, but don't claim the final runtime drawImage billboard is equivalent to rotating a full 3D voxel mesh on the GPU.

Licenses: SciPy BSD-3-Clause, NumPy BSD-3-Clause, Pillow HPND; build-time independent OSS, not bundled into the game. Author code original. Before importing any independently downloaded game assets confirm owner rights. Runtime needs no third-party URLs.
