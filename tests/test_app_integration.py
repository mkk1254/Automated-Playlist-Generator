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
        self.updated_descriptions = []
        self.playlists_by_name = {
            "Daily Mission 2099-01-01": {
                "id": "playlist-existing",
                "name": "Daily Mission 2099-01-01",
                "description": "Auto-generated daily mission playlist mission_sig:deadbeef",
            }
        }
        self.playlists_by_id = {
            playlist["id"]: playlist.copy() for playlist in self.playlists_by_name.values()
        }

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
        playlist = self.playlists_by_name.get(name)
        return playlist.copy() if playlist is not None else None

    def get_playlist(self, playlist_id):
        playlist = self.playlists_by_id.get(playlist_id)
        if playlist is None:
            raise app.SpotifyClientError(f"Playlist {playlist_id} not found")
        return playlist.copy()

    def create_playlist(self, user_id, name, description, public=False):
        playlist_id = f"created-{len(self.created) + 1}"
        self.created.append((user_id, name, description, public))
        playlist = {
            "id": playlist_id,
            "name": name,
            "description": description,
        }
        self.playlists_by_name[name] = playlist
        self.playlists_by_id[playlist_id] = playlist.copy()
        return playlist_id

    def update_playlist_description(self, playlist_id, description):
        self.updated_descriptions.append((playlist_id, description))
        playlist = self.playlists_by_id.get(playlist_id)
        if playlist is not None:
            playlist["description"] = description
            playlist_name = playlist.get("name")
            if isinstance(playlist_name, str) and playlist_name in self.playlists_by_name:
                self.playlists_by_name[playlist_name]["description"] = description

    def replace_playlist_tracks(self, playlist_id, uris):
        self.replaced.append((playlist_id, uris))


def _configure_app(monkeypatch, tmp_path, spotify_factory):
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "secret")
    monkeypatch.setenv("SPOTIFY_REFRESH_TOKEN", "refresh")
    monkeypatch.setattr(app, "MissionClient", DummyMissionClient)
    monkeypatch.setattr(app, "SpotifyClient", spotify_factory)
    monkeypatch.setattr(
        app,
        "generate_playlist_with_diagnostics",
        lambda missions, seed=None, min_fillers=2: GenerationResult(
            playlist=["Butter", "Dynamite", "Butter"],
            diagnostics=GenerationDiagnostics(False, False, False),
        ),
    )
    monkeypatch.setattr(app, "playlist_name_for_today", lambda _: "Daily Mission 2099-01-01")
    monkeypatch.setattr(app, "DEFAULT_STATE_PATH", tmp_path / "daily_mission_state.json")
    monkeypatch.setattr("sys.argv", ["prog", "--diagnostics"])


def test_main_updates_existing_playlist_and_saves_private_state(monkeypatch, tmp_path, capsys):
    spotify_holder = {}

    def _spotify_factory(**kwargs):
        client = DummySpotifyClient(**kwargs)
        spotify_holder["client"] = client
        return client

    _configure_app(monkeypatch, tmp_path, _spotify_factory)

    code = app.main()
    assert code == 0

    out, err = capsys.readouterr()
    playlist = json.loads(out)
    summary = json.loads(err)
    state = json.loads((tmp_path / "daily_mission_state.json").read_text(encoding="utf-8"))

    assert playlist == ["Butter", "Dynamite", "Butter"]
    assert summary["total_uploaded_tracks"] == 3
    assert summary["unmatched_titles"] == []
    assert summary["mission_unchanged"] is False
    assert summary["playlist_reused"] is False

    replaced = spotify_holder["client"].replaced
    assert replaced and replaced[0][0] == "playlist-existing"
    assert replaced[0][1] == ["spotify:track:butter", "spotify:track:dynamite", "spotify:track:butter"]
    assert spotify_holder["client"].updated_descriptions == [
        ("playlist-existing", "Auto-generated daily mission playlist")
    ]
    assert state["playlist_id"] == "playlist-existing"
    assert state["playlist_name"] == "Daily Mission 2099-01-01"
    assert state["last_mission_signature"] == summary["mission_signature"]


def test_main_reuses_saved_playlist_when_mission_unchanged(monkeypatch, tmp_path, capsys):
    state_path = tmp_path / "daily_mission_state.json"
    state_path.write_text(
        json.dumps(
            {
                "last_mission_signature": "db6f34513ae4ca28",
                "playlist_id": "playlist-older",
                "playlist_name": "Daily Mission 2098-12-31",
                "playlist_date": "2098-12-31",
            }
        ),
        encoding="utf-8",
    )

    spotify_holder = {}

    def _spotify_factory(**kwargs):
        client = DummySpotifyClient(**kwargs)
        client.playlists_by_name = {}
        client.playlists_by_id = {
            "playlist-older": {
                "id": "playlist-older",
                "name": "Daily Mission 2098-12-31",
                "description": "Auto-generated daily mission playlist mission_sig:db6f34513ae4ca28",
            }
        }
        spotify_holder["client"] = client
        return client

    _configure_app(monkeypatch, tmp_path, _spotify_factory)

    code = app.main()
    assert code == 0

    out, err = capsys.readouterr()
    playlist = json.loads(out)
    summary = json.loads(err)
    state = json.loads(state_path.read_text(encoding="utf-8"))

    assert playlist == ["Butter", "Dynamite", "Butter"]
    assert summary["mission_unchanged"] is True
    assert summary["same_as_yesterday"] is True
    assert summary["playlist_reused"] is True
    assert summary["playlist_name"] == "Daily Mission 2098-12-31"
    assert spotify_holder["client"].created == []
    assert spotify_holder["client"].updated_descriptions == [
        ("playlist-older", "Auto-generated daily mission playlist")
    ]

    replaced = spotify_holder["client"].replaced
    assert replaced and replaced[0][0] == "playlist-older"
    assert state["playlist_id"] == "playlist-older"
    assert state["playlist_name"] == "Daily Mission 2098-12-31"


def test_main_recovers_when_saved_playlist_was_deleted(monkeypatch, tmp_path, capsys):
    state_path = tmp_path / "daily_mission_state.json"
    state_path.write_text(
        json.dumps(
            {
                "last_mission_signature": "db6f34513ae4ca28",
                "playlist_id": "missing-playlist",
                "playlist_name": "Daily Mission 2098-12-31",
                "playlist_date": "2098-12-31",
            }
        ),
        encoding="utf-8",
    )

    spotify_holder = {}

    def _spotify_factory(**kwargs):
        client = DummySpotifyClient(**kwargs)
        client.playlists_by_name = {}
        client.playlists_by_id = {}
        spotify_holder["client"] = client
        return client

    _configure_app(monkeypatch, tmp_path, _spotify_factory)

    code = app.main()
    assert code == 0

    out, err = capsys.readouterr()
    playlist = json.loads(out)
    summary = json.loads(err)
    state = json.loads(state_path.read_text(encoding="utf-8"))

    assert playlist == ["Butter", "Dynamite", "Butter"]
    assert summary["mission_unchanged"] is False
    assert summary["playlist_reused"] is False
    assert spotify_holder["client"].created == [
        ("user123", "Daily Mission 2099-01-01", "Auto-generated daily mission playlist", True)
    ]
    assert spotify_holder["client"].updated_descriptions == []
    assert state["playlist_name"] == "Daily Mission 2099-01-01"
    assert state["playlist_id"] == "created-1"
