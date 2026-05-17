import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

_LRC_RE = re.compile(r"^\[(\d{2}):(\d{2})\.(\d{2,3})\]\s*(.*)")


@dataclass
class LyricLine:
    start: float
    end: float
    text: str


def parse_lrc(
    lrc_string: str,
    max_duration: Optional[float] = None,
    strip_silence: bool = True,
) -> List[LyricLine]:
    """
    Parse an LRC string into a list of timed LyricLine objects.

    strip_silence: if True, subtract the first lyric's start time so lyrics
                   begin at t=0 in the video instead of after a silent intro.
    max_duration:  cap at N seconds (applied after stripping silence).
    """
    raw: List[Tuple[float, str]] = []

    for line in lrc_string.splitlines():
        m = _LRC_RE.match(line.strip())
        if not m:
            continue
        mm, ss, ms_str, text = m.group(1), m.group(2), m.group(3), m.group(4).strip()
        if not text:
            continue
        ms = int(ms_str) / (1000 if len(ms_str) == 3 else 100)
        seconds = int(mm) * 60 + int(ss) + ms
        raw.append((seconds, text))

    raw.sort(key=lambda x: x[0])

    if not raw:
        return []

    offset = raw[0][0] if strip_silence else 0.0

    lines: List[LyricLine] = []
    for i, (start, text) in enumerate(raw):
        start -= offset
        if max_duration is not None and start >= max_duration:
            break
        if i + 1 < len(raw):
            end = raw[i + 1][0] - offset - 0.1
        else:
            end = start + 3.0
        if max_duration is not None:
            end = min(end, max_duration)
        lines.append(LyricLine(start=start, end=end, text=text))

    return lines
