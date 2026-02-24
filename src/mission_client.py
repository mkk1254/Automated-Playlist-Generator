from __future__ import annotations

import os
from typing import Any

import requests

from .models import Mission
from .normalize import aggregate_missions, normalize_title


class MissionClientError(RuntimeError):
    pass


class MissionClient:
    def __init__(self, base_url: str, timeout_seconds: float = 20.0) -> None:
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds

    def fetch_raw_payload(self) -> dict[str, Any]:
        headers: dict[str, str] = {}
        bearer_token = os.getenv("BCD_BEARER_TOKEN", "").strip()
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"

        response = requests.get(self.base_url, timeout=self.timeout_seconds, headers=headers or None)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise MissionClientError("Mission API returned non-object JSON payload")
        return payload

    def fetch_missions(self) -> list[Mission]:
        payload = self.fetch_raw_payload()

        data = payload.get("data")
        if not isinstance(data, dict):
            raise MissionClientError("Mission API payload missing object field 'data'")

        mission_items = data.get("missions")
        if not isinstance(mission_items, list):
            raise MissionClientError("Mission API payload missing list field 'data.missions'")

        parsed: list[Mission] = []
        for item in mission_items:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "streams":
                continue

            raw_title = item.get("title")
            count = item.get("streams_amount_with_multiplier")

            if not isinstance(raw_title, str) or not raw_title.strip():
                continue
            if not isinstance(count, int) or count <= 0:
                continue

            title = normalize_title(raw_title)
            if not title:
                continue

            parsed.append(Mission(song_title=title, stream_count=count))

        aggregated = aggregate_missions(parsed)
        if not aggregated:
            raise MissionClientError("No stream missions found in API response")
        return aggregated
