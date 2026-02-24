from __future__ import annotations

from collections import Counter

from src.generator import generate_playlist, is_no_adjacent_feasible
from src.models import Mission


def test_generate_playlist_respects_exact_counts_and_known_titles():
    missions = [Mission("Butter", 5), Mission("Dynamite", 3), Mission("Spring Day", 4)]

    playlist = generate_playlist(missions, seed=7)
    counts = Counter(playlist)

    assert len(playlist) == 12
    assert counts == Counter({"Butter": 5, "Dynamite": 3, "Spring Day": 4})
    assert set(playlist) == {"Butter", "Dynamite", "Spring Day"}


def test_generate_playlist_has_no_adjacent_duplicates_when_feasible():
    missions = [Mission("A", 3), Mission("B", 3), Mission("C", 1)]

    assert is_no_adjacent_feasible(missions)
    playlist = generate_playlist(missions, seed=1)
    assert all(playlist[i] != playlist[i - 1] for i in range(1, len(playlist)))


def test_generate_playlist_respects_two_fillers_when_feasible():
    missions = [Mission("A", 3), Mission("B", 3), Mission("C", 3)]
    playlist = generate_playlist(missions, seed=9, min_fillers=2)

    for i in range(2, len(playlist)):
        assert playlist[i] != playlist[i - 2]


def test_generate_playlist_seed_is_reproducible():
    missions = [Mission("A", 4), Mission("B", 3), Mission("C", 2)]

    p1 = generate_playlist(missions, seed=42)
    p2 = generate_playlist(missions, seed=42)

    assert p1 == p2


def test_generate_playlist_infeasible_case_still_returns_all_counts():
    missions = [Mission("A", 5), Mission("B", 1)]
    playlist = generate_playlist(missions, seed=2)

    counts = Counter(playlist)
    assert counts == Counter({"A": 5, "B": 1})
    assert len(playlist) == 6
