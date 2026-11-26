---
name: nexus-cli-anything
description: "Исполнительный слой Skill Nexus: обнаружение и запуск проверенных CLI-Anything интерфейсов для графики, музыки, Sprite Stacking, 3D и игровых сцен."
---

# CLI-Anything execution layer

Upstream: https://github.com/HKUDS/CLI-Anything/tree/34f519533bc175d2fe287ab8316b0dd99bb9cc43 (Apache-2.0).
The canonical dispatcher and registry live in https://github.com/mpaykin1/skills/tree/87824ea89087ccf5c4404bfe0b3409394eafa507/packages/skill-synergy-manager . Obtain scripts/nexus_cli.py and assets/nexus-cli-registry.json from that commit, keeping their relative paths. Never treat GitHub reads as execution. First refresh the skill inventory, preserve existing Nexus gates, then select exactly one actual project bottleneck.

1. Run `python3 scripts/nexus_cli.py inventory` in the package root. Candidate is NOT verified. Missing executable or backend means blocked, not PASS.
2. For the selected tool inspect pinned upstream <tool>/agent-harness and its SKILL.md/documentation. Install only after reviewing license, dependencies, hashes and resource costs; use an isolated venv and a disposable CPU-first worker. Install native software separately where required. No automatic unreviewed downloads, paid services, or production credentials. CLI-Hub is optional; do not use its floating registry as a lock.
3. Use `python3 scripts/nexus_cli.py help-tool blender` (substitute selected tool); then use the documented command arguments with `python3 scripts/nexus_cli.py run --workspace /absolute/disposable/job --timeout 120 blender -- ...`. The dispatcher is not a security sandbox. Only trusted commands, trusted inputs, isolated worker, no protected repository checkout, no secrets. GUI/service-only backends may be blocked on hosted runners.
4. Check real artifact output and use existing Nexus exchange protocol. Pass the same approved model/rig into Blender, RGBA slices into Sprite Stacking, GIMP only for derived texture edits; preserve original frames and alpha. Pass MusicXML/MIDI into music-skill and existing audio mastering modules. Godot export must preserve original graphics. Never substitute synthetic assets or imply tool installation from a successful help call.
5. Automation: discover current skill inventory on every invocation; choose the tool through its skill mapping, use only approved free environments, and work on one bottleneck. Existing SYMPHONIA tasks keep their assigned roles. If no runtime available, use existing verified method or mark blocked; no fake progress.
6. Promote only actual outputs through existing lab/FINISH gates, never alter meta6. Keep original files immutable. Update the registry and GitHub/ChatGPT parity only after verification.

Stages: architecture = dispatcher and registry; installation = separate pinned dependencies per worker; integration = successful real artifact chain; automation readiness = actual successful automation run. Do not conflate stages.


## RenderDoc native GPU diagnostics
Use renderdoc-gpu-bridge in Game Style Forge; registry key renderdoc; install via scripts/install_renderdoc_cli.sh. Native replay and browser performance are separate. Use compatible authorized captures; never promote merely on CLI help. Feedback to Blender, GIMP, Sprite Stacking, Godot, Three.js and existing visual guards.
