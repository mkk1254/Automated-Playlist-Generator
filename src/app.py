from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .config import load_artist_allowlist, load_settings
from .generator import generate_playlist_with_diagnostics, is_min_filler_feasible, is_no_adjacent_feasible
from .mission_client import MissionClient
from .spotify_client import SpotifyClient


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate and sync daily Spotify mission playlist")
    parser.add_argument("--seed", type=int, default=None, help="Seed for deterministic tie-breaking")
    parser.add_argument(
        "--allowlist-path",
        default="artist_allowlist.json",
        help="Path to title->artist allowlist JSON file",
    )
    parser.add_argument("--mission-url", default=None, help="Optional mission API URL override")
    parser.add_argument("--min-fillers", type=int, default=2, help="Minimum filler songs between repeats")
    parser.add_argument("--diagnostics", action="store_true", help="Print detailed diagnostics to stderr")
    return parser


def playlist_name_for_today(timezone_name: str) -> str:
    current_date = datetime.now(ZoneInfo(timezone_name)).date()
    return f"Daily Mission {current_date.isoformat()}"


def playlist_name_for_yesterday(timezone_name: str) -> str:
    current_date = datetime.now(ZoneInfo(timezone_name)).date()
    return f"Daily Mission {(current_date - timedelta(days=1)).isoformat()}"


def mission_signature(missions: list) -> str:
    canonical = sorted((mission.song_title, mission.stream_count) for mission in missions)
    payload = json.dumps(canonical, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _signature_from_description(description: str) -> str | None:
    marker = "mission_sig:"
    start = description.find(marker)
    if start == -1:
        return None
    token = description[start + len(marker) :].split()[0].strip()
    return token or None


def main() -> int:
    args = build_parser().parse_args()

    settings = load_settings()
    mission_url = args.mission_url or settings.mission_url
    allowlist = load_artist_allowlist(args.allowlist_path)

    mission_client = MissionClient(base_url=mission_url)
    missions = mission_client.fetch_missions()
    current_signature = mission_signature(missions)

    generation_result = generate_playlist_with_diagnostics(
        missions=missions,
        seed=args.seed,
        min_fillers=args.min_fillers,
    )
    planned_titles = generation_result.playlist

    spotify = SpotifyClient(
        client_id=settings.spotify_client_id,
        client_secret=settings.spotify_client_secret,
        refresh_token=settings.spotify_refresh_token,
        redirect_uri=settings.spotify_redirect_uri,
    )

    uri_cache: dict[str, str | None] = {}
    unmatched: set[str] = set()

    for title in sorted(set(planned_titles)):
        preferred_artists = allowlist.get(title) or allowlist.get("*")
        uri = spotify.search_track_uri(title, preferred_artists=preferred_artists)
        uri_cache[title] = uri
        if uri is None:
            unmatched.add(title)

    ordered_uris = [uri_cache[title] for title in planned_titles if uri_cache.get(title)]
    ordered_uris = [uri for uri in ordered_uris if isinstance(uri, str)]

    user_id = spotify.get_current_user_id()
    playlist_name = playlist_name_for_today(settings.timezone_name)
    yesterday_playlist_name = playlist_name_for_yesterday(settings.timezone_name)
    yesterday_playlist = spotify.find_playlist_by_name(user_id=user_id, name=yesterday_playlist_name)
    yesterday_signature = _signature_from_description(yesterday_playlist["description"]) if yesterday_playlist else None
    same_as_yesterday = yesterday_signature == current_signature

    playlist_id: str | None = None
    playlist_reused = False
    description = f"Auto-generated daily mission playlist mission_sig:{current_signature}"

    if same_as_yesterday and yesterday_playlist is not None:
        playlist_id = yesterday_playlist["id"]
        playlist_name = yesterday_playlist_name
        playlist_reused = True
    else:
        playlist_id = spotify.find_playlist_id_by_name(user_id=user_id, name=playlist_name)
        if playlist_id is None:
            playlist_id = spotify.create_playlist(user_id=user_id, name=playlist_name, description=description, public=False)

    spotify.replace_playlist_tracks(playlist_id, ordered_uris)

    print(json.dumps(planned_titles, ensure_ascii=False))

    summary = {
        "playlist_name": playlist_name,
        "total_unique_mission_titles": len(missions),
        "total_planned_plays": len(planned_titles),
        "total_uploaded_tracks": len(ordered_uris),
        "unmatched_titles": sorted(unmatched),
        "mission_signature": current_signature,
        "same_as_yesterday": same_as_yesterday,
        "playlist_reused": playlist_reused,
        "strict_no_adjacent_feasible": is_no_adjacent_feasible(missions),
        "min_fillers_requested": args.min_fillers,
        "min_fillers_feasible": is_min_filler_feasible(missions, args.min_fillers),
        "diagnostics": asdict(generation_result.diagnostics),
    }

    if args.diagnostics:
        print(json.dumps(summary, ensure_ascii=False), file=sys.stderr)
    else:
        print(
            (
                f"summary: plays={summary['total_planned_plays']} uploaded={summary['total_uploaded_tracks']} "
                f"unmatched={len(unmatched)}"
            ),
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
