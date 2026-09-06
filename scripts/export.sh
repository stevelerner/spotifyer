#!/usr/bin/env bash
# desc: back up playlists to CSV/JSON  |  export.sh [OUTDIR] [FORMAT] [--playlist NAME]...
#
# OUTDIR  default: backup
# FORMAT  csv (default) | json | both
# Read-only; no --apply needed. Extra --playlist flags are passed through.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

out="backup"; fmt="csv"; passthru=()
if [[ $# -ge 1 && "$1" != -* ]]; then out="$1"; shift; fi
if [[ $# -ge 1 && "$1" != -* ]]; then fmt="$1"; shift; fi
passthru=("$@")

set -x
exec "$ROOT/spotifyer" export --out "$out" --format "$fmt" "${passthru[@]}"
