from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    spotify_client_id: str
    spotify_client_secret: str
    spotify_refresh_token: str
    spotify_redirect_uri: str | None
    mission_url: str
    timezone_name: str


class ConfigError(ValueError):
    pass


def load_settings() -> Settings:
    _load_dotenv_if_present()

    client_id = os.getenv("SPOTIFY_CLIENT_ID", "").strip()
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET", "").strip()
    refresh_token = os.getenv("SPOTIFY_REFRESH_TOKEN", "").strip()

    missing = [
        name
        for name, value in (
            ("SPOTIFY_CLIENT_ID", client_id),
            ("SPOTIFY_CLIENT_SECRET", client_secret),
            ("SPOTIFY_REFRESH_TOKEN", refresh_token),
        )
        if not value
    ]
    if missing:
        raise ConfigError(f"Missing required environment variables: {', '.join(missing)}")

    return Settings(
        spotify_client_id=client_id,
        spotify_client_secret=client_secret,
        spotify_refresh_token=refresh_token,
        spotify_redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI", "").strip() or None,
        mission_url=os.getenv("MISSION_URL", "https://bcd-api.fly.dev/api/missions/daily-mission"),
        timezone_name=os.getenv("PLAYLIST_TIMEZONE", "America/New_York"),
    )


def _load_dotenv_if_present(dotenv_path: str = ".env") -> None:
    path = Path(dotenv_path)
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or key in os.environ:
            continue

        if len(value) >= 2 and ((value[0] == value[-1] == '"') or (value[0] == value[-1] == "'")):
            value = value[1:-1]

        os.environ[key] = value


def load_artist_allowlist(path: str) -> dict[str, list[str]]:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8-sig") as handle:
        raw = json.load(handle)
    if not isinstance(raw, dict):
        raise ConfigError("artist_allowlist.json must be an object of title -> artist list")

    parsed: dict[str, list[str]] = {}
    for title, artists in raw.items():
        if not isinstance(title, str) or not title.strip():
            raise ConfigError("Allowlist keys must be non-empty strings")
        if not isinstance(artists, list) or not all(isinstance(a, str) and a.strip() for a in artists):
            raise ConfigError(f"Allowlist value for '{title}' must be a list of non-empty strings")
        parsed[title.strip()] = [a.strip() for a in artists]
    return parsed
