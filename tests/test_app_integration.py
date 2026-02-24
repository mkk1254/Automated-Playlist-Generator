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

    def search_track_uri(self, title, preferred_artists=None):
        return {
            "Butter": "spotify:track:butter",
            "Dynamite": "spotify:track:dynamite",
        }.get(title)

    def get_current_user_id(self):
        return "user123"

    def find_playlist_id_by_name(self, user_id, name):
        return "playlist-existing"

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

