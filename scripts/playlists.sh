#!/usr/bin/env bash
# desc: list your playlists ("<id>  <count>  <owner>  <name>")
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "$ROOT/spotifyer" playlists "$@"
