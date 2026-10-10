#!/usr/bin/env python3
"""Replace the pinned Git source with a local checkout for development builds."""
import argparse
from pathlib import Path

import yaml

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("source", type=Path)
parser.add_argument("output", type=Path)
args = parser.parse_args()
source = args.source.resolve(strict=True)
if not (source / "Cargo.lock").is_file():
    parser.error("source must be a Signet Linux checkout containing Cargo.lock")
root = Path(__file__).resolve().parent.parent
output = args.output.resolve()
if output.parent != root or not output.name.startswith("local-") or output.suffix != ".yml":
    parser.error("output must be a local-*.yml file beside the manifest")
manifest = yaml.safe_load((root / "eu.nosini.Signet.yml").read_text())
module = next(m for m in manifest["modules"] if m["name"] == "signet")
module["sources"][0] = {
    "type": "dir",
    "path": str(source),
    "skip": [".git", "target", ".flatpak-builder", ".cache"],
}
output.write_text(yaml.safe_dump(manifest, sort_keys=False))
