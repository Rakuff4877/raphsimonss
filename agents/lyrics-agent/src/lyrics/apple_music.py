import re
from typing import Optional, Tuple
from urllib.parse import urlparse, parse_qs

import requests


def resolve_apple_music_url(url: str) -> Tuple[str, str]:
    """Return (song_title, artist_name) from an Apple Music URL."""
    parsed = urlparse(url)
    if "music.apple.com" not in parsed.netloc:
        raise ValueError(f"Not an Apple Music URL: {url}")

    qs = parse_qs(parsed.query)
    track_id: Optional[str] = qs["i"][0] if "i" in qs else None
    path_id = parsed.path.rstrip("/").rsplit("/", 1)[-1]
    if not re.match(r"^\d+$", path_id):
        raise ValueError(f"Could not extract a numeric ID from URL: {url}")

    # If this is an album URL (path contains /album/) with a ?i= track, look up
    # the album and match the track by ID.  Falls back to direct track lookup.
    if "/album/" in parsed.path and track_id:
        album_id = path_id          # last path segment = album ID
        result = _lookup_track_in_album(album_id, track_id)
        if result:
            return result

    # Direct lookup of the track/song ID (works for /song/ URLs and some share links)
    lookup_id = track_id if track_id else path_id
    result = _direct_lookup(lookup_id)
    if result:
        return result

    raise ValueError(
        f"iTunes lookup found no track for URL: {url}. "
        "Make sure the link is a song link (not just an album)."
    )


def _direct_lookup(itunes_id: str) -> Optional[Tuple[str, str]]:
    data = _itunes_get(f"https://itunes.apple.com/lookup?id={itunes_id}")
    for item in data.get("results", []):
        if item.get("wrapperType") == "track" and "trackName" in item:
            return item["trackName"], item["artistName"]
    return None


def _lookup_track_in_album(album_id: str, track_id: str) -> Optional[Tuple[str, str]]:
    data = _itunes_get(
        f"https://itunes.apple.com/lookup?id={album_id}&entity=song"
    )
    target = int(track_id)
    for item in data.get("results", []):
        if item.get("trackId") == target:
            return item["trackName"], item["artistName"]
    return None


def _itunes_get(url: str) -> dict:
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return resp.json()
