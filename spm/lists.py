"""Parse a plain-text or JSON input list into typed entries.

Text line formats (blank lines and lines starting with '#' are ignored):

    Radiohead                     -> artist   (bare line)
    artist: Radiohead             -> artist
    album: Radiohead - In Rainbows-> album
    track: Radiohead - Karma Police -> track

A bare "Artist - Something" line is treated according to --default-mode
(handled by the caller), so it is emitted here as kind "auto".

JSON format: array of track objects with "artist" and "title" fields.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List


@dataclass
class Entry:
    kind: str  # "artist" | "album" | "track" | "auto"
    artist: str
    title: str = ""
    raw: str = ""


def parse_list(text: str) -> List[Entry]:
    entries: List[Entry] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        kind = "auto"
        body = line
        low = line.lower()
        for prefix, k in (("artist:", "artist"), ("album:", "album"), ("track:", "track")):
            if low.startswith(prefix):
                kind, body = k, line[len(prefix) :].strip()
                break

        artist, title = body, ""
        for sep in (" - ", " – ", " — ", " -- ", "\t", " | "):
            if sep in body:
                artist, title = (s.strip() for s in body.split(sep, 1))
                break

        if kind == "auto" and not title:
            kind = "artist"

        entries.append(Entry(kind=kind, artist=artist, title=title, raw=line))
    return entries


def parse_json(data: str) -> List[Entry]:
    """Parse JSON array of track objects into entries."""
    entries: List[Entry] = []
    try:
        obj = json.loads(data)
        tracks = obj.get("tracks", obj) if isinstance(obj, dict) else obj
        if not isinstance(tracks, list):
            raise ValueError("Expected array of tracks or object with 'tracks' key")

        for track in tracks:
            if isinstance(track, dict):
                artist = track.get("artist", "").strip()
                title = track.get("title", "").strip()
                if artist:
                    entries.append(Entry(kind="track", artist=artist, title=title,
                                       raw=f"{artist} - {title}"))
    except (json.JSONDecodeError, ValueError) as e:
        raise ValueError(f"Invalid JSON format: {e}")
    return entries
