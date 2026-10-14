# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
# Part of Spectro Maestro. See LICENSE and THIRD-PARTY-NOTICES.md at the root of the skill.
"""Mixing defaults by role. A track's final settings are: role defaults, then the genre profile,
then the track's own `mix:` block. Levels are loudness targets, not fader positions: the mixer
measures each stem and moves it to its target, so a patch that happens to be loud or quiet
still lands in the right place."""
from __future__ import annotations

import copy

REFERENCE_LUFS = -20.0          # loud-part loudness given to a role with level 0 before mastering

# level: dB relative to the reference; reverb/delay: send gain (linear); duck: sidechain depth in dB
ROLE_DEFAULTS = {
    "kick":    dict(bus="drums", level=-4.0, pan=0.0, width=0.0, reverb=0.0, delay=0.0, duck=0.0, hpf=25),
    "snare":   dict(bus="drums", level=-5.0, pan=0.0, width=0.0, reverb=0.10, delay=0.0, duck=0.0, hpf=110),
    "hat":     dict(bus="drums", level=-14.0, pan=0.12, width=0.0, reverb=0.04, delay=0.0, duck=0.0, hpf=400),
    "perc":    dict(bus="drums", level=-12.5, pan=-0.2, width=0.0, reverb=0.10, delay=0.0, duck=0.0, hpf=150),
    "bass":    dict(bus="bass", level=-3.0, pan=0.0, width=0.0, reverb=0.0, delay=0.0, duck=-7.0, hpf=28, mono=True),
    "sub":     dict(bus="bass", level=-4.5, pan=0.0, width=0.0, reverb=0.0, delay=0.0, duck=-9.0, hpf=25, lpf=140,
                    mono=True),
    "lead":    dict(bus="music", level=-2.0, pan=0.0, width=1.0, reverb=0.22, delay=0.16, duck=-2.5, hpf=180),
    "pluck":   dict(bus="music", level=-3.5, pan=0.0, width=1.0, reverb=0.22, delay=0.20, duck=-3.0, hpf=200),
    "arp":     dict(bus="music", level=-5.5, pan=0.0, width=1.0, reverb=0.18, delay=0.22, duck=-3.0, hpf=250),
    "pad":     dict(bus="music", level=-7.0, pan=0.0, width=1.0, reverb=0.28, delay=0.0, duck=-5.0, hpf=160),
    "chord":   dict(bus="music", level=-3.5, pan=0.0, width=1.0, reverb=0.18, delay=0.08, duck=-4.0, hpf=160),
    "keys":    dict(bus="music", level=-3.5, pan=0.0, width=1.0, reverb=0.16, delay=0.05, duck=-2.0, hpf=110),
    "fx":      dict(bus="fx", level=-8.0, pan=0.0, width=1.0, reverb=0.25, delay=0.0, duck=0.0, hpf=80),
    "vocal":   dict(bus="vocals", level=0.0, pan=0.0, width=0.0, reverb=0.16, delay=0.08, duck=0.0, hpf=90),
    "backing": dict(bus="vocals", level=-8.0, pan=0.0, width=1.0, reverb=0.24, delay=0.06, duck=0.0, hpf=140),
}

RETURNS = {
    "reverb": dict(decay=2.2, predelay=0.02, damp=6500.0, lowcut=250.0, duck=-4.0),
    "delay": dict(time="1/8d", feedback=0.36, damp=4500.0, lowcut=300.0, duck=-3.0),
    # Vocal sends are never ducked by the kick: a pumped tail sounds chopped on every beat.
    "vox_reverb": dict(decay=1.8, predelay=0.06, damp=7000.0, lowcut=300.0, duck=0.0),
    "vox_delay": dict(time="1/4", feedback=0.28, damp=3500.0, lowcut=400.0, duck=0.0),
}

BUS_CHAINS = {
    "drums": [dict(fx="comp", threshold=-14.0, ratio=2.5, attack=0.02, release=0.12, makeup=1.0)],
    "bass": [],
    "music": [],
    "fx": [],
    "vocals": [],
}

# The lead vocal's own chain: clean up, even out, add presence and air. Applied before levelling.
VOCAL_CHAIN = [
    dict(fx="hpf", freq=95, poles=4),
    dict(fx="eq", bands=[["peak", 280, -2.5, 1.2], ["peak", 3200, 2.5, 1.0], ["highshelf", 9500, 3.0]]),
    dict(fx="comp", threshold=-20.0, ratio=3.0, attack=0.006, release=0.11, makeup=3.0),
    dict(fx="comp", threshold=-12.0, ratio=6.0, attack=0.001, release=0.06),
]

MASTER_DEFAULTS = dict(lufs=-10.0, ceiling=-1.0, glue=True, clip=True, tail=3.0, fade_out=0.0, eq=[],
                       vocal_carve=-2.5, sidechain_release=0.5, mono_below=110.0)


def track_settings(track: dict, profile: dict) -> dict:
    """Resolve one track's mix settings from role defaults, genre profile and the track itself."""
    role = track.get("role", "lead")
    settings = copy.deepcopy(ROLE_DEFAULTS.get(role, ROLE_DEFAULTS["lead"]))
    settings.update(copy.deepcopy((profile.get("roles") or {}).get(role, {})))
    own = copy.deepcopy(track.get("mix") or {})
    settings.update(own)
    settings.setdefault("gain_db", 0.0)
    settings.setdefault("inserts", [])
    return settings


def master_settings(project: dict, profile: dict) -> dict:
    settings = copy.deepcopy(MASTER_DEFAULTS)
    settings.update(copy.deepcopy(profile.get("master") or {}))
    settings.update(copy.deepcopy(project.get("master") or {}))
    return settings


def return_settings(project: dict, profile: dict) -> dict:
    settings = copy.deepcopy(RETURNS)
    for source in (profile.get("returns") or {}, (project.get("mix") or {}).get("returns") or {}):
        for name, values in source.items():
            settings.setdefault(name, {}).update(values)
    return settings
