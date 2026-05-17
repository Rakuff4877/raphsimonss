from typing import Optional

import requests

from config import LRCLIB_BASE

_HEADERS = {"User-Agent": "lyrics-agent/1.0"}
_TIMEOUT = 30


class LyricsNotFoundError(Exception):
    def __init__(self, song: str, artist: str):
        super().__init__(f"No synced lyrics found for '{song}' by {artist}")


def fetch_synced_lyrics(song: str, artist: str) -> str:
    """Return the raw LRC syncedLyrics string for a song, or raise LyricsNotFoundError."""
    lrc = _try_get(song, artist) or _try_search(song, artist)
    if not lrc:
        raise LyricsNotFoundError(song, artist)
    return lrc


def _try_get(song: str, artist: str) -> Optional[str]:
    resp = requests.get(
        f"{LRCLIB_BASE}/get",
        params={"track_name": song, "artist_name": artist},
        headers=_HEADERS,
        timeout=_TIMEOUT,
    )
    if resp.status_code == 200:
        return resp.json().get("syncedLyrics") or None
    return None


def _try_search(song: str, artist: str) -> Optional[str]:
    resp = requests.get(
        f"{LRCLIB_BASE}/search",
        params={"track_name": song, "artist_name": artist},
        headers=_HEADERS,
        timeout=_TIMEOUT,
    )
    if resp.status_code != 200:
        return None
    for item in resp.json():
        lrc = item.get("syncedLyrics")
        if lrc:
            return lrc
    return None
