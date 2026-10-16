# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
"""Genre profiles: the numeric defaults a plan starts from (tempo, loudness, pump depth, balance, form).

These are conventions of each style, not laws. references/genres.md explains the patterns and sound
choices behind every profile; a user's request overrides any number here.

Fields
  bpm        (low, high, default)
  lufs       integrated loudness target of the master
  sidechain  kick ducking depth in dB for bass/music (0 = none by convention)
  swing      0-0.5 share of a 16th that off-steps are delayed
  scale      usual tonality
  levels     role levels in LU against the kick that replace compose.LEVEL_OF_ROLE for this style (roles not named keep the default)
  vocal_duck optional (depth_db, presence_db) of the music-bus ducking under sung lead lines, replacing
             compose.VOCAL_DUCK_DB / VOCAL_PRESENCE_DB for this style; a song script's duck_for_vocals call beats both
  bands      shifts of mix.BAND_TARGETS centre in dB (how bright / bass-heavy the master is)
  form       section template as (name, bars) - one common arrangement, sized for a full track
  kit        drum patches that fit: kick, snare/clap, closed hat, open hat
"""
from __future__ import annotations

_DANCE = [("intro", 16), ("build1", 8), ("drop1", 16), ("break", 16), ("build2", 8), ("drop2", 16), ("outro", 16)]
_SONG = [("intro", 8), ("verse1", 16), ("chorus1", 8), ("verse2", 16), ("chorus2", 8), ("bridge", 8), ("chorus3", 16), ("outro", 8)]

GENRES: dict[str, dict] = {
    # ---- house family -----------------------------------------------------------------------------
    "house": {"bpm": (118, 128, 124), "lufs": -10, "sidechain": 5, "swing": 0.12, "scale": "minor/dorian",
              "levels": {"kick": 0, "bass": -2, "hat": -6}, "form": _DANCE, "kit": ("house_kick", "909_clap", "909_hat", "909_ohat")},
    "deep_house": {"bpm": (115, 124, 120), "lufs": -11, "sidechain": 4, "swing": 0.15, "scale": "minor7/dorian",
                   "levels": {"pad": -4, "keys": -2, "hat": -9}, "bands": {"air": -2}, "form": _DANCE,
                   "kit": ("house_kick", "clap_tight", "hat_tight", "ohat")},
    "tech_house": {"bpm": (122, 128, 125), "lufs": -10, "sidechain": 5, "swing": 0.1, "scale": "minor",
                   "levels": {"bass": -3, "perc": -6}, "form": _DANCE, "kit": ("house_kick", "909_clap", "909_hat", "909_ohat")},
    "progressive_house": {"bpm": (122, 130, 126), "lufs": -10, "sidechain": 6, "scale": "minor",
                          "levels": {"lead": 0, "pad": -5}, "form": _DANCE, "kit": ("trance_kick", "909_clap", "909_hat", "909_ohat")},
    "electro_house": {"bpm": (125, 130, 128), "lufs": -9, "sidechain": 8, "scale": "minor",
                      "levels": {"bass": 0, "lead": 0}, "form": _DANCE, "kit": ("house_kick", "909_clap", "909_hat", "909_ohat")},
    "future_house": {"bpm": (120, 128, 126), "lufs": -9, "sidechain": 7, "scale": "minor", "form": _DANCE,
                     "kit": ("house_kick", "clap", "hat", "ohat")},
    "acid_house": {"bpm": (118, 128, 122), "lufs": -10, "sidechain": 3, "swing": 0.1, "scale": "minor/phrygian",
                   "levels": {"bass": 0}, "form": _DANCE, "kit": ("909_kick", "909_clap", "909_hat", "909_ohat")},
    "uk_garage": {"bpm": (128, 136, 132), "lufs": -10, "sidechain": 3, "swing": 0.3, "scale": "minor", "form": _DANCE,
                  "kit": ("house_kick", "snare_short", "hat_tight", "ohat")},
    "disco": {"bpm": (110, 126, 118), "lufs": -11, "sidechain": 2, "scale": "minor/major", "levels": {"bass": -2, "keys": -3},
              "form": _SONG, "kit": ("kick_acoustic", "clap", "hat", "ohat")},
    # ---- techno family ----------------------------------------------------------------------------
    "techno": {"bpm": (125, 140, 132), "lufs": -10, "sidechain": 4, "scale": "minor/phrygian",
               "levels": {"kick": 0, "bass": -3, "hat": -6, "perc": -6}, "bands": {"sub": 1}, "form": _DANCE,
               "kit": ("techno_kick", "909_clap", "909_hat", "909_ohat")},
    "minimal_techno": {"bpm": (122, 130, 126), "lufs": -11, "sidechain": 3, "scale": "minor",
                       "levels": {"perc": -5, "pad": -8}, "form": _DANCE, "kit": ("techno_kick", "808_rim", "606_hat", "606_ohat")},
    "hard_techno": {"bpm": (140, 160, 148), "lufs": -9, "sidechain": 5, "scale": "phrygian",
                    "levels": {"kick": 0, "bass": -4}, "form": _DANCE, "kit": ("industrial_kick", "909_clap", "909_hat", "909_ohat")},
    "electro": {"bpm": (120, 135, 128), "lufs": -10, "sidechain": 0, "scale": "minor", "levels": {"snare": -1},
                "form": _DANCE, "kit": ("808_kick", "808_snare", "808_hat", "808_ohat")},
    "ebm": {"bpm": (110, 130, 122), "lufs": -10, "sidechain": 3, "scale": "minor/phrygian",
            "levels": {"bass": -1, "snare": -1, "vocal": -2}, "bands": {"low_mid": 1}, "form": _SONG,
            "kit": ("techno_kick", "electro_snare", "808_hat", "808_ohat")},
    "industrial": {"bpm": (90, 140, 118), "lufs": -10, "sidechain": 2, "scale": "phrygian/locrian",
                   "levels": {"snare": 0, "perc": -4, "vocal": -2}, "bands": {"high_mid": 2}, "form": _SONG,
                   "kit": ("industrial_kick", "snare_harsh", "hat", "ohat")},
    "futurepop": {"bpm": (125, 140, 132), "lufs": -10, "sidechain": 6, "scale": "minor",
                  "levels": {"lead": -3, "pad": -8, "vocal": 0, "bass": -3}, "form": [
                      ("intro", 8), ("verse1", 16), ("pre1", 8), ("chorus1", 16), ("verse2", 16), ("pre2", 8),
                      ("chorus2", 16), ("bridge", 8), ("chorus3", 16), ("outro", 8)],
                  "kit": ("trance_kick", "909_clap", "909_hat", "909_ohat")},
    # ---- trance family ----------------------------------------------------------------------------
    "trance": {"bpm": (130, 142, 138), "lufs": -10, "sidechain": 8, "scale": "minor",
               "levels": {"lead": -3, "pad": -8, "pluck": -5}, "form": _DANCE, "kit": ("trance_kick", "909_clap", "909_hat", "909_ohat")},
    "uplifting_trance": {"bpm": (136, 142, 138), "lufs": -10, "sidechain": 8, "scale": "minor (i-VI-III-VII, VI-VII-i)",
                         "levels": {"lead": -3, "pad": -7, "pluck": -5, "bass": -3},
                         "form": [("intro", 32), ("build1", 16), ("drop1", 32), ("breakdown", 32), ("build2", 16),
                                  ("climax", 48), ("outro", 32)],
                         "kit": ("trance_kick", "909_clap", "909_hat", "909_ohat")},
    "progressive_trance": {"bpm": (128, 136, 132), "lufs": -10, "sidechain": 6, "scale": "minor",
                           "levels": {"pad": -7}, "form": _DANCE, "kit": ("trance_kick", "clap_tight", "909_hat", "909_ohat")},
    "psytrance": {"bpm": (138, 148, 145), "lufs": -9, "sidechain": 0, "scale": "phrygian/phrygian_dominant",
                  "levels": {"kick": 0, "bass": -1, "lead": -6, "fx": -8}, "bands": {"bass": 1},
                  "form": [("intro", 16), ("groove1", 32), ("break1", 16), ("groove2", 32), ("break2", 16), ("peak", 48), ("outro", 16)],
                  "kit": ("psy_kick", "snare_short", "909_hat", "909_ohat")},
    "dark_psytrance": {"bpm": (148, 180, 155), "lufs": -9, "sidechain": 0, "scale": "locrian/chromatic",
                       "levels": {"bass": -1, "lead": -7, "fx": -6, "pad": -10}, "bands": {"air": -1},
                       "form": [("intro", 16), ("groove1", 32), ("break1", 8), ("groove2", 48), ("break2", 16), ("peak", 48), ("outro", 16)],
                       "kit": ("psy_kick", "snare_short", "909_hat", "909_ohat")},
    "goa_trance": {"bpm": (135, 150, 142), "lufs": -10, "sidechain": 0, "scale": "phrygian_dominant/harmonic_minor",
                   "levels": {"lead": -4, "pluck": -5}, "form": _DANCE, "kit": ("psy_kick", "909_clap", "909_hat", "909_ohat")},
    "hard_trance": {"bpm": (140, 150, 145), "lufs": -9, "sidechain": 8, "scale": "minor", "form": _DANCE,
                    "kit": ("hard_kick", "909_clap", "909_hat", "909_ohat")},
    # ---- hardcore family --------------------------------------------------------------------------
    "gabber": {"bpm": (160, 200, 180), "lufs": -8, "sidechain": 0, "scale": "minor/phrygian",
               "levels": {"kick": 0, "bass": -12, "lead": -4, "hat": -7}, "bands": {"low_mid": 2, "mid": 2},
               "form": [("intro", 16), ("main1", 32), ("break", 16), ("main2", 32), ("outro", 16)],
               "kit": ("hard_kick", "909_clap", "909_hat", "909_ohat")},
    "hardstyle": {"bpm": (145, 155, 150), "lufs": -8, "sidechain": 0, "scale": "minor",
                  "levels": {"kick": 0, "lead": -3, "bass": -10}, "form": _DANCE, "kit": ("hard_kick", "909_clap", "909_hat", "909_ohat")},
    "happy_hardcore": {"bpm": (160, 180, 170), "lufs": -9, "sidechain": 4, "scale": "major", "levels": {"lead": -3, "keys": -4},
                       "form": _DANCE, "kit": ("hard_kick", "909_clap", "909_hat", "909_ohat")},
    # ---- breakbeat family -------------------------------------------------------------------------
    "breakbeat": {"bpm": (120, 140, 130), "lufs": -10, "sidechain": 2, "swing": 0.1, "scale": "minor",
                  "levels": {"snare": 0, "bass": -2}, "form": _DANCE, "kit": ("kick_acoustic", "snare_acoustic", "hat", "ohat")},
    "big_beat": {"bpm": (100, 140, 125), "lufs": -9, "sidechain": 0, "scale": "minor/blues",
                 "levels": {"snare": 0, "kick": 0, "bass": -2, "lead": -4}, "bands": {"low_mid": 1, "mid": 1},
                 "form": _DANCE, "kit": ("kick_hiphop", "snare_acoustic", "hat", "ohat")},
    "drum_and_bass": {"bpm": (165, 180, 174), "lufs": -9, "sidechain": 3, "scale": "minor",
                      "levels": {"snare": 0, "sub": -3, "bass": -3, "hat": -7}, "bands": {"sub": 1},
                      "form": [("intro", 16), ("build1", 16), ("drop1", 32), ("break", 16), ("build2", 16), ("drop2", 32), ("outro", 16)],
                      "kit": ("dnb_kick", "snare_acoustic", "hat_tight", "ohat")},
    "liquid_dnb": {"bpm": (170, 176, 174), "lufs": -10, "sidechain": 3, "scale": "minor7/major7",
                   "levels": {"pad": -6, "keys": -5, "sub": -3}, "form": _DANCE, "kit": ("dnb_kick", "snare_acoustic", "hat_tight", "ohat")},
    "jungle": {"bpm": (155, 172, 165), "lufs": -10, "sidechain": 0, "scale": "minor", "levels": {"sub": -2, "snare": 0},
               "form": _DANCE, "kit": ("kick_acoustic", "snare_acoustic", "hat", "ohat")},
    "dubstep": {"bpm": (138, 142, 140), "lufs": -9, "sidechain": 3, "scale": "minor/phrygian",
                "levels": {"snare": 0, "bass": 0, "sub": -3}, "bands": {"sub": 2}, "form": _DANCE,
                "kit": ("kick_hiphop", "snare_hiphop", "hat_tight", "ohat")},
    "idm": {"bpm": (80, 170, 130), "lufs": -11, "sidechain": 0, "scale": "any (modal, chromatic colour)",
            "levels": {"perc": -4, "pad": -6, "keys": -5}, "form": [("a", 16), ("b", 16), ("a2", 16), ("c", 16), ("b2", 16), ("coda", 8)],
            "kit": ("606_kick", "606_snare", "606_hat", "606_ohat")},
    # ---- hip hop family ---------------------------------------------------------------------------
    "hip_hop": {"bpm": (80, 100, 90), "lufs": -10, "sidechain": 2, "swing": 0.2, "scale": "minor",
                "levels": {"kick": 0, "snare": -1, "bass": -2, "vocal": 0, "keys": -6}, "form": _SONG,
                "kit": ("kick_hiphop", "snare_hiphop", "hat", "ohat")},
    "trap": {"bpm": (130, 160, 140), "lufs": -10, "sidechain": 0, "scale": "minor/harmonic_minor",
             "levels": {"bass": 0, "hat": -6, "snare": -1, "vocal": 0}, "bands": {"sub": 2}, "form": _SONG,
             "kit": ("808_kick", "808_clap", "808_hat", "808_ohat")},
    "lofi_hip_hop": {"bpm": (70, 90, 80), "lufs": -13, "sidechain": 3, "swing": 0.25, "scale": "major7/minor7",
                     "levels": {"keys": -3, "kick": 0, "hat": -10}, "bands": {"air": -5, "high_mid": -2}, "form": _SONG,
                     "kit": ("kick_hiphop", "snare_short", "hat_tight", "ohat")},
    # ---- synth pop family -------------------------------------------------------------------------
    "synthpop": {"bpm": (100, 130, 118), "lufs": -11, "sidechain": 2, "scale": "major/minor",
                 "levels": {"vocal": 0, "snare": -1, "lead": -5, "bass": -2}, "form": _SONG,
                 "kit": ("linn_kick", "linn_snare", "linn_cabasa", "606_ohat")},
    "synthwave": {"bpm": (80, 118, 100), "lufs": -11, "sidechain": 5, "scale": "minor (i-VI-III-VII)",
                  "levels": {"snare": 0, "bass": -2, "lead": -4, "pad": -7}, "form": _SONG,
                  "kit": ("linn_kick", "reverb_snare", "linn_cabasa", "606_ohat")},
    "darksynth": {"bpm": (95, 130, 112), "lufs": -10, "sidechain": 6, "scale": "minor/phrygian",
                  "levels": {"bass": -1, "snare": 0, "lead": -4}, "bands": {"low_mid": 1}, "form": _SONG,
                  "kit": ("industrial_kick", "reverb_snare", "909_hat", "909_ohat")},
    "doomer": {"bpm": (95, 150, 124), "lufs": -12, "sidechain": 0, "scale": "minor (i-VI-III-VII, i-iv)",
               "levels": {"bass": -1, "vocal": -1, "snare": -1, "pluck": -4, "pad": -8, "hat": -10},
               "bands": {"air": -3, "high_mid": -2, "low_mid": 1},
               "form": [("intro", 8), ("verse1", 16), ("chorus1", 8), ("verse2", 16), ("chorus2", 8), ("instrumental", 8),
                        ("chorus3", 16), ("outro", 8)],
               "kit": ("linn_kick", "linn_snare", "cr78_hat", "606_ohat")},
    "chiptune": {"bpm": (110, 180, 140), "lufs": -11, "sidechain": 0, "scale": "major/minor",
                 "levels": {"lead": -2, "bass": -3}, "bands": {"sub": -4}, "form": _SONG,
                 "kit": ("606_kick", "606_snare", "cr78_hat", "606_ohat")},
    "vaporwave": {"bpm": (60, 100, 80), "lufs": -13, "sidechain": 0, "scale": "major7", "levels": {"keys": -3, "pad": -4},
                  "bands": {"air": -5}, "form": _SONG, "kit": ("linn_kick", "reverb_snare", "linn_cabasa", "ohat")},
    # ---- slow and beatless ------------------------------------------------------------------------
    "ambient": {"bpm": (60, 100, 80), "lufs": -16, "sidechain": 0, "scale": "lydian/major/dorian",
                "levels": {"pad": 0, "keys": -3, "fx": -6}, "bands": {"sub": -3, "air": -2},
                "form": [("emerge", 16), ("drift1", 32), ("swell", 16), ("drift2", 32), ("fade", 16)],
                "kit": ("boom_kick", "808_rim", "shaker", "808_ride")},
    "downtempo": {"bpm": (80, 110, 95), "lufs": -12, "sidechain": 2, "swing": 0.15, "scale": "minor7/dorian",
                  "levels": {"pad": -5, "keys": -4}, "form": _SONG, "kit": ("kick_hiphop", "snare_short", "hat_tight", "ohat")},
    "trip_hop": {"bpm": (70, 95, 85), "lufs": -12, "sidechain": 0, "swing": 0.15, "scale": "minor",
                 "levels": {"snare": 0, "bass": -1, "vocal": 0}, "bands": {"air": -3}, "form": _SONG,
                 "kit": ("kick_acoustic", "snare_acoustic", "hat", "ohat")},
    "dub_techno": {"bpm": (110, 125, 118), "lufs": -12, "sidechain": 3, "scale": "minor7",
                   "levels": {"keys": -4, "pad": -5}, "bands": {"air": -3}, "form": _DANCE, "kit": ("techno_kick", "808_rim", "606_hat", "606_ohat")},
}
ALIASES = {"dnb": "drum_and_bass", "drum_n_bass": "drum_and_bass", "future_pop": "futurepop", "psy": "psytrance",
           "dark_psy": "dark_psytrance", "darkpsy": "dark_psytrance", "hardcore": "gabber", "post_punk": "doomer",
           "russian_doomer": "doomer", "coldwave": "doomer", "outrun": "synthwave", "retrowave": "synthwave",
           "edm": "electro_house", "hiphop": "hip_hop", "lofi": "lofi_hip_hop", "2step": "uk_garage",
           "garage": "uk_garage", "electronic_body_music": "ebm", "synth_pop": "synthpop", "uplifting": "uplifting_trance"}
DEFAULT = {"bpm": (90, 140, 120), "lufs": -11, "sidechain": 4, "swing": 0.0, "scale": "minor", "levels": {}, "bands": {},
           "form": _SONG, "kit": ("house_kick", "clap", "hat", "ohat")}


def get(name: str | None) -> dict:
    """Profile for a genre name (spaces, dashes and case ignored); unknown names give the generic default."""
    key = (name or "").strip().lower().replace(" ", "_").replace("-", "_")
    key = ALIASES.get(key, key)
    return {**DEFAULT, **GENRES.get(key, {}), "name": key if key in GENRES else "generic"}


def names() -> list[str]:
    return sorted(GENRES)
