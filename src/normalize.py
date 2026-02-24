from __future__ import annotations

from collections import defaultdict

from .models import Mission


PREFIX = "Listen to "


def normalize_title(raw_title: str) -> str:
    title = raw_title.strip()
    if title.startswith(PREFIX):
        title = title[len(PREFIX) :].strip()
    return " ".join(title.split())


def normalize_key(title: str) -> str:
    return " ".join(title.strip().split()).casefold()


def aggregate_missions(missions: list[Mission]) -> list[Mission]:
    counts: defaultdict[str, int] = defaultdict(int)
    display: dict[str, str] = {}

    for mission in missions:
        key = normalize_key(mission.song_title)
        if not key:
            continue
        counts[key] += mission.stream_count
        display.setdefault(key, mission.song_title.strip())

    return [Mission(song_title=display[key], stream_count=count) for key, count in counts.items() if count > 0]
