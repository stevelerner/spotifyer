#!/usr/bin/env bash
# desc: build a playlist from a list file  |  build.sh LISTFILE [NAME] [--apply] [extra spm flags]
#
# Default is a DRY RUN. Add --apply to actually create/modify the playlist.
# NAME (optional 2nd positional) sets --name for a new playlist. To add into an
# existing playlist instead, pass through: build.sh list.txt --apply --into "My PL"
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

[[ $# -ge 1 ]] || { echo "usage: build.sh LISTFILE [NAME] [--apply] [spm flags]" >&2; exit 2; }
listfile="$1"; shift

name=""
if [[ $# -ge 1 && "$1" != -* ]]; then name="$1"; shift; fi

args=()
apply=0
for a in "$@"; do
  if [[ "$a" == "--apply" ]]; then apply=1; else args+=("$a"); fi
done
[[ -n "$name" ]] && args=(--name "$name" "${args[@]}")
[[ "$apply" -eq 0 ]] && args+=(--dry-run)

set -x
exec "$ROOT/spotifyer" build "$listfile" "${args[@]}"
