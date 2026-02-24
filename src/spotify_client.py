from __future__ import annotations

import base64
import re
from typing import Any

import requests


class SpotifyClientError(RuntimeError):
    pass


class SpotifyClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        redirect_uri: str | None = None,
        timeout_seconds: float = 20.0,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.redirect_uri = redirect_uri
        self.timeout_seconds = timeout_seconds
        self._access_token: str | None = None

    def refresh_access_token(self) -> str:
        creds = f"{self.client_id}:{self.client_secret}".encode("utf-8")
        encoded = base64.b64encode(creds).decode("ascii")

        headers = {
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
        }
        if self.redirect_uri:
            data["redirect_uri"] = self.redirect_uri

        response = requests.post(
            "https://accounts.spotify.com/api/token",
            headers=headers,
            data=data,
            timeout=self.timeout_seconds,
        )
        if response.status_code >= 400:
            raise SpotifyClientError(f"Spotify token refresh failed: {response.status_code} {response.text}")

        payload = response.json()
        token = payload.get("access_token")
        if not isinstance(token, str) or not token:
            raise SpotifyClientError("Spotify token response did not include access_token")

        self._access_token = token
        return token

    def _api_request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        if not self._access_token:
            self.refresh_access_token()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self._access_token}"

        response = requests.request(
            method,
            f"https://api.spotify.com{path}",
            headers=headers,
            timeout=self.timeout_seconds,
            **kwargs,
        )

        if response.status_code == 401:
            self.refresh_access_token()
            headers["Authorization"] = f"Bearer {self._access_token}"
            response = requests.request(
                method,
                f"https://api.spotify.com{path}",
                headers=headers,
                timeout=self.timeout_seconds,
                **kwargs,
            )

        if response.status_code >= 400:
            raise SpotifyClientError(f"Spotify API error {response.status_code} on {path}: {response.text}")

        return response

    def get_current_user_id(self) -> str:
        response = self._api_request("GET", "/v1/me")
        payload = response.json()
        user_id = payload.get("id")
        if not isinstance(user_id, str) or not user_id:
            raise SpotifyClientError("Could not resolve current Spotify user id")
        return user_id

    def search_track_uri(self, title: str, preferred_artists: list[str] | None = None) -> str | None:
        queries = _build_query_variants(title)

        candidates: list[dict[str, Any]] = []
        seen_uris: set[str] = set()

        for query_title in queries:
            response = self._api_request(
                "GET",
                "/v1/search",
                params={"q": f'track:"{query_title}"', "type": "track", "limit": 10},
            )
            payload = response.json()
            items = payload.get("tracks", {}).get("items", [])
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                uri = item.get("uri")
                if not isinstance(uri, str) or not uri or uri in seen_uris:
                    continue
                seen_uris.add(uri)
                candidates.append(item)

        if not candidates:
            return None

        preferred = {_normalize_artist_name(artist) for artist in (preferred_artists or []) if artist.strip()}

        # Strict mode: when allowlist is configured, only keep exact normalized artist matches.
        if preferred:
            allowed_candidates = [item for item in candidates if _has_allowed_artist(item, preferred)]
            if not allowed_candidates:
                return None
            candidates = allowed_candidates

        ranked = sorted(
            candidates,
            key=lambda item: (
                0 if _normalize_title(item.get("name", "")) == _normalize_title(title) else 1,
                -int(item.get("popularity") or 0),
            ),
        )

        uri = ranked[0].get("uri")
        return uri if isinstance(uri, str) and uri else None

    def find_playlist_id_by_name(self, user_id: str, name: str) -> str | None:
        offset = 0
        while True:
            response = self._api_request(
                "GET",
                "/v1/me/playlists",
                params={"limit": 50, "offset": offset},
            )
            payload = response.json()
            items = payload.get("items", [])
            if not isinstance(items, list):
                return None

            for item in items:
                if not isinstance(item, dict):
                    continue
                if item.get("name") == name and isinstance(item.get("id"), str):
                    owner = item.get("owner", {})
                    if isinstance(owner, dict) and owner.get("id") == user_id:
                        return item["id"]

            if not payload.get("next"):
                return None
            offset += 50

    def create_playlist(self, user_id: str, name: str, description: str, public: bool = False) -> str:
        response = self._api_request(
            "POST",
            f"/v1/users/{user_id}/playlists",
            json={
                "name": name,
                "description": description,
                "public": public,
            },
        )
        payload = response.json()
        playlist_id = payload.get("id")
        if not isinstance(playlist_id, str) or not playlist_id:
            raise SpotifyClientError("Spotify create playlist response missing playlist id")
        return playlist_id

    def replace_playlist_tracks(self, playlist_id: str, uris: list[str]) -> None:
        first_chunk = uris[:100]
        self._api_request("PUT", f"/v1/playlists/{playlist_id}/tracks", json={"uris": first_chunk})

        if len(uris) <= 100:
            return

        for i in range(100, len(uris), 100):
            chunk = uris[i : i + 100]
            self._api_request("POST", f"/v1/playlists/{playlist_id}/tracks", json={"uris": chunk})


def _normalize_artist_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.casefold())


def _normalize_title(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().casefold())


def _has_allowed_artist(item: dict[str, Any], allowed_artists: set[str]) -> bool:
    artists = item.get("artists", [])
    if not isinstance(artists, list):
        return False
    for artist in artists:
        if not isinstance(artist, dict):
            continue
        artist_name = artist.get("name")
        if isinstance(artist_name, str) and _normalize_artist_name(artist_name) in allowed_artists:
            return True
    return False


def _build_query_variants(title: str) -> list[str]:
    variants: list[str] = [title.strip()]

    # "Life Goes On (BTS)" -> also try "Life Goes On"
    stripped = re.sub(r"\s*\([^)]*\)\s*$", "", title).strip()
    if stripped and stripped not in variants:
        variants.append(stripped)

    return [variant for variant in variants if variant]
