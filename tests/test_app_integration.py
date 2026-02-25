from __future__ import annotations

import json

from src import app
from src.models import GenerationDiagnostics, GenerationResult, Mission


class DummyMissionClient:
    def __init__(self, base_url: str):
        self.base_url = base_url

    def fetch_missions(self):
        return [Mission("Butter", 2), Mission("Dynamite", 1)]


class DummySpotifyClient:
    def __init__(self, **kwargs):
        self.created = []
        self.replaced = []
        self.today_playlist = {"id": "playlist-existing", "description": "Auto-generated daily mission playlist mission_sig:deadbeef"}
        self.yesterday_playlist = None

    def search_track_uri(self, title, preferred_artists=None):
        return {
            "Butter": "spotify:track:butter",
            "Dynamite": "spotify:track:dynamite",
        }.get(title)

    def get_current_user_id(self):
        return "user123"

    def find_playlist_id_by_name(self, user_id, name):
        playlist = self.find_playlist_by_name(user_id, name)
        if playlist is None:
            return None
        return playlist["id"]

    def find_playlist_by_name(self, user_id, name):
        if name.endswith("2099-01-01"):
            return self.today_playlist
        if name.endswith("2098-12-31"):
            return self.yesterday_playlist
        return None

    def create_playlist(self, user_id, name, description, public=False):
        self.created.append((user_id, name, description, public))
        return "playlist-new"

    def replace_playlist_tracks(self, playlist_id, uris):
        self.replaced.append((playlist_id, uris))


def test_main_updates_existing_playlist(monkeypatch, capsys):
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "secret")
    monkeypatch.setenv("SPOTIFY_REFRESH_TOKEN", "refresh")

    monkeypatch.setattr(app, "MissionClient", DummyMissionClient)

    spotify_holder = {}

    def _spotify_factory(**kwargs):
        client = DummySpotifyClient(**kwargs)
        client.today_playlist = {"id": "playlist-existing", "description": "Auto-generated daily mission playlist mission_sig:1234"}
        client.yesterday_playlist = None
        spotify_holder["client"] = client
        return client

    monkeypatch.setattr(app, "SpotifyClient", _spotify_factory)
    monkeypatch.setattr(
        app,
        "generate_playlist_with_diagnostics",
        lambda missions, seed=None, min_fillers=2: GenerationResult(
            playlist=["Butter", "Dynamite", "Butter"],
            diagnostics=GenerationDiagnostics(False, False, False),
        ),
    )
    monkeypatch.setattr(app, "playlist_name_for_today", lambda _: "Daily Mission 2099-01-01")
    monkeypatch.setattr(app, "playlist_name_for_yesterday", lambda _: "Daily Mission 2098-12-31")

    monkeypatch.setattr("sys.argv", ["prog", "--diagnostics"])

    code = app.main()
    assert code == 0

    out, err = capsys.readouterr()
    playlist = json.loads(out)
    summary = json.loads(err)

    assert playlist == ["Butter", "Dynamite", "Butter"]
    assert summary["total_uploaded_tracks"] == 3
    assert summary["unmatched_titles"] == []

    replaced = spotify_holder["client"].replaced
    assert replaced and replaced[0][0] == "playlist-existing"
    assert replaced[0][1] == ["spotify:track:butter", "spotify:track:dynamite", "spotify:track:butter"]


def test_main_reuses_yesterday_playlist_when_mission_unchanged(monkeypatch, capsys):
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "secret")
    monkeypatch.setenv("SPOTIFY_REFRESH_TOKEN", "refresh")

    monkeypatch.setattr(app, "MissionClient", DummyMissionClient)

    spotify_holder = {}

    def _spotify_factory(**kwargs):
        client = DummySpotifyClient(**kwargs)
        client.today_playlist = None
        client.yesterday_playlist = {
            "id": "playlist-yesterday",
            "description": "Auto-generated daily mission playlist mission_sig:db6f34513ae4ca28",
        }
        spotify_holder["client"] = client
        return client

    monkeypatch.setattr(app, "SpotifyClient", _spotify_factory)
    monkeypatch.setattr(
        app,
        "generate_playlist_with_diagnostics",
        lambda missions, seed=None, min_fillers=2: GenerationResult(
            playlist=["Butter", "Dynamite", "Butter"],
            diagnostics=GenerationDiagnostics(False, False, False),
        ),
    )
    monkeypatch.setattr(app, "playlist_name_for_today", lambda _: "Daily Mission 2099-01-01")
    monkeypatch.setattr(app, "playlist_name_for_yesterday", lambda _: "Daily Mission 2098-12-31")

    monkeypatch.setattr("sys.argv", ["prog", "--diagnostics"])

    code = app.main()
    assert code == 0

    out, err = capsys.readouterr()
    playlist = json.loads(out)
    summary = json.loads(err)

    assert playlist == ["Butter", "Dynamite", "Butter"]
    assert summary["same_as_yesterday"] is True
    assert summary["playlist_reused"] is True
    assert summary["playlist_name"] == "Daily Mission 2098-12-31"

    replaced = spotify_holder["client"].replaced
    assert replaced and replaced[0][0] == "playlist-yesterday"
    assert replaced[0][1] == ["spotify:track:butter", "spotify:track:dynamite", "spotify:track:butter"]
    assert spotify_holder["client"].created == []

