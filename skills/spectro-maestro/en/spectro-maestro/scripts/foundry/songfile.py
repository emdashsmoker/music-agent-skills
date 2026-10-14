# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
# Part of Spectro Maestro. See LICENSE and THIRD-PARTY-NOTICES.md at the root of the skill.
"""Open a song from disk: a YAML spec is compiled, a project JSON is loaded as is."""
from __future__ import annotations

from . import export, instruments, spec


def load(path: str, sections: str | None = None) -> dict:
    """Spec (.yaml) or project (.json) -> project dict. `sections` keeps only the named sections (fast preview)."""
    if path.endswith(".json"):
        if sections:
            raise spec.SpecError("--sections needs the YAML song file; a project JSON is always rendered whole")
        return export.load_project(path)
    song = spec.load_spec(path)
    if sections:
        wanted = [name.strip() for name in sections.split(",")]
        song["sections"] = [s for s in song["sections"] if s.get("name") in wanted]
        if not song["sections"]:
            raise spec.SpecError(f"none of the sections {wanted} exist in {path}")
    return spec.compile_spec(song, instruments.drum_names())
