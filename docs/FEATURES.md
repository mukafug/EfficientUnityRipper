# Feature parity and implemented coverage

This table describes the delivered MVP, not a future-feature marketing list. Upstream proof is in SOURCE_AUDIT.md.

| Area | Working implementation | Validation boundary |
| --- | --- | --- |
| Unity engine integration | Real AssetRipper GameStructure importer; native binary serialized files and UnityFS bundles | Synthetic binary + Unity 6 editor-authored bundles; real-game sample in validation report |
| Scanning/index | Content fingerprint, stable IDs, individual JSON files, manifest and source hashes | Real importer, cache corruption/rebuild tests |
| Browser/search | Type/name/collection/PathID filtering, multi-selection | GUI smoke selection and filter |
| Property inspection | Nested original-name JSON; field/value find, provenance, errors | GUI material/custom script settings |
| Dependencies | PPtr projection, FileID resolution, unresolved edges, jump navigation, closure | Synthetic + Unity bundle refs including scripts/config |
| Scene hierarchy | GameObjects/Transform/RectTransform parents, components, local fields | Parent/position/scale asserts, Unity scene/prefab fixture |
| Metadata export | Selected-object JSON and collection/scene package with closure | Actual exported package + no-overwrite test |
| Mesh | Serialized data, GLB static export, rotatable wireframe | Authored triangle/skin metadata, GLB reader and Assimp |
| Texture | Serialized settings, decoded PNG and GUI image | Pixel decode/resolution checks |
| Material/shader | Serialized parameter/texture/shader refs and buffers | Fixture material `_MainTex`, shader fields; no appearance claim |
| Rig/animation/animator | Serialized bone refs, weights/bind poses, curves/controllers/settings | Unity fixture types/fields; no animated FBX |
| MonoBehaviour / ScriptableObject | Type-tree-decoded custom settings and script metadata/refs | `moveSpeed`, `lives`, `checkpoint`, config values asserted |
| UI/light/physics/terrain/prefab | Serialized objects and referenced assets, hierarchy | Authored fixture; not reconstructed scene/render |
| Audio | Serialized settings and decoded audio file when supported | Authored PCM bundle; no playback UI |
| Queue/batch | Persistent jobs, sequential worker, retry/stop, failure preservation | Queue restart/failure tests; GUI worker execution |
| Cache/checkpoint/resume | Hash validation, atomic object checkpoints and manifest, completed-directory cache; job-boundary resume | Corrupt-object rebuild and reused checkpoints asserted |
| Progress/logs | Real import phases, actual completed/total counts, persistent NDJSON | CLI events + GUI logs; no fake import percentage |
| Error recovery | Per-object errors, raw unavailable object bytes, backend error protocol stays alive, process stop/inactivity timeout | Invalid input then ping, failed-media preservation |
| FBX | Optional actual binary FBX conversion after GLB extraction | Independent Assimp reader; static geometry only |
| Background | Hidden CLI launcher, persistent index/agent context | Background process/log + completed manifest verification |
| Licensing | GPL-3.0-only source, MIT attribution, pinned upstream/dependency metadata and notices | Source/manifest license audit; binary distribution needs separate compliance packaging |

Not implemented: automatic game reconstruction, shader/script behavior recovery, interactive scene renderer, graph canvas, native FBX animation exporter, watched rescans, network/MCP endpoint, signed installation and REA integration. These are excluded, not hidden stubs.
