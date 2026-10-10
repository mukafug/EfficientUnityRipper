# SPDX-License-Identifier: GPL-3.0-only
import argparse
import json
from pathlib import Path
import sys
from .core import Backend, Index


def main():
    parser = argparse.ArgumentParser(description="Unity source index and reconstruction manifests")
    sub = parser.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("scan")
    scan.add_argument("inputs", nargs="+")
    scan.add_argument("--output", required=True)
    scan.add_argument("--force", action="store_true")
    export = sub.add_parser("export")
    export.add_argument("manifest")
    export.add_argument("--output", required=True, help="New directory; never overwritten")
    export.add_argument("--id", action="append")
    export.add_argument("--collection")
    export.add_argument("--dependencies", action="store_true")
    export.add_argument("--media", action="store_true")
    export.add_argument("--fbx", metavar="BLENDER_EXE", help="Optional actual GLB-to-FBX conversion")
    args = parser.parse_args()
    backend = Backend(lambda event: print(json.dumps(event), flush=True))
    try:
        if args.command == "scan":
            backend.scan(args.inputs, Path(args.output), force=args.force)
        else:
            index = Index(args.manifest)
            ids = index.scene_ids(args.collection) if args.collection else (args.id or list(index.rows))
            if args.dependencies:
                ids = index.closure(ids)
            destination = index.export_json(ids, args.output)
            if args.media or args.fbx:
                media_ids = [id for id in ids if index.rows[id]["class_id"] in (28, 43, 83)]
                result = backend.media(index, media_ids, destination / "media")
                if args.fbx:
                    from .fbx import convert
                    for item in result["results"]:
                        if item.get("path", "").endswith(".glb"):
                            convert(item["path"], args.fbx)
                if result["failed"]:
                    return 2
            print(json.dumps({"kind": "complete", "operation": "package", "path": str(destination)}))
        return 0
    except Exception as error:
        print(json.dumps({"kind": "error", "message": str(error)}), file=sys.stderr)
        return 1
    finally:
        backend.close()


if __name__ == "__main__":
    sys.exit(main())
