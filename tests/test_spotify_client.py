from __future__ import annotations

from src.spotify_client import SpotifyClient


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def test_search_track_prefers_allowlisted_artist(monkeypatch):
    client = SpotifyClient("id", "secret", "refresh")

    def fake_api_request(method, path, **kwargs):
        assert method == "GET"
        assert path == "/v1/search"
        return FakeResponse(
            {
                "tracks": {
                    "items": [
                        {
                            "name": "Who",
                            "uri": "spotify:track:wrong",
                            "artists": [{"name": "Other Artist"}],
                        },
                        {
                            "name": "Who",
                            "uri": "spotify:track:right",
                            "artists": [{"name": "Jimin"}],
                        },
                    ]
                }
            }
        )

    monkeypatch.setattr(client, "_api_request", fake_api_request)

    uri = client.search_track_uri("Who", preferred_artists=["Jimin"])
    assert uri == "spotify:track:right"


def test_search_track_returns_none_if_no_items(monkeypatch):
    client = SpotifyClient("id", "secret", "refresh")

    monkeypatch.setattr(
        client,
        "_api_request",
        lambda method, path, **kwargs: FakeResponse({"tracks": {"items": []}}),
    )

    assert client.search_track_uri("Missing") is None


def test_search_track_does_not_fallback_outside_allowlist(monkeypatch):
    client = SpotifyClient("id", "secret", "refresh")

    monkeypatch.setattr(
        client,
        "_api_request",
        lambda method, path, **kwargs: FakeResponse(
            {
                "tracks": {
                    "items": [
                        {
                            "name": "Life Goes On",
                            "uri": "spotify:track:tribute",
                            "artists": [{"name": "Diva Warrior"}],
                        }
                    ]
                }
            }
        ),
    )

    assert client.search_track_uri("Life Goes On (BTS)", preferred_artists=["BTS"]) is None
