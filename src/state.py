from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


DEFAULT_STATE_PATH = Path(".cache/daily_mission_state.json")


@dataclass(frozen=True)
class PlaylistState:
    last_mission_signature: str
    playlist_id: str
    playlist_name: str
    playlist_date: str


def load_playlist_state(path: Path = DEFAULT_STATE_PATH) -> PlaylistState | None:
    if not path.exists():
        return None

    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(payload, dict):
        return None

    signature = payload.get("last_mission_signature")
    playlist_id = payload.get("playlist_id")
    playlist_name = payload.get("playlist_name")
    playlist_date = payload.get("playlist_date")

    values = (signature, playlist_id, playlist_name, playlist_date)
    if not all(isinstance(value, str) and value.strip() for value in values):
        return None

    return PlaylistState(
        last_mission_signature=signature.strip(),
        playlist_id=playlist_id.strip(),
        playlist_name=playlist_name.strip(),
        playlist_date=playlist_date.strip(),
    )


def save_playlist_state(state: PlaylistState, path: Path = DEFAULT_STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(asdict(state), handle, ensure_ascii=True, indent=2)
