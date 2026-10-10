# EfficientUnityRipper

A Unity asset ripper for Blender, Unity, and AI-assisted scene reconstruction.

Windows desktop browser and headless reconstruction index powered by AssetRipper. It loads Unity serialized files and bundles, exports decoded properties and reference graphs, and preserves uncertainty. REA remains a separate application.

## Run on Windows

Requirements: Windows x64, Git, Python 3.10+ (verified with 3.14.2), internet for initial dependencies. Setup installs a local .NET 10 SDK and PySide6 environment. No game installation is modified.

```powershell
cd <EfficientUnityRipper source directory>
powershell -ExecutionPolicy Bypass -File .\setup.ps1
.\launch.cmd
```

After setup completes, double-click `launch.cmd`. The backend and environment in `.local` are ignored by Git. This is a runnable source MVP, not an installer or signed executable distribution. This public repository contains source and authored test fixtures; extracted game assets, local caches and Blender showcases are excluded.

1. Select a Unity data folder, serialized file, or asset bundle; click **Scan / index**. Use only inputs you are authorized to read.
2. Search/filter the browser. Select objects to inspect properties, dependencies, and provenance. Enter a field/value in the inspector search and press Enter. Double-click a dependency to navigate.
3. Open the hierarchy tab to see GameObjects and components. Collection scene evidence is recorded in the manifest; a collection with GameObjects can also be a prefab.
4. **Queue selected export** creates a new JSON package, optionally with dependencies and decoded media. **Queue collection / scene export** exports the whole collection plus reference closure. **Run / resume** executes pending jobs. Stop kills the backend; completed jobs and object checkpoints remain.
5. **Decode selected preview** supports PNG images and a rotatable wireframe for decoded GLB meshes. Serialized material/shader properties are visible; the viewer does not claim shader/render fidelity. Audio decodes to a local file; playback is not implemented.

Default index, preview, queue, and log data live in `%LOCALAPPDATA%\EfficientUnityRipper`, outside the source repository. Exports go to the selected parent in a newly named subfolder. Existing user outputs are never deleted. Input fingerprints read file contents, so scanning a large game folder can be expensive; select a representative file/bundle for a small test.

## CLI and background use

```powershell
.\.local\venv\Scripts\python.exe -m eur.cli scan "D:\AuthorizedGame\Game_Data" --output "D:\UnityIndex\game"
.\.local\venv\Scripts\python.exe -m eur.cli export "D:\UnityIndex\game\manifest.json" --id "<stable-id>" --dependencies --media --output "D:\UnityExports\object-package"
```

For a collection/scene use `--collection <collection-id>` instead of `--id`. A decoded PNG/GLB/audio failure returns exit code 2 while preserving JSON and successful files. Other errors return 1. JSON-only export needs no running engine. Media export reloads original Unity inputs if necessary, and refuses changed input fingerprints.

Exported JSON and media filenames use the decoded asset name plus a stable 12-character suffix, with Windows-invalid characters sanitized. Internal index object files retain stable hash names; manifest IDs and references do not change.

For a textured static scene suitable for Blender, use:

```powershell
.\.local\venv\Scripts\python.exe -m eur.cli export "D:\UnityIndex\game\manifest.json" --collection "<scene-collection-id>" --scene-glb --output "D:\UnityExports\scene-package"
```

This uses AssetRipper's existing scene builder to preserve static mesh hierarchy/transforms and embed basic base-color/normal textures. Add `--fbx "C:\Program Files\Blender Foundation\Blender 5.1\blender.exe"` for binary FBX with embedded textures. Custom shader behavior, skinned renderers, sprites, particles, lighting and gameplay are not reconstructed by this scene export. A scene GLB is an approximation, not a playable recovered Unity project. The option currently belongs to the CLI; the GUI's collection export retains separate asset media.

```powershell
.\background-index.ps1 -InputPath "D:\AuthorizedGame\Game_Data" -OutputDirectory "D:\UnityIndex\game"
```

This starts a hidden local process and returns its PID and progress-log path immediately. Wait for the CLI's `complete` event before referencing the finished index. No GUI or always-running server is needed afterward. To stop a known background job, stop its reported PID; rerun the same scan/output to resume valid object checkpoints. Do not run concurrent scans into the same output directory.

In a Codex chat with filesystem access, reference the generated `agent-context.md` or the index folder:

> Use `D:\UnityIndex\game\agent-context.md`. Read manifest/hierarchy/dependencies, then inspect only relevant object JSON. Preserve recovered transforms and serialized settings; identify derived, inferred, and unavailable data. Reconstruct the selected scene using the evidence; do not invent script logic or claim automatic 1:1 fidelity.

ChatGPT without access to your local filesystem cannot read a Windows path by itself. Upload a selected JSON export package there, or use a separately configured file connector. This project does not install a ChatGPT connector or MCP service.

## Optional FBX

Core indexing, manifests, GUI, PNG, and GLB do not require Blender. An optional existing Blender executable converts an actual decoded GLB into actual binary FBX:

```powershell
.\.local\venv\Scripts\python.exe -m eur.cli export "D:\UnityIndex\game\manifest.json" --id "<mesh-id>" --media --fbx "C:\Program Files\Blender Foundation\Blender 5.1\blender.exe" --output "D:\UnityExports\mesh-package"
```

This is static mesh conversion. Source rig/animation data stay in the JSON; the media exporter does not reconstruct them into FBX. AssetRipper's single-mesh GLB builder uses a default material: shader appearance and texture assignments are not recovered into that mesh export. Texture media can be exported separately, with material references preserved in JSON. FBX files are not renamed GLB files.

A separate authorized local animation experiment transferred 228 character clips into Blender and checked actual skeletal deformation: 227 showed motion, and one was a reference pose. That experiment and its game-derived showcase remain local; animated GLB/FBX export is not integrated into the shipped CLI or GUI. See [validation](docs/VALIDATION.md) for its scope and omitted animation channels.

## Tests

```powershell
.\.local\venv\Scripts\python.exe -m unittest discover -s tests -v
# Optional broader fixture, built from our authored Unity fixture scripts:
$env:EUR_BUNDLE_FIXTURE = 'D:\FixtureBundles'
.\.local\venv\Scripts\python.exe -m unittest discover -s tests -v
# Optional independent mesh validation:
.\.local\venv\Scripts\python.exe -m pip install -r requirements-qa.txt
.\.local\venv\Scripts\python.exe tools\validate_media.py 'D:\UnityExports\mesh-package\media' --report 'D:\UnityExports\validation.json'
```

The base tests generate their own binary Unity serialized fixture through AssetRipper's writer and read it back through the actual game importer. The optional bundle fixture is authored in `fixtures/unity/Assets`; copy those files to an empty scratch Unity project and run Unity 6000.3.7f1 in batch mode with `-executeMethod BuildFixture.Build`, setting `EUR_FIXTURE_OUTPUT` to a new scratch directory. The bundle fixture has authored geometry, texture pixels, animation, UI RectTransforms, terrain, physics, PCM audio, MonoBehaviour settings and ScriptableObject config. No game assets are source fixtures.

Read [architecture](docs/ARCHITECTURE.md), [manifest contract](docs/MANIFEST.md), [source audit](docs/SOURCE_AUDIT.md), [coverage/parity](docs/FEATURES.md), [limitations](docs/LIMITATIONS.md), [license obligations](docs/LICENSE_AUDIT.md), and [actual validation report](docs/VALIDATION.md).
