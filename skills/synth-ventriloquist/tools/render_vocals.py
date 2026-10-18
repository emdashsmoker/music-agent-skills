# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
"""Render the lead vocal stem of an example song (or the probe line) with one checkout of the toolkit.

Only the Python side of a song is run: Song.save is replaced so that it sings the lead parts and stops before
the LMMS project, the drum kit and the plan are written. The stems are therefore the same audio LMMS would play.

Usage:
    python render_vocals.py <checkout> <out_dir> <voice> song <example> [build args ...]
    python render_vocals.py <checkout> <out_dir> <voice> probe <high|low>
Writes <out_dir>/vocals.json: {"bpm", "voice", "checkout", "parts": [render_part reports]}.
"""
import importlib.util
import json
import os
import sys
import time

SKILL = os.path.join("skills", "synth-ventriloquist", "en", "synth-ventriloquist")
PROBE_TEXT = "Share the air we hear for years"          # the check sentence of the vowel-timing change
PROBE_MELODIES = {"high": "A4/1 G4/0.5 A4/1.5 G4/0.5 A4/1.5 G4/0.5 E4/2 R/1",
                  "low": "A3/1 G3/0.5 A3/1.5 G3/0.5 A3/1.5 G3/0.5 E3/2 R/1"}
PROBE_BPM = 120.0
PROBE_START_BEAT = 4.0
PROBE_TOTAL_BEATS = 24.0


def _plain(value):
    return value.item() if hasattr(value, "item") else str(value)


def render_song(skill: str, out_dir: str, voice: str, example: str, build_args: list) -> dict:
    from lmmskit import compose
    captured = {}
    extra = json.loads(os.environ.get("VOCAL_OPTIONS", "{}"))      # engine options added to every vocal part
    if extra:
        original_vocal = compose.Song.vocal

        def vocal(self, name, voice_id, **kwargs):
            return original_vocal(self, name, voice_id, **{**kwargs, **extra})
        compose.Song.vocal = vocal

    def save(self, path, vocal_cache=None):
        self.vocals = [w for w in self.vocals if w.part.role == "vocal"]   # backing parts sing the lead's words
        captured["parts"] = self.render_vocals(path, vocal_cache)
        captured["bpm"] = self.bpm
        return path

    compose.Song.save = save
    spec = importlib.util.spec_from_file_location("example_song", os.path.join(skill, "examples", example, "song.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    os.chdir(out_dir)
    module.build(voice, "song", *build_args)
    return captured


def render_probe(out_dir: str, voice: str, register: str) -> dict:
    from lmmskit.vocal import part as vocal_part
    part = vocal_part.VocalPart("probe", voice)
    part.line(PROBE_START_BEAT, PROBE_TEXT, PROBE_MELODIES[register])
    stem = os.path.join(out_dir, "probe.flac")
    report = vocal_part.render_part(part, PROBE_BPM, None, PROBE_TOTAL_BEATS, stem, os.path.join(out_dir, ".vocal_cache"))
    return {"parts": [report], "bpm": PROBE_BPM}


def main() -> None:
    checkout, out_dir, voice, mode, *rest = sys.argv[1:]
    checkout, out_dir = os.path.abspath(checkout), os.path.abspath(out_dir)
    skill = os.path.join(checkout, SKILL)
    sys.path.insert(0, os.path.join(skill, "scripts"))
    os.makedirs(out_dir, exist_ok=True)
    began = time.time()
    result = render_song(skill, out_dir, voice, rest[0], rest[1:]) if mode == "song" else render_probe(out_dir, voice, rest[0])
    result.update({"voice": voice, "checkout": checkout, "mode": mode, "args": rest, "seconds": round(time.time() - began, 1),
                   "options": json.loads(os.environ.get("VOCAL_OPTIONS", "{}"))})
    with open(os.path.join(out_dir, "vocals.json"), "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=1, ensure_ascii=False, default=_plain)
    print(f"{voice} {mode} {' '.join(rest)}: {len(result['parts'])} part(s), {result['seconds']} s -> {out_dir}/vocals.json")


if __name__ == "__main__":
    main()
