"""Command implementations. Each takes parsed argparse args."""
from __future__ import annotations

import csv
import json
import os
import re
from typing import Any, Dict, List

from . import spotify as sp_
from .lists import parse_list, parse_json


def _sp(args):
    return sp_.get_client(open_browser=not getattr(args, "no_browser", False))


def _slug(name: str) -> str:
    return re.sub(r"[^\w.-]+", "_", name).strip("_") or "playlist"


def _track_line(item: Dict[str, Any]) -> Dict[str, Any]:
    t = item.get("track") or {}
    alb = t.get("album") or {}
    return {
        "track": t.get("name", ""),
        "artists": ", ".join(a["name"] for a in t.get("artists", [])),
        "album": alb.get("name", ""),
        "release_date": alb.get("release_date", ""),
        "duration_ms": t.get("duration_ms", ""),
        "isrc": (t.get("external_ids") or {}).get("isrc", ""),
        "added_at": item.get("added_at", ""),
        "uri": t.get("uri", ""),
        "is_local": t.get("is_local", False),
    }


# --- info -------------------------------------------------------------------

def cmd_login(args) -> None:
    sp = _sp(args)
    me = sp.current_user()
    print("Logged in as %s (%s). Token cached at %s"
          % (me.get("display_name") or me["id"], me["id"], sp_.CACHE_PATH))


def cmd_playlists(args) -> None:
    sp = _sp(args)
    me = sp.current_user()["id"]
    for p in sp_.my_playlists(sp):
        owner = (p.get("owner") or {}).get("id", "?")
        tag = "own" if owner == me else owner
        # Spotify moved the count from `tracks.total` to `items.total` on this endpoint.
        total = ((p.get("tracks") or p.get("items") or {}) or {}).get("total", 0)
        print("%-22s  %4d  %-14s  %s" % (p.get("id", "?"), total, tag, p.get("name", "")))


# --- build ----------------------------------------------------------------

def cmd_build(args) -> None:
    if not os.path.isfile(args.file):
        raise sp_.SpmError("No such file: %s" % args.file)
    with open(args.file, "r", encoding="utf-8") as fh:
        content = fh.read()

    if args.file.endswith('.json'):
        entries = parse_json(content)
    else:
        entries = parse_list(content)
    if not entries:
        raise sp_.SpmError("No usable lines in %s" % args.file)

    sp = _sp(args)
    market = args.market or (sp.current_user().get("country") or "US")

    uris: List[str] = []
    seen = set()
    report: List[str] = []

    def push(new: List[str], label: str) -> None:
        added = 0
        for u in new:
            if u and u not in seen:
                seen.add(u)
                uris.append(u)
                added += 1
        report.append("  %-40s +%d" % (label, added))

    for e in entries:
        kind = e.kind
        if kind == "auto":
            kind = args.default_mode  # "artist" | "album" | "track"
        try:
            if kind == "track":
                u = sp_.find_track_uri(sp, e.artist, e.title)
                if u:
                    push([u], "track: %s - %s" % (e.artist, e.title))
                else:
                    report.append("  MISS track: %s - %s" % (e.artist, e.title))
            elif kind == "album":
                alb = sp_.find_album(sp, e.artist, e.title)
                if alb:
                    push(sp_.album_track_uris(sp, alb["id"]),
                         "album: %s - %s" % (e.artist, alb["name"]))
                else:
                    report.append("  MISS album: %s - %s" % (e.artist, e.title))
            else:  # artist -> most recent album (or top tracks)
                art = sp_.resolve_artist(sp, e.artist)
                if args.artist_mode == "top":
                    push(sp_.artist_top_track_uris(sp, art["id"], market),
                         "top: %s" % art["name"])
                else:
                    alb = sp_.most_recent_album(sp, art["id"], args.min_tracks, market)
                    push(sp_.album_track_uris(sp, alb["id"]),
                         "%s - %s (%s)" % (art["name"], alb["name"], alb.get("release_date")))
        except sp_.SpmError as ex:
            report.append("  ERROR %s: %s" % (e.raw, ex))

    print("\n".join(report))
    print("\n%d unique tracks resolved from %d lines." % (len(uris), len(entries)))

    if args.dry_run:
        print("(dry run — nothing written)")
        return
    if not uris:
        raise sp_.SpmError("Nothing to add; not creating a playlist.")

    if args.into:
        pl = sp_.find_playlist(sp, args.into)
        if args.replace:
            sp_.set_playlist_tracks(sp, pl["id"], uris)
            print("Replaced %s with %d tracks." % (pl["name"], len(uris)))
        else:
            n = sp_.add_tracks(sp, pl["id"], uris)
            print("Appended %d tracks to %s." % (n, pl["name"]))
    else:
        name = args.name or "SPM import"
        pl = sp_.create_playlist(sp, name, public=args.public,
                                 description="Built by spm from %s" % os.path.basename(args.file))
        sp_.set_playlist_tracks(sp, pl["id"], uris)
        print("Created %s (%s) with %d tracks:\n%s"
              % (name, "public" if args.public else "private", len(uris),
                 pl["external_urls"]["spotify"]))


# --- export -------------------------------------------------------------------

def cmd_export(args) -> None:
    sp = _sp(args)
    targets = ([sp_.find_playlist(sp, x) for x in args.playlist]
               if args.playlist else sp_.my_playlists(sp))
    os.makedirs(args.out, exist_ok=True)

    for p in targets:
        items = sp_.playlist_tracks(sp, p["id"])
        rows = [_track_line(it) for it in items]
        base = os.path.join(args.out, "%s__%s" % (_slug(p["name"]), p["id"]))
        if args.format in ("csv", "both"):
            with open(base + ".csv", "w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else
                                   ["track", "artists", "album", "release_date",
                                    "duration_ms", "isrc", "added_at", "uri", "is_local"])
                w.writeheader()
                w.writerows(rows)
        if args.format in ("json", "both"):
            with open(base + ".json", "w", encoding="utf-8") as fh:
                json.dump({"playlist": {"id": p["id"], "name": p["name"],
                                        "description": p.get("description", ""),
                                        "public": p.get("public"),
                                        "owner": p["owner"]["id"]},
                           "tracks": rows}, fh, indent=2, ensure_ascii=False)
        print("exported %-40s %4d tracks -> %s.*" % (p["name"], len(rows), base))


# --- dedupe -----------------------------------------------------------------

def cmd_dedupe(args) -> None:
    sp = _sp(args)
    pl = sp_.find_playlist(sp, args.playlist)
    items = sp_.playlist_tracks(sp, pl["id"], market=args.market)

    kept: List[str] = []
    seen = set()
    removed_dupe = removed_dead = 0

    for it in items:
        t = it["track"]
        if args.remove_unavailable and t.get("is_playable") is False:
            removed_dead += 1
            continue
        if t.get("is_local"):
            kept.append(t["uri"])  # can't re-key reliably; leave as-is
            continue
        if args.by == "name":
            key = (t["name"].strip().lower(),
                   tuple(a["name"].strip().lower() for a in t.get("artists", [])))
        else:  # "id"
            key = t["id"]
        if key in seen:
            removed_dupe += 1
            continue
        seen.add(key)
        kept.append(t["uri"])

    print("%s: %d -> %d  (dupes -%d, unavailable -%d)"
          % (pl["name"], len(items), len(kept), removed_dupe, removed_dead))
    if args.dry_run:
        print("(dry run — nothing written)")
        return
    if removed_dupe or removed_dead:
        sp_.set_playlist_tracks(sp, pl["id"], kept)
        print("done.")
    else:
        print("nothing to remove.")


# --- organize (merge / copy / sort) ---------------------------------------

def _collect(sp, names: List[str]) -> List[str]:
    uris: List[str] = []
    for n in names:
        pl = sp_.find_playlist(sp, n)
        uris.extend(it["track"]["uri"] for it in sp_.playlist_tracks(sp, pl["id"]))
    return uris


def cmd_merge(args) -> None:
    sp = _sp(args)
    src = _collect(sp, args.sources)
    if args.dedupe:
        src = list(dict.fromkeys(src))

    try:
        target = sp_.find_playlist(sp, args.into)
    except sp_.SpmError:
        if not args.create:
            raise
        target = sp_.create_playlist(sp, args.into, public=args.public,
                                     description="Merged by spm")
        print("created target playlist %s" % args.into)

    if args.dry_run:
        print("would add %d tracks to %s (%s)"
              % (len(src), target["name"], "replace" if args.replace else "append"))
        return
    if args.replace:
        sp_.set_playlist_tracks(sp, target["id"], src)
        print("replaced %s with %d tracks." % (target["name"], len(src)))
    else:
        n = sp_.add_tracks(sp, target["id"], src)
        print("appended %d tracks to %s." % (n, target["name"]))


def cmd_sort(args) -> None:
    sp = _sp(args)
    pl = sp_.find_playlist(sp, args.playlist)
    items = sp_.playlist_tracks(sp, pl["id"])

    def key(it):
        t = it["track"]
        alb = t.get("album") or {}
        if args.by == "release-date":
            return (sp_.norm_date(alb.get("release_date")), t.get("name", "").lower())
        if args.by == "added-at":
            return (it.get("added_at") or "",)
        if args.by == "album":
            return (alb.get("name", "").lower(), t.get("track_number", 0))
        # "artist"
        first = (t.get("artists") or [{"name": ""}])[0]["name"].lower()
        return (first, alb.get("name", "").lower(), t.get("track_number", 0))

    ordered = sorted(items, key=key, reverse=args.desc)
    uris = [it["track"]["uri"] for it in ordered]
    print("%s: sorting %d tracks by %s%s"
          % (pl["name"], len(uris), args.by, " desc" if args.desc else ""))
    if args.dry_run:
        for it in ordered[:20]:
            t = it["track"]
            print("  %s — %s (%s)" % (t["artists"][0]["name"], t["name"],
                                      (t.get("album") or {}).get("release_date", "?")))
        if len(ordered) > 20:
            print("  ... (%d more)" % (len(ordered) - 20))
        print("(dry run — nothing written)")
        return
    sp_.set_playlist_tracks(sp, pl["id"], uris)
    print("done.")
