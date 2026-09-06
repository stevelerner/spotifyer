#!/usr/bin/env bash
# desc: remove duplicate/unavailable tracks  |  dedupe.sh PLAYLIST [--apply] [--by id|name] [--remove-unavailable]
#
# Default is a DRY RUN. Add --apply to rewrite the playlist.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

[[ $# -ge 1 ]] || { echo "usage: dedupe.sh PLAYLIST [--apply] [spm flags]" >&2; exit 2; }
pl="$1"; shift

args=(); apply=0
for a in "$@"; do
  if [[ "$a" == "--apply" ]]; then apply=1; else args+=("$a"); fi
done
[[ "$apply" -eq 0 ]] && args+=(--dry-run)

set -x
exec "$ROOT/spotifyer" dedupe "$pl" "${args[@]}"
