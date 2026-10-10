# Agent manifest contract (schema 1, backend revision 2)

`manifest.json` is the entry point: engine/version/commit, backend revision, timestamp, explicit inputs, SHA-256 input fingerprint and source file inventory, asset rows, collections, warnings, and limitations. Each row gives ID, type/ClassID, collection, PathID string, availability status, object file and its SHA-256. Collection origin distinguishes `serialized_input` from `engine_injected`; scene classification is derived from native level-manager evidence.

`objects/<sha256-id>.json` contains unflattened original-name serialized properties, dependency fields with exact FileID/PathID, resolved target IDs where known, provenance (engine commit, collection/bundle, version, representation class), error/limitations, and optional raw binary sidecar for unreadable/unknown objects. AssetRipper's JSON walker encodes byte arrays as base64. Nonfinite floats are preserved as strings so JSON stays valid. Custom MonoBehaviour/ScriptableObject data normally appear under `m_Structure`, when type trees or assemblies describe the layout.

Classification is deliberately scoped:

| Value | Meaning |
| --- | --- |
| recovered | Decoded serialized input fields; not original source code or verified gameplay behavior. |
| derived | Engine-injected placeholder, graph/hierarchy projection, or decoded/reformatted media. Consult provenance for which one. |
| partial | Some fields available, with missing MonoBehaviour structure or importer errors. Defaults may remain. |
| inferred | Reserved for explicitly identified future inference. This version performs none. |
| unavailable | Decode/layout/target missing or unsupported; never silently fabricated. |

Provenance and global warnings take precedence over a superficial object name. Engine-injected assets may have derived or partial status but always say they were not recovered from input. If the importer reports an error, input records are marked partial conservatively; a full serialized walk does not prove every byte is semantically correct.

`dependencies.json` provides directed source/field/target edges, retaining unresolved pointers. `hierarchy.json` resolves Transform/RectTransform owners and fathers to GameObject nodes, components, children, and original local transform/UI fields. Hierarchy is derived and does not infer world transforms or invent a scene assignment. A nonnull unresolved parent is marked unavailable, distinct from a recovered null parent.

Object IDs and top-level `path_id` are strings. Serialized property PPtr numbers can exceed JavaScript's safe integer range: use Python/arbitrary-precision JSON or the dependency records' string IDs. The authoritative pointer resolution is the recorded FileID/PathID and collection namespace, not guessed matching names.

`agent-context.md` explains where to start. Export packages contain a selected object set and its original stable IDs, plus selected dependency closure if requested. Edges outside the set are listed as missing dependencies. A collection/scene package is JSON evidence, not a `.unity` project or a playable game. `media/export-results.json` records each success or failure and a derived-media path.

Wait for a scan completion before consuming its index; atomic files do not make the entire directory a concurrent transactional database. Concurrent writers into one output are unsupported. Missing original inputs do not prevent JSON-only browse/export but do prevent re-decoding media.
