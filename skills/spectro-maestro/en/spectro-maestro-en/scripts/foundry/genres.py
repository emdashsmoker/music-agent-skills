# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
# Part of Spectro Maestro. See LICENSE and THIRD-PARTY-NOTICES.md at the root of the skill.
"""Genre library: one YAML file per genre under assets/genres.

Each file holds conventions (`about`), a mix `profile` (role levels, returns, master target, QA limits)
and a complete starter `song` written with roman-numeral chords so it works in any key."""
from __future__ import annotations

import copy
import glob
import os

GENRE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "assets", "genres")


def available() -> list:
    return sorted(os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(GENRE_DIR, "*.yaml")))


def load(genre_id: str) -> dict:
    path = os.path.join(GENRE_DIR, f"{genre_id}.yaml")
    if not os.path.exists(path):
        raise KeyError(f"unknown genre {genre_id!r}; available: {', '.join(available())}")
    from .spec import load_yaml
    data = load_yaml(path)
    parent = data.get("extends")
    if parent:                                   # a sub-genre states only what differs from its parent
        base = load(parent)
        merged = _merge(base, {k: v for k, v in data.items() if k != "extends"})
        merged["id"] = genre_id
        return merged
    data.setdefault("id", genre_id)
    return data


def _merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict) and key not in ("sections",):
            out[key] = _merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def profile_of(genre_id: str | None) -> dict:
    """Mix profile of a genre; empty when the song names no known genre."""
    if not genre_id or genre_id not in available():
        return {}
    return load(genre_id).get("profile") or {}


def starter_song(genre_id: str, title: str | None = None, bpm: float | None = None, key: str | None = None) -> dict:
    data = load(genre_id)
    song = copy.deepcopy(data["song"])
    ordered = {"title": title or f"Untitled {data.get('name', genre_id)}", "genre": genre_id,
               "bpm": bpm or data["bpm"][2], "key": key or data["keys"][0]}
    ordered.update({k: v for k, v in song.items() if k not in ordered})
    return ordered
