# Godot Engine — официальный первоисточник и практические ограничения

- Godot engine: https://github.com/godotengine/godot
- LICENSE (MIT): https://github.com/godotengine/godot/blob/master/LICENSE.txt
- Web export: https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_web.html
- CLI exports: https://docs.godotengine.org/en/stable/tutorials/editor/command_line_tutorial.html
- Export presets: https://docs.godotengine.org/en/stable/tutorials/export/exporting_projects.html
- Third-party notices: https://docs.godotengine.org/en/stable/about/complying_with_licenses.html

Godot CLI example (Godot 4, installed Web export templates):

    godot --headless --path /path/to/project --export-release Web /path/to/output/index.html

Version matters: Godot 3 and 4 have different renderers/templates and sometimes export preset syntax. This v1 CLI is optimized for Godot 4.x GDScript; matching editor/export templates are required. Godot 4 C# Web export not generally available. GDExtension binary modules or native-only APIs may block Web export. Native Vulkan Forward+ cannot be preserved verbatim in WebGL 2; Web export usually needs the Compatibility renderer, changing graphics in some projects. Feature parity is project-dependent.

Single-file packing: HTML can embed JS/WASM/PCK and hook browser `fetch()` for virtual resource URLs. This doesn't guarantee successful boot from `file://`: service workers, COOP/COEP, WebAssembly streaming, workers, and resource resolution may fail depending on browser/runtime. Reject multithread exports by default. Never claim full compatibility without actually launching.

Godot is MIT-licensed and NOT bundled. Include Godot's MIT license notice in distributed games according to the official license compliance guide.
