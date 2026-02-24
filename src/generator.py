from __future__ import annotations

import random
from collections import Counter

from .models import GenerationDiagnostics, GenerationResult, Mission


DEFAULT_MIN_FILLERS = 2


def generate_playlist(missions: list[Mission], seed: int | None = None, min_fillers: int = DEFAULT_MIN_FILLERS) -> list[str]:
    return generate_playlist_with_diagnostics(missions, seed=seed, min_fillers=min_fillers).playlist


def generate_playlist_with_diagnostics(
    missions: list[Mission],
    seed: int | None = None,
    min_fillers: int = DEFAULT_MIN_FILLERS,
) -> GenerationResult:
    if not missions:
        return GenerationResult(
            playlist=[],
            diagnostics=GenerationDiagnostics(False, False, False),
        )

    remaining = {mission.song_title: mission.stream_count for mission in missions}
    total_tracks = sum(remaining.values())
    if total_tracks <= 0:
        raise ValueError("At least one stream count must be positive")

    min_fillers = max(0, min_fillers)
    ideal_gaps = {title: total_tracks / count for title, count in remaining.items()}
    next_ideal_position = {title: 0.0 for title in remaining}

    rng = random.Random(seed)
    playlist: list[str] = []

    used_adjacency_fallback = False
    used_distribution_fallback = False
    used_pattern_fallback = False

    for index in range(total_tracks):
        active_gap = min_fillers
        candidates = _gap_candidates(remaining, playlist, active_gap)

        while not candidates and active_gap > 0:
            active_gap -= 1
            used_adjacency_fallback = True
            candidates = _gap_candidates(remaining, playlist, active_gap)

        if not candidates:
            candidates = [title for title, count in remaining.items() if count > 0]

        if active_gap == min_fillers and min_fillers > 0:
            feasible_candidates = [
                title for title in candidates if _keeps_gap_feasible_after_pick(remaining, title, min_fillers)
            ]
            if feasible_candidates:
                candidates = feasible_candidates

        weights: list[float] = []
        for title in candidates:
            spread_penalty = abs(index - next_ideal_position[title])
            pattern_penalty = _pattern_penalty(playlist, title)
            proximity_penalty = _proximity_penalty(playlist, title, min_fillers)

            if pattern_penalty > 0:
                used_pattern_fallback = True
            if spread_penalty > ideal_gaps[title]:
                used_distribution_fallback = True

            base = remaining[title]
            weight = base / (1.0 + (spread_penalty * 1.6) + (pattern_penalty * 2.5) + (proximity_penalty * 3.0))
            weights.append(max(0.0001, weight))

        choice = rng.choices(candidates, weights=weights, k=1)[0]

        playlist.append(choice)
        remaining[choice] -= 1
        next_ideal_position[choice] += ideal_gaps[choice]

    repaired = _repair_adjacent_duplicates(playlist)

    return GenerationResult(
        playlist=repaired,
        diagnostics=GenerationDiagnostics(
            used_adjacency_fallback=used_adjacency_fallback,
            used_distribution_fallback=used_distribution_fallback,
            used_pattern_fallback=used_pattern_fallback,
        ),
    )


def _gap_candidates(remaining: dict[str, int], playlist: list[str], gap: int) -> list[str]:
    blocked = set(playlist[-gap:]) if gap > 0 else set()
    return [title for title, count in remaining.items() if count > 0 and title not in blocked]


def _proximity_penalty(playlist: list[str], candidate: str, min_fillers: int) -> float:
    if min_fillers <= 0 or not playlist:
        return 0.0
    lookback = playlist[-min_fillers:]
    if candidate in lookback:
        return float(min_fillers - lookback[::-1].index(candidate))
    return 0.0


def _pattern_penalty(playlist: list[str], candidate: str) -> float:
    if len(playlist) < 3:
        return 0.0

    penalty = 0.0
    trial = playlist + [candidate]

    if len(trial) >= 4 and trial[-1] == trial[-3] and trial[-2] == trial[-4]:
        penalty += 4.0

    if len(trial) >= 6 and trial[-1] == trial[-4] and trial[-2] == trial[-5] and trial[-3] == trial[-6]:
        penalty += 3.0

    recent = trial[-8:]
    counts = Counter(recent)
    if counts and counts.most_common(1)[0][1] >= 4:
        penalty += 2.0

    return penalty


def _repair_adjacent_duplicates(playlist: list[str]) -> list[str]:
    if len(playlist) < 3:
        return playlist

    repaired = playlist[:]
    for i in range(1, len(repaired)):
        if repaired[i] != repaired[i - 1]:
            continue

        swap_index = -1
        for j in range(i + 1, len(repaired)):
            if repaired[j] == repaired[i] or repaired[j] == repaired[i - 1]:
                continue
            if j + 1 < len(repaired) and repaired[j + 1] == repaired[i]:
                continue
            swap_index = j
            break

        if swap_index != -1:
            repaired[i], repaired[swap_index] = repaired[swap_index], repaired[i]

    return repaired


def is_no_adjacent_feasible(missions: list[Mission]) -> bool:
    return is_min_filler_feasible(missions, min_fillers=1)


def is_min_filler_feasible(missions: list[Mission], min_fillers: int) -> bool:
    counts = [m.stream_count for m in missions if m.stream_count > 0]
    return _counts_feasible(counts, min_fillers=max(0, min_fillers))


def _keeps_gap_feasible_after_pick(remaining: dict[str, int], pick: str, min_fillers: int) -> bool:
    post_counts = []
    for title, count in remaining.items():
        next_count = count - 1 if title == pick else count
        if next_count > 0:
            post_counts.append(next_count)
    return _counts_feasible(post_counts, min_fillers=min_fillers)


def _counts_feasible(counts: list[int], min_fillers: int) -> bool:
    if not counts:
        return True
    total = sum(counts)
    highest = max(counts)
    return (highest - 1) * min_fillers <= (total - highest)
