// Preserve the full infinite-world check, using the current phone buttons and safe loopback origin.
// Usage and HERO_PLAYWRIGHT_MODULE/HERO_TEST_MODES match the prior test entry point.
process.env.HERO_WORLD_TRAVEL='1';
await import('./test_controls_game.mjs');
