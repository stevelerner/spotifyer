#!/usr/bin/env bash
# desc: reorder a playlist in place  |  sort.sh PLAYLIST [BY] [--apply] [--desc]
#
# BY  release-date (default) | artist | album | added-at
# Default is a DRY RUN. Add --apply to rewrite the playlist order.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

[[ $# -ge 1 ]] || { echo "usage: sort.sh PLAYLIST [BY] [--apply] [--desc]" >&2; exit 2; }
pl="$1"; shift

by="release-date"
if [[ $# -ge 1 && "$1" != -* ]]; then by="$1"; shift; fi

args=(--by "$by"); apply=0
for a in "$@"; do
  if [[ "$a" == "--apply" ]]; then apply=1; else args+=("$a"); fi
done
[[ "$apply" -eq 0 ]] && args+=(--dry-run)

set -x
exec "$ROOT/spotifyer" sort "$pl" "${args[@]}"
