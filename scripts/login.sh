#!/usr/bin/env bash
# desc: run the Spotify OAuth flow and cache a token
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "$ROOT/spotifyer" login "$@"
