from __future__ import annotations

import argparse
import sys

from . import __version__
from . import commands as c
from .spotify import SpmError


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="spm", description="Manage your Spotify playlists from the command line."
    )
    p.add_argument("--version", action="version", version="spm " + __version__)
    p.add_argument("--no-browser", action="store_true",
                   help="don't auto-open a browser for auth; print the URL instead")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("login", help="authenticate and cache a token").set_defaults(func=c.cmd_login)
    sub.add_parser("playlists", help="list your playlists (id, count, owner, name)"
                   ).set_defaults(func=c.cmd_playlists)

    b = sub.add_parser("build", help="build a playlist from a text list")
    b.add_argument("file", help="path to the list file")
    b.add_argument("--name", help="name for a new playlist (default: 'SPM import')")
    b.add_argument("--into", help="add to an existing playlist (name or id) instead of creating")
    b.add_argument("--replace", action="store_true",
                   help="with --into: overwrite the playlist instead of appending")
    b.add_argument("--public", action="store_true", help="make the new playlist public")
    b.add_argument("--default-mode", choices=("artist", "album", "track"), default="artist",
                   help="how to treat 'Artist - Title' lines with no prefix (default: artist)")
    b.add_argument("--artist-mode", choices=("recent-album", "top"), default="recent-album",
                   help="for artist lines: most recent album, or the artist's top tracks")
    b.add_argument("--min-tracks", type=int, default=7,
                   help="min track count for an album to count as 'full-length' (default: 7)")
    b.add_argument("--market", help="ISO country code for track availability (default: your account)")
    b.add_argument("--dry-run", action="store_true", help="resolve and report, write nothing")
    b.set_defaults(func=c.cmd_build)

    e = sub.add_parser("export", help="back up playlists to CSV/JSON")
    e.add_argument("--playlist", action="append", default=[],
                   help="name or id (repeatable); omit for all your playlists")
    e.add_argument("--out", default="backup", help="output directory (default: ./backup)")
    e.add_argument("--format", choices=("csv", "json", "both"), default="csv")
    e.set_defaults(func=c.cmd_export)

    d = sub.add_parser("dedupe", help="remove duplicate / unavailable tracks in a playlist")
    d.add_argument("playlist", help="name or id")
    d.add_argument("--by", choices=("id", "name"), default="id",
                   help="dedupe key: exact track id, or artist+title (default: id)")
    d.add_argument("--remove-unavailable", action="store_true",
                   help="also drop tracks not playable in the market")
    d.add_argument("--market", help="ISO country code (default: your account)")
    d.add_argument("--dry-run", action="store_true")
    d.set_defaults(func=c.cmd_dedupe)

    m = sub.add_parser("merge", help="merge/copy playlists into a target")
    m.add_argument("--into", required=True, help="target playlist (name or id)")
    m.add_argument("sources", nargs="+", help="one or more source playlists (name or id)")
    m.add_argument("--create", action="store_true", help="create the target if missing")
    m.add_argument("--replace", action="store_true", help="overwrite the target instead of appending")
    m.add_argument("--dedupe", action="store_true", help="drop repeats, keeping first occurrence")
    m.add_argument("--public", action="store_true", help="if creating, make it public")
    m.add_argument("--dry-run", action="store_true")
    m.set_defaults(func=c.cmd_merge)

    s = sub.add_parser("sort", help="reorder a playlist in place")
    s.add_argument("playlist", help="name or id")
    s.add_argument("--by", choices=("release-date", "artist", "album", "added-at"),
                   default="release-date")
    s.add_argument("--desc", action="store_true", help="descending order")
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(func=c.cmd_sort)

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except SpmError as ex:
        print("error: %s" % ex, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
