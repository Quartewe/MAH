# MAH Development Layout

## Source and package layouts

- `assets/interface.json` is the source ProjectInterface V2 file.
- `assets/resource/` contains source resource bundles. A resource path must point to a bundle root, not directly to `pipeline/`.
- `agent/` contains the Python AgentServer and custom actions/recognitions.
- `data/` contains user-selectable automation data that is shipped with the project.
- `config/maa_option.json` is static MaaFramework configuration. `config/config.json` is runtime state and must remain local.
- `debug/` contains runtime logs, screenshots, and error artifacts and is ignored by Git.
- `install/` is generated package output. It is not a second source tree.

The source interface runs with `assets/` as its working directory. Therefore its Agent entry is `../agent/main.py`. `tools/install.py` converts that path to `./agent/main.py` when it creates the package-root layout:

```text
source:  assets/interface.json + ../agent/main.py
package: interface.json        + ./agent/main.py
```

Do not move the source resource tree to the repository root without updating the install workflow, resource paths, language paths, schema associations, and incremental package rules together.

## MaaFramework conventions

- Keep `interface_version` at `2` and validate `interface.json` against the MaaFramework schema.
- Keep the existing Pipeline syntax in a file when editing it; do not mix v1 flat nodes and v2 object nodes without a reason.
- Prefer state-driven `recognition -> action -> next` flows and explicit recovery nodes over blind delays.
- Use CustomAction or CustomRecognition only for runtime data, dynamic branching, OCR post-processing, or other logic that cannot remain a stable Pipeline graph.
- Keep the 720 short-side baseline. Current device tests use `1280x720`; do not change display settings as part of resource or layout work.
- Keep JSON formatted with four spaces and preserve the repository's existing node naming conventions.

## Verification order

1. Check JSON/schema and resource loading.
2. Check CustomAction and CustomRecognition names against Agent registrations.
3. Run non-mutating recognition probes.
4. Test task branches and recovery paths on the live device only when the side effects are authorized.

Resource loading alone is not proof that the Agent, Custom mapping, or end-to-end task flow works.
