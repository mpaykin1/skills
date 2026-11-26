# XState 5.33.4: finite-state AI behavior over existing game engines

**Upstream:** https://github.com/statelyai/xstate (`xstate@5.33.4`, MIT).
Pinned to the **v5 stable tag**, not the current experimental v6 beta on the repository default branch.

## Single owner per responsibility

- **bitECS**: validated bounded `scene:enter`, `player:interact`, `dialogue:state` events. No arbitrary state machine JSON is executed.
- **XState**: finite states of two guards: `patrol`, `investigate`, `return`, `recover`. Separate `idle`, `following`, `arrived`, `blocked` states for the Recast guide.
- **YUKA**: steering along Recast waypoint routes. In XState-enabled worlds, YUKA does not own state transitions or investigation timeout; it receives XState's chosen destination.
- **Rapier**: sole authority for actual positions and collisions. Never use XState for movement or positional writes.
- **Recast**: sole navigator. XState state machines cannot skip blocked routes or bypass NavMesh.
- **Howler/Quarks/PostFX**: receive the same input-authorized ECS interaction events and observe NPC positions. They don't drive a second NPC state.
- **Ink/Rete**: supply only validated scene IDs; chapter changes trigger deterministic guard reset, not player movement.

## Integration

`src/behavior-xstate.js` contains the fixed, hand-authored state machines, and `scripts/xstate_bridge.py` creates the strict manifest for the current approved scene graph. Each guard has an actor, and the guide has a separate state actor. Re-entry on patrol endpoint alternates between patrol waypoints. Investigate expires after 7.5 simulated seconds, then returns to patrol. A blocked route temporarily enters `recover`, then retries after 1.25 simulated seconds. Timers stop during dialogue; actor state changes only through explicit allowed events. The hero has NO behavior actor.

`ecs-runtime.js` routes scene/dialogue events to the behavior actors after the visual and YUKA layers. `ai-yuka.js` delegates state transitions (not physical steering) when XState is present; older game manifests use the original YUKA behavior. The fixed-step loop remains the only movement loop, with no new requestAnimationFrame or setInterval.

`src/main.js` refuses to enable new statechart worlds when bitECS, Recast, or YUKA is unavailable. Existing worlds with no `behavior_machine` remain compatible.

`package.json` pins `xstate: 5.33.4`. The original XState runtime is an **external npm dependency, not included in this skill archive**. No dependency installation or browser visual PASS is assumed.

For generated projects:

```bash
python scripts/xstate_bridge.py audit --project /path/to/generated-game
npm install
npm run dev
```

The project's own source and third-party user art must be approved separately. Preserve the original animated-world guard and the source-hash/ScanCode rights chain.
