from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Mission:
    song_title: str
    stream_count: int


@dataclass(frozen=True)
class GenerationDiagnostics:
    used_adjacency_fallback: bool
    used_distribution_fallback: bool
    used_pattern_fallback: bool


@dataclass(frozen=True)
class GenerationResult:
    playlist: list[str]
    diagnostics: GenerationDiagnostics
