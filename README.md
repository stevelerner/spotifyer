# spotifyer — Spotify playlist manager

Build playlists from a text list of bands, back playlists up, dedupe, merge, and
sort them — all from the command line. Wraps the Spotify Web API via
[spotipy](https://spotipy.readthedocs.io/).

Two layers:

- **`./spotifyer`** — master CLI. One entrypoint; manages the virtualenv and
  `.env` for you. Use this.
- **`spm`** (Python package) — the actual implementation. `./spotifyer <cmd>`
  just runs `python -m spm <cmd>` inside `.venv`.

For letting an AI agent drive it, see [`AGENTS.md`](AGENTS.md) (also exposed as a
Claude Code skill via `.claude/skills/spotifyer/`).

---

## Setup

### 1. Create a Spotify app

https://developer.spotify.com/dashboard → **Create app**.

- **Redirect URI** (Settings → Redirect URIs): add exactly
  `http://127.0.0.1:8888/callback`. Any localhost port is fine as long as it
  matches `SPOTIPY_REDIRECT_URI` in your `.env`.
- Copy the **Client ID** and **Client secret** (Settings → *View client secret*).
  Both are 32-character hex strings.

### 2. Create `.env`

```bash
cp .env.example .env
```

Then edit it:

```
SPOTIPY_CLIENT_ID=your32charhexid
SPOTIPY_CLIENT_SECRET=your32charhexsecret
SPOTIPY_REDIRECT_URI=http://127.0.0.1:8888/callback
```

The wrapper also accepts alias key names (`clientid`, `client_id`, `CLIENT_ID`,
`SPOTIFY_CLIENT_ID`, and the `*_SECRET` / `*_REDIRECT_URI` equivalents), and
defaults the redirect URI if omitted. No quotes, no trailing spaces.

### 3. Install + log in

```bash
./spotifyer setup      # create .venv, install deps (auto-runs on first use too)
./spotifyer login      # opens a browser once; caches a token in .cache-spm
./spotifyer doctor     # all-green = ready
```

`login` prints your account name and id on success. The cached token refreshes
itself; you only log in again if you delete `.cache-spm` or change scopes.

---

## Commands

Run as `./spotifyer <command> [args]`.

| Command | Mutating | What it does |
|---|---|---|
| `doctor` | no | Check credentials + token; non-zero exit if not ready. |
| `login` | no | OAuth flow; cache a refresh token. |
| `commands` | no | Machine-readable manifest of every command + args. |
| `playlists` | no | List your playlists: `id  count  owner  name`. |
| `build FILE` | **yes** | Create (or add to) a playlist from a text list. |
| `export` | no | Dump playlists to CSV/JSON in `./backup`. |
| `dedupe PLAYLIST` | **yes** | Remove duplicate (and optionally unavailable) tracks. |
| `merge --into T A B ...` | **yes** | Merge/copy playlists `A`, `B`, ... into `T`. |
| `sort PLAYLIST` | **yes** | Reorder (by release date, artist, album, or date added). |

`PLAYLIST` / `--into` / sources accept a playlist **name** (case-insensitive) or
an **id/URL**. A name matching more than one playlist errors out and lists the
ambiguous ids — use an id then.

**Every mutating command supports `--dry-run`** — it prints a report and writes
nothing. Do that first.

### build

```bash
# Each bare line -> that artist's most recent full-length album
./spotifyer build bands.txt --name "New Releases" --dry-run
./spotifyer build bands.txt --name "New Releases"

# Treat unprefixed "Artist - Title" lines as tracks instead of artists
./spotifyer build songs.txt --name "Mix" --default-mode track

# Build from a JSON file (array of track objects with artist/title fields)
./spotifyer build tracks.json --name "Mix" --dry-run

# Add into an existing playlist rather than creating one
./spotifyer build more.txt --into "New Releases"

# Each artist's top tracks instead of an album
./spotifyer build bands.txt --name "Samplers" --artist-mode top
```

**Text file formats** (blank lines and `#` comments ignored):

```
Radiohead                        # artist -> most recent full-length album
artist: Boygenius                # same, explicit
album:  Fleetwood Mac - Rumours  # the whole album
track:  Talking Heads - Once in a Lifetime
```

**JSON file format** — array of track objects:

```json
{
  "tracks": [
    { "artist": "Artist Name", "title": "Song Title" },
    { "artist": "Another Artist", "title": "Another Song" }
  ]
}
```

The file extension (`.json` vs `.txt`) determines the parser automatically.

"Most recent full-length" = newest `album`-type release that looks like a single
studio LP: at least `--min-tracks` tracks (default 7), at most 25, and whose title
has no live/deluxe/remix/anniversary/anthology marker or two-year span. It falls
back progressively (studio any-length → any album → newest EP/single) when nothing
qualifies. The heuristic is title-based, so an oddly-named studio album can still
be missed — use an explicit `album: Artist - Title` line to pin the exact record.

### export

```bash
./spotifyer export                                   # all playlists -> ./backup/*.csv
./spotifyer export --format both --out dumps
./spotifyer export --playlist "New Releases" --playlist "Road Trip"
```

Files are written as `<slug>__<playlist-id>.csv` / `.json`.

### dedupe

```bash
./spotifyer dedupe "New Releases" --dry-run
./spotifyer dedupe "New Releases" --by name --remove-unavailable
```

`--by id` (default) drops exact repeats of the same recording; `--by name` also
collapses different releases of the same title by the same artist.

### merge

```bash
# Append A and B into T (T must exist unless --create)
./spotifyer merge --into "All Punk" "Punk 2023" "Punk 2024" --dedupe --dry-run
./spotifyer merge --into "All Punk" "Punk 2023" "Punk 2024" --dedupe

# Create the target and overwrite it with the union
./spotifyer merge --into "Everything" $(./spotifyer playlists | awk '{print $1}') --create --replace
```

### sort

```bash
./spotifyer sort "New Releases" --by release-date --desc --dry-run
./spotifyer sort "Road Trip" --by artist
```

---

## scripts/

Thin, **safe-by-default** wrappers over the same commands. Mutating wrappers run
a **dry run unless you pass `--apply`**, and echo the underlying command:

```bash
scripts/playlists.sh
scripts/build.sh   bands.example.txt "New Releases"            # dry run
scripts/build.sh   bands.example.txt "New Releases" --apply    # writes
scripts/export.sh  backup both
scripts/dedupe.sh  "New Releases" --by name                    # dry run
scripts/dedupe.sh  "New Releases" --by name --apply            # writes
scripts/merge.sh   "All" "A" "B" --create --dedupe --apply
scripts/sort.sh    "New Releases" release-date --desc --apply
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `invalid_client` / `Invalid client secret` | Re-copy the secret from the dashboard (don't paste the Client ID twice); make sure ID and secret are from the **same** app; if still failing, **Rotate client secret** and paste the new one. Check for `CRLF` line endings (`file .env`) — fix with `sed -i '' 's/\r$//' .env`. |
| `INVALID_CLIENT: Invalid redirect URI` | The dashboard redirect URI must match `SPOTIPY_REDIRECT_URI` **exactly**, including the port and trailing path. |
| `Missing env vars` from `doctor` | `.env` missing or key names unrecognized. Use the canonical `SPOTIPY_*` names. |
| Browser opens but never returns | Another process is on port 8888, or you denied the auth. Kill it, change the port in both the dashboard and `.env`, retry. |
| Want to start over | `rm -f .cache-spm && ./spotifyer login` |

Quick `.env` sanity check (prints key names + value lengths only — both should be 32):

```bash
awk -F= '{print $1": "length($2)" chars"}' .env
```

---

## Notes & limits

- **dedupe / sort / `merge --replace` rewrite the whole playlist** (replace-all).
  Order is set as requested; `added_at` timestamps reset. Run `export` first if
  that matters.
- Local files in a playlist are left in place but can't be reordered reliably.
- Playlists you don't own are readable/exportable but not modifiable.
- The Spotify API paginates at 100 items; the tool batches automatically.
- Your password is never handled here — auth is Spotify's OAuth page in your
  browser. The only stored credential is the refresh token in `.cache-spm`
  (git-ignored).

## Layout

```
spotifyer            master CLI (bash)
spm/                 implementation
  cli.py             argparse
  commands.py        one function per command
  spotify.py         auth, pagination, playlist read/write, "recent album" logic
  lists.py           text and JSON parsers
scripts/*.sh         safe-by-default task wrappers
AGENTS.md            agent/skill instructions (symlinked from .claude/skills/spotifyer/SKILL.md)
.env                 your credentials (git-ignored)
.cache-spm           cached OAuth token (git-ignored)
backup/              export output (git-ignored)
playlists/           local playlists (git-ignored)
screenshots/         screenshots (git-ignored)
```
