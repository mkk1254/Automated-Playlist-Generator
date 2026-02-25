# Daily Mission Spotify Playlist Generator

Automates your daily mission pipeline:

1. Fetches mission songs from `https://bcd-api.fly.dev/api/missions/daily-mission`
2. Generates a natural playlist order with mission counts
3. Resolves tracks on Spotify (title + optional artist allowlist)
4. Creates or updates a private playlist named `Daily Mission YYYY-MM-DD`
5. Reuses yesterday's playlist when today's mission payload is unchanged

## Setup

1. Create and activate a Python 3.11+ environment.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set environment variables:
   - `SPOTIFY_CLIENT_ID`
   - `SPOTIFY_CLIENT_SECRET`
   - `SPOTIFY_REFRESH_TOKEN`
   - Optional: `SPOTIFY_REDIRECT_URI`
   - Optional: `MISSION_URL` (defaults to daily mission endpoint)
   - Optional: `PLAYLIST_TIMEZONE` (defaults to `America/New_York`)

## Artist allowlist

Edit `artist_allowlist.json`:

```json
{
  "Who": ["Jimin"],
  "Life Goes On (BTS)": ["BTS"]
}
```

## Run locally

```bash
python -m src.app --diagnostics
```

Optional flags:
- `--seed 42`
- `--allowlist-path artist_allowlist.json`
- `--mission-url https://bcd-api.fly.dev/api/missions/daily-mission`

## Output behavior

- `stdout`: JSON array of ordered mission titles
- `stderr`: summary report (or full diagnostics with `--diagnostics`)
- Unmatched songs are skipped for Spotify upload and listed in report

## Tests

```bash
pytest -q
```

## GitHub Actions

Workflow is at `.github/workflows/daily_playlist.yml`.
Scheduled at `00:30 UTC` (`6:00 AM IST`).
Set repository secrets:
- `SPOTIFY_CLIENT_ID`
- `SPOTIFY_CLIENT_SECRET`
- `SPOTIFY_REFRESH_TOKEN`
- Optional `SPOTIFY_REDIRECT_URI`
