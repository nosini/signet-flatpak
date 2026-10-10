#!/usr/bin/env bash
# Generate offline sources using the lock file of the packaged Signet revision.
set -euo pipefail
if (( $# != 1 )); then
  echo "Usage: $0 /path/to/Signet/Cargo.lock" >&2
  exit 2
fi
lock=$(realpath "$1")
cd "$(dirname "$0")/.."
tools=$(bash scripts/builder-tools.sh)
python3 "$tools/cargo/flatpak-cargo-generator.py" "$lock" -o cargo-sources.json
