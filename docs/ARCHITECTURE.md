# Architecture and scope

The smallest complete architecture is a Python/PySide6 desktop frontend, a Python CLI using the same core, and a small C# NDJSON subprocess linked to the real AssetRipper import/export modules. It does not scrape upstream HTML, pretend that a demo manifest is a Unity input, or assume an obsolete AssetRipper CLI contract.

```text
Authorized Unity data / serialized files / bundles
    -> Python content fingerprint
    -> C# GameStructure.Load (AssetRipper.Import)
    -> WalkRelease / WalkEditor serialized properties
    -> PPtr projection and reference resolution
    -> atomic object records + manifest
    -> Python hierarchy/dependency projections
    -> GUI / JSON-only export / coding agent files

Selected loaded objects
    -> AssetRipper MeshData + GlbMeshBuilder / TextureConverter / AudioClipDecoder
    -> derived GLB / PNG / audio
    -> optional external Blender conversion to real FBX
```

Backend commands: `ping`, `scan` (`paths`, `output`, optional `fingerprint`), and `export` (`ids`, `output`, `format`). Events: `ready`, `phase`, `log`, `progress` (completed/total), `complete`, and `error`. Stdout is reserved for NDJSON; upstream incidental text is redirected to stderr. Both streams are drained without blocking the GUI and persisted in session logs. The frontend maintains one command worker at a time. Engine loading has no fabricated percentage. Index/export progress is actual processed-object count. The backend stops on 300 seconds of output inactivity; its process is killed and checkpoints retained.

The index deliberately bypasses `ExportHandler.LoadAndProcess`: upstream processors can mutate editor format, prefab/scene definitions, controllers, lighting and assets. Our primary contract is decoded serialized evidence, not an automatically regenerated Unity project. Engine-provided injected resources remain identifiable as placeholders, never original input evidence.

Dependency extraction uses actual serialized PPtr shapes emitted by AssetRipper's walk, resolving FileID through the collection dependency table. During real Unity 6 fixture testing, upstream `FetchDependencies()` failed to finish for `NavMeshSettings`; the common projection replaces that enumeration for every object. No gameplay/naming heuristic is needed. Known unreadable targets keep their stable ID while indicating unavailable data.

Stable object IDs use SHA-256 of bundle ancestry plus serialized collection name, followed by the original signed PathID as a decimal string. IDs survive rescanning and relocation of identical inputs with identical bundle/file names. They are not promises across a Unity rebuild. Ambiguous collection namespaces abort rather than silently merge objects.

Caching is content-based and includes engine commit and backend revision. Completed manifest reuse also checks each object hash. Valid per-object checkpoints can resume an interrupted directory scan after the importer reloads inputs. File-only scan caching is deliberately disabled because upstream may resolve sidecars outside the explicitly fingerprinted file. Batch job checkpoints preserve pending/done/failed/cancelled states; interrupted media/package jobs retry into a new directory and retain earlier attempts. They do not resume the importer's in-memory parse or a half-written media file.

Inputs are read-only. Export packages require a new directory. Metadata writes are atomic; media uses exclusive file creation. Stop kills only this app's owned backend process. No proprietary inputs, caches, builds or upstream checkout are tracked. Binary distribution is a separate packaging/licensing task.
