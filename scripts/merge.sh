#!/usr/bin/env bash
# desc: merge playlists into a target  |  merge.sh TARGET SRC [SRC...] [--apply] [--create] [--replace] [--dedupe]
#
# Default is a DRY RUN. Add --apply to write. --create makes TARGET if missing.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

[[ $# -ge 2 ]] || { echo "usage: merge.sh TARGET SRC [SRC...] [--apply] [spm flags]" >&2; exit 2; }
target="$1"; shift

sources=(); flags=(); apply=0
for a in "$@"; do
  case "$a" in
    --apply) apply=1 ;;
    --*)     flags+=("$a") ;;
    *)       sources+=("$a") ;;
  esac
done
[[ ${#sources[@]} -ge 1 ]] || { echo "merge.sh: need at least one source playlist" >&2; exit 2; }
[[ "$apply" -eq 0 ]] && flags+=(--dry-run)

set -x
exec "$ROOT/spotifyer" merge --into "$target" "${sources[@]}" "${flags[@]}"
