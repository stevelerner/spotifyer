"""Thin helpers on top of spotipy: auth, pagination, playlist mutation, lookups."""
from __future__ import annotations

import os
import re
import sys
import time
from typing import Any, Dict, Iterable, Iterator, List, Optional

try:
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
except ImportError:  # pragma: no cover
    sys.exit("spotipy is not installed. Run: pip install -r requirements.txt")

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # dotenv is optional
    pass

SCOPES = [
    "playlist-read-private",
    "playlist-read-collaborative",
    "playlist-modify-private",
    "playlist-modify-public",
]

CACHE_PATH = os.path.join(os.getcwd(), ".cache-spm")

# Rate limiting: min 0.1s between API calls to avoid hitting Spotify's rate limits.
# Spotify's rate limits are typically 429 errors after ~150-200 req/sec per client.
_RATE_LIMIT_DELAY = 0.15


class _RateLimitedSpotify:
    """Wrapper around spotipy.Spotify that adds rate limiting to search operations."""

    def __init__(self, sp: "spotipy.Spotify"):
        self._sp = sp
        self._last_call_time = 0.0

    def _throttle(self) -> None:
        """Enforce minimum delay between API calls."""
        elapsed = time.time() - self._last_call_time
        if elapsed < _RATE_LIMIT_DELAY:
            time.sleep(_RATE_LIMIT_DELAY - elapsed)
        self._last_call_time = time.time()

    def search(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        self._throttle()
        return self._sp.search(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        """Pass through all other methods to the underlying spotipy client."""
        return getattr(self._sp, name)


class SpmError(RuntimeError):
    """User-facing error; printed without a traceback."""


def get_client(open_browser: bool = True) -> "_RateLimitedSpotify":
    missing = [
        k
        for k in ("SPOTIPY_CLIENT_ID", "SPOTIPY_CLIENT_SECRET", "SPOTIPY_REDIRECT_URI")
        if not os.environ.get(k)
    ]
    if missing:
        raise SpmError(
            "Missing env vars: %s\n"
            "Create a Spotify app at https://developer.spotify.com/dashboard, "
            "then copy .env.example to .env and fill it in." % ", ".join(missing)
        )
    auth = SpotifyOAuth(
        scope=" ".join(SCOPES),
        cache_path=CACHE_PATH,
        open_browser=open_browser,
    )
    sp = spotipy.Spotify(auth_manager=auth, retries=3, requests_timeout=30)
    return _RateLimitedSpotify(sp)


# --- pagination -----------------------------------------------------------------

def _pages(sp: "spotipy.Spotify", first: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
    page = first
    while page:
        yield page
        page = sp.next(page) if page.get("next") else None


def all_items(sp: "spotipy.Spotify", first: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for page in _pages(sp, first):
        out.extend(page.get("items", []))
    return out


def chunked(seq: List[Any], size: int) -> Iterator[List[Any]]:
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


# --- playlists ----------------------------------------------------------------

def my_playlists(sp: "spotipy.Spotify") -> List[Dict[str, Any]]:
    # Spotify occasionally returns null entries for unavailable playlists.
    return [p for p in all_items(sp, sp.current_user_playlists(limit=50)) if p and p.get("id")]


def find_playlist(sp: "spotipy.Spotify", name_or_id: str) -> Dict[str, Any]:
    """Match by exact id/uri first, then case-insensitive name. Ambiguity is an error."""
    key = name_or_id.strip()
    bare = key.split(":")[-1].split("/")[-1].split("?")[0]
    pls = my_playlists(sp)
    for p in pls:
        if p.get("id") == bare:
            return p
    matches = [p for p in pls if (p.get("name") or "").strip().lower() == key.lower()]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise SpmError(
            "Playlist name %r is ambiguous (%d matches). Use one of these ids:\n%s"
            % (key, len(matches), "\n".join("  %s  %s" % (m["id"], m["name"]) for m in matches))
        )
    raise SpmError("No playlist found matching %r. Run `spm playlists` to list them." % key)


def playlist_tracks(
    sp: "spotipy.Spotify", playlist_id: str, market: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Return raw playlist item dicts, tracks only. Normalises the track object
    onto it['track'] (newer API responses put it under it['item'])."""
    first = sp.playlist_items(
        playlist_id, limit=100, additional_types=("track",), market=market
    )
    out: List[Dict[str, Any]] = []
    for it in all_items(sp, first):
        tr = it.get("track") or it.get("item")
        if tr and tr.get("type") == "track":
            it["track"] = tr
            out.append(it)
    return out


def set_playlist_tracks(sp: "spotipy.Spotify", playlist_id: str, uris: List[str]) -> None:
    """Replace the entire contents of a playlist with `uris`, in order."""
    uris = [u for u in uris if u and not u.startswith("spotify:local:")]
    sp.playlist_replace_items(playlist_id, uris[:100])
    for batch in chunked(uris[100:], 100):
        sp.playlist_add_items(playlist_id, batch)


def add_tracks(sp: "spotipy.Spotify", playlist_id: str, uris: List[str]) -> int:
    uris = [u for u in uris if u and not u.startswith("spotify:local:")]
    for batch in chunked(uris, 100):
        sp.playlist_add_items(playlist_id, batch)
    return len(uris)


def create_playlist(
    sp: "spotipy.Spotify", name: str, public: bool = False, description: str = ""
) -> Dict[str, Any]:
    uid = sp.current_user()["id"]
    return sp.user_playlist_create(uid, name, public=public, description=description)


# --- lookups ----------------------------------------------------------------

def norm_date(release_date: Optional[str]) -> str:
    """Pad a Spotify release_date ('2019', '2019-05', '2019-05-01') to sortable YYYY-MM-DD."""
    if not release_date:
        return "0000-00-00"
    parts = release_date.split("-")
    parts += ["01"] * (3 - len(parts))
    return "-".join(p.zfill(2) for p in parts[:3])


def resolve_artist(sp: "spotipy.Spotify", name: str) -> Dict[str, Any]:
    res = sp.search(q=name, type="artist", limit=5)
    items = res.get("artists", {}).get("items", [])
    if not items:
        raise SpmError("No artist found for %r" % name)
    exact = [a for a in items if a["name"].strip().lower() == name.strip().lower()]
    return (exact or items)[0]


def artist_releases(
    sp: "spotipy.Spotify",
    artist_id: str,
    groups: str = "album,single",
    market: str = "US",
) -> List[Dict[str, Any]]:
    # Hit the endpoint directly and keep limit low: spotipy's artist_albums()
    # wrapper and any limit > 10 currently trip a spurious "Invalid limit" 400
    # against the live API. Pagination still walks the full discography.
    first = sp._get(
        "artists/%s/albums" % artist_id,
        include_groups=groups,
        market=market,
        limit=10,
    )
    albums = all_items(sp, first)
    # Dedupe reissues/market dupes by normalized title; keep the earliest pressing.
    by_name: Dict[str, Dict[str, Any]] = {}
    for a in albums:
        k = a["name"].strip().lower()
        if k not in by_name or norm_date(a["release_date"]) < norm_date(
            by_name[k]["release_date"]
        ):
            by_name[k] = a
    return sorted(by_name.values(), key=lambda a: norm_date(a["release_date"]), reverse=True)


# Non-studio editions Spotify still tags as album_type "album".
_NON_STUDIO = re.compile(
    r"\b(live|unplugged|acoustic|remix(?:es|ed)?|versions?|instrumental(?:s)?|"
    r"karaoke|commentary|demos?|rarities|b-sides|session(?:s)?|"
    r"deluxe|expanded|anniversary|remaster(?:ed)?|edition|"
    r"greatest hits|the best of|collection|anthology|compilation|"
    r"soundtrack|score|from the motion picture|mixtape)\b",
    re.I,
)


_TWO_YEARS = re.compile(r"(?:19|20)\d{2}\D+(?:19|20)\d{2}")


def _is_studio(a: Dict[str, Any]) -> bool:
    name = a.get("name", "")
    # A span of two years in the title ("OK Computer OKNOTOK 1997 2017",
    # "1979-1983") is the giveaway for an anniversary reissue / anthology.
    return not _NON_STUDIO.search(name) and not _TWO_YEARS.search(name)


def most_recent_album(
    sp: "spotipy.Spotify", artist_id: str, min_tracks: int = 7, market: str = "US"
) -> Dict[str, Any]:
    """Most recent studio full-length. Falls back progressively when none qualifies."""
    rel = artist_releases(sp, artist_id, groups="album,single", market=market)
    albums = [a for a in rel if a.get("album_type") == "album"]

    def tracks(a):
        return a.get("total_tracks", 0)

    tiers = (
        # A single studio LP: studio-titled, and not a box-set-sized track count.
        [a for a in albums if _is_studio(a) and min_tracks <= tracks(a) <= 25],
        [a for a in albums if _is_studio(a) and tracks(a) >= min_tracks],
        [a for a in albums if _is_studio(a)],
        [a for a in albums if tracks(a) >= min_tracks],
        albums,
        rel,  # last resort: newest EP / single
    )
    for tier in tiers:
        if tier:
            return tier[0]
    raise SpmError("Artist has no releases on Spotify.")


def album_track_uris(sp: "spotipy.Spotify", album_id: str) -> List[str]:
    first = sp.album_tracks(album_id, limit=50)
    return [t["uri"] for t in all_items(sp, first)]


def artist_top_track_uris(
    sp: "spotipy.Spotify", artist_id: str, market: str = "US"
) -> List[str]:
    return [t["uri"] for t in sp.artist_top_tracks(artist_id, country=market)["tracks"]]


def find_track_uri(sp: "spotipy.Spotify", artist: str, title: str) -> Optional[str]:
    q = 'artist:%s track:%s' % (artist, title)
    res = sp.search(q=q, type="track", limit=5)
    items = res.get("tracks", {}).get("items", [])
    if not items:  # loosen the query
        res = sp.search(q="%s %s" % (artist, title), type="track", limit=5)
        items = res.get("tracks", {}).get("items", [])
    return items[0]["uri"] if items else None


def find_album(sp: "spotipy.Spotify", artist: str, title: str) -> Optional[Dict[str, Any]]:
    res = sp.search(q='artist:%s album:%s' % (artist, title), type="album", limit=5)
    items = res.get("albums", {}).get("items", [])
    return items[0] if items else None
