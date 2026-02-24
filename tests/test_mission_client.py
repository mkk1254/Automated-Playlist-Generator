from __future__ import annotations

from src.mission_client import MissionClient


def test_fetch_missions_parses_streams_and_aggregates(monkeypatch):
    client = MissionClient("https://example.com")

    payload = {
        "success": True,
        "data": {
            "missions": [
                {
                    "type": "streams",
                    "title": "Listen to Butter",
                    "streams_amount_with_multiplier": 3,
                },
                {
                    "type": "streams",
                    "title": "Listen to   Butter  ",
                    "streams_amount_with_multiplier": 2,
                },
                {
                    "type": "streams",
                    "title": "Listen to Dynamite",
                    "streams_amount_with_multiplier": 1,
                },
                {
                    "type": "other",
                    "title": "Ignore me",
                    "streams_amount_with_multiplier": 99,
                },
            ]
        },
    }

    monkeypatch.setattr(client, "fetch_raw_payload", lambda: payload)

    missions = client.fetch_missions()
    as_map = {m.song_title: m.stream_count for m in missions}
    assert as_map == {"Butter": 5, "Dynamite": 1}
