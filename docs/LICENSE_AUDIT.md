# Licensing audit and distribution boundary

## Actual evidence and conservative choice

EfficientAssetRipper root `LICENSE` is the MIT text with `Copyright (c) 2026 Nathan Shturm` at commit `32f638ecfd1b3a9a7d7fb1c21c3b3ed288d66dc4`. Full notice is retained in `docs/licenses/EfficientAssetRipper-MIT.txt`; UI workflow inspiration is acknowledged in NOTICE. MIT is GPL-compatible if its copyright/permission notices are preserved. The new GUI is authored for this project; Unreal engine code is not imported.

AssetRipper root `LICENSE.md` is GNU GPL version 3, and README line 40 says GPLv3, at commit `beeb50ee1c223e856c860caa338e5309404956a3`. Directory.Build.props names ds5678, version 2.0.0. Do not infer an “or later” permission for the main repo merely from generic boilerplate in the license template. `AssetRipper.SourceGenerated/1.4.0` restored NuGet metadata separately declares `GPL-3.0-or-later`; choosing GPLv3 is compatible with that declaration.

EfficientUnityRipper as a whole is **GPL-3.0-only**. GPL text is in LICENSE; new code contains SPDX headers. The C# backend directly links GPL AssetRipper modules. The fact that Python talks through subprocess/NDJSON does not automatically exempt the GUI or combined distribution from GPL. Applying GPLv3 conservatively to the whole application avoids relying on that unsupported exception. REA remains separate, not an integrated derivative.

## Restored dependencies and notices

`dependency-notices.json` was generated from the actual `project.assets.json` and restored NuGet `.nuspec` metadata: 41 package/version entries, including license expression/file/URL and repository metadata where supplied. File-based licenses have been copied verbatim into `docs/licenses/<package>/<version>/`. This is a real metadata inventory, not a complete legal conclusion about each dependency's binary distribution.

Examples actually restored: SourceGenerated 1.4.0 (GPL-3.0-or-later); Cpp2IL.Core/LibCpp2IL 1.0.9, CIL 1.3.2, Tpk 2.0.0, TextureDecoder 2.6.3, Crunch/UnityCrunch 1.0.3, SharpGLTF modules 1.0.2, AsmResolver 6.0.1, NAudio.Core 3.1.0 and NAudio.Vorbis 3.0.0 (MIT according to their nuspec metadata). Engine/package metadata does not grant rights to proprietary game assets.

Actual installed PySide6 6.12.0 METADATA says `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`. We use the GPLv3 option for compatibility with this GPLv3 application; a distributor must still preserve Qt/PySide notices, obtain corresponding Qt/PySide source and comply with the chosen license. Installing the meta-package also installs Qt components not used by this GUI. Do not redistribute an entire Python environment assuming one short notice covers every Qt module, Python dependency, or runtime file.

Optional FBX uses a separately installed Blender 5.1 executable (Blender's GPL program is not bundled). Conversion is not a licensing escape hatch for a combined derivative. Assimp via assimp_py 1.2.0 is an optional QA reader, not a runtime dependency of extraction. Its installed distribution includes a LICENSE file; preserve that and the Assimp notices if bundling it. .NET SDK/runtime and Python are setup dependencies, not tracked application binaries; their redistribution terms must be included if an installer later bundles them.

## Corresponding source and private repositories

Source repository contains our complete source/build/install/test scripts, GPL/MIT notices, pinned upstream identifiers and dependency inventory. Upstream checkout, tool environments and generated backend binaries are excluded from Git. No AssetRipper source modifications were made. The delivered machine has a local build; this is not a release package approved for onward binary distribution.

If conveying a backend binary (bundled or modified), meet GPL section 6 using an applicable actual delivery method: provide complete machine-readable corresponding source for that binary and all covered/generated components, necessary build/install scripts and instructions, modifications, exact upstream/dependency source versions and notices; or a valid source offer where the license permits that method. A README link to GitHub or an inaccessible private repo by itself is not a universal substitute for corresponding source. If modifying AssetRipper later, identify modifications and retain notices. Do not impose recipient restrictions inconsistent with GPL rights.

Keeping a GitHub repository private does not remove obligations when conveying copies to recipients. Local/private use differs from distribution, but privacy is not a blanket exemption. Source recipients must receive the required licensing information and rights; distributing generated binaries requires a separate complete compliance package. The app's GPL license does not license extracted game art, music, code or trademarks for redistribution.

Current Git policy: source-only public repository, explicitly authorized by the owner; no game assets, local cache, backend DLLs/executables, .NET/Python tool caches, build output, or upstream checkouts. Never upload proprietary test files as public or private source fixtures. User-authorized extraction tests stay local outside the source repo; validation reports contain status/counts only.
