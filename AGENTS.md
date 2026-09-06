---
name: spotifyer
description: Manage Spotify playlists via the local spotifyer CLI — build playlists from a text list of bands/albums/tracks, export/back up playlists, dedupe, merge, and sort. Use whenever the task involves creating or editing the user's Spotify playlists from this project.
---

# Driving spotifyer from an agent

Single entrypoint: **`./spotifyer <command> [args]`** (run from anywhere; it cd's
into the project itself). It auto-creates `.venv` on first use and loads `.env`.

## Preflight

```bash
./spotifyer doctor      # exit 0 = credentials + token ready; non-zero = not ready
./spotifyer login       # only if doctor reports a missing token (opens a browser once)
./spotifyer commands    # machine-readable manifest of every command + args
```

## Commands

Read-only: `doctor`, `playlists`, `export`.
Mutating: `build`, `dedupe`, `merge`, `sort` — all accept `--dry-run`, which
prints a report and writes nothing. **Always dry-run first, show the user, then
re-run without `--dry-run`.**

```bash
./spotifyer playlists
./spotifyer build tracks.txt --name "New Releases" --dry-run
./spotifyer build tracks.json --name "New Releases" --dry-run
./spotifyer build tracks.txt --name "New Releases"
./spotifyer export --out backup --format both
./spotifyer dedupe "New Releases" --by name --dry-run
./spotifyer merge --into "All" "A" "B" --create --dedupe --dry-run
./spotifyer sort "New Releases" --by release-date --desc --dry-run
```

`PLAYLIST` args take a name (case-insensitive) or an id/URL. Names that match
more than one playlist error out with the ambiguous ids listed — use an id then.

## Input formats

**Text files** — one entry per line; blank lines and `#` comments ignored:
```
Radiohead                   # artist
artist: Boygenius           # same, explicit
album: Fleetwood Mac - Rumours
track: Talking Heads - Once in a Lifetime
```

**JSON files** — auto-detected by `.json` extension:
```json
{
  "tracks": [
    { "artist": "Artist Name", "title": "Song Title" },
    { "artist": "Another Artist", "title": "Another Song" }
  ]
}
```

## scripts/ wrappers

Thin, safe-by-default wrappers over the same commands. Mutating wrappers run a
**dry run unless you pass `--apply`**, and echo the underlying command (`set -x`):

```bash
scripts/playlists.sh
scripts/build.sh  bands.example.txt "New Releases"            # dry run
scripts/build.sh  bands.example.txt "New Releases" --apply    # writes
scripts/export.sh backup both
scripts/dedupe.sh "New Releases" --by name                    # dry run
scripts/dedupe.sh "New Releases" --by name --apply            # writes
scripts/merge.sh  "All" "A" "B" --create --dedupe --apply
scripts/sort.sh   "New Releases" release-date --desc --apply
```

## Output shape

- `playlists`: one playlist per line — `id  trackcount  owner  name` (space-padded).
- `build`: a `+N` line per input entry, then `N unique tracks resolved`, then the
  new playlist URL (or "appended/replaced" when `--into` was used).
- `export`: one `exported <name> <count> -> <path>.*` line per playlist; files land
  in the `--out` dir as `<slug>__<id>.csv` / `.json`.
- `dedupe` / `sort` / `merge`: a `before -> after` summary line.
- Errors print `error: <message>` to stderr and exit non-zero.

## Gotchas

- `build` list-file paths resolve relative to the project dir (or pass absolute).
- `dedupe`/`sort`/`merge --replace` rewrite the whole playlist; `added_at` resets.
  Run `export` first if the order/timestamps matter.
- Playlists you don't own: readable/exportable, not modifiable.
- Artist lines pick the newest *studio-looking* LP via a title heuristic (skips
  live/deluxe/remix/anniversary/anthology and two-year-span titles, 7–25 tracks).
  Always `--dry-run` first and show the user the picks; if one is a reissue or
  wrong record, change that line to `album: Artist - Exact Title`.
- Reads hit the live API directly for artist albums (`limit=10`) because
  spotipy's wrapper currently 400s; nothing to do, just expect paginated calls.
