# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
"""Mix by measurement: balance part levels from rendered stems, set master loudness, and check the result.

The checks encode textbook mixing ratios as testable numbers. They find where to look; when a
finding contradicts the creative intent (a deliberately dark track, a buried texture) keep the
intent and say so in the report.
"""
from __future__ import annotations

import os
import re
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from scipy import signal

from . import audio, compose, fx, genres, render, settings
from .findings import finding
from .project import TRACK_BB, TRACK_INSTRUMENT, TRACK_SAMPLE, EffectChain, Project

# Band level ranges of a finished master in dB relative to the full-band level. Derived from the
# spread of LMMS's own demo songs and common mastering references; genres shift the centre.
BAND_TARGETS = {"sub": (-12.0, -4.0), "bass": (-8.0, -2.0), "low_mid": (-14.0, -6.0), "mid": (-14.0, -6.0),
                "high_mid": (-19.0, -9.0), "air": (-24.0, -12.0)}
ANCHOR_PEAK_DB = -9.0                 # where the kick stem peaks before the master chain: leaves limiter headroom
ANCHOR_LOUDNESS = -20.0               # used when the anchor is not a drum
LEVEL_TOLERANCE_LU = 1.5
MAX_TRACK_VOLUME, MAX_FADER = 200.0, 2.0
MIN_FADER = 0.01
BB_DEFAULT_NAME = "beat/bassline"
PRESENCE_HZ, PRESENCE_OCTAVES = 2600.0, 3.0      # centre and width of the vocal presence lift
MAX_PRESENCE_LIFT_DB = 6.0
PRESENCE_BAND_SHARE = 0.65                      # measured: a 6 dB dip at the centre lowers the 1.3-5 kHz band by 3.9 dB
PRESENCE_SAFETY_DB = 1.0                        # aim a little above the required margin
INAUDIBLE_RESIDUAL_DB = -60.0         # a difference between two renders this far under the mix cannot be heard
BURIED_LU = 20.0                      # a part this far under the loudest one is practically inaudible
KICK_HISS_LIMIT_DB = -50.0            # 2-10 kHz against the low end in a kick's body; above this it is audible hiss or fuzz
HISS_FFT, HISS_SKIP_S = 512, 0.03
MAX_LIMITER_REDUCTION_DB = 3.0        # deepest cut the master limiter may make on the loudest moments
REDUCTION_PERCENTILE = 99.5           # 'the loudest moments': this percentile of 10 ms peak windows
PEAK_WINDOW_S, QUIET_WINDOW_DB = 0.01, -40.0
MASTER_PASSES = 2
# Brightness of the densest 20 s (audio.brightness_db: highs above 2.8 kHz against the mids, pink noise = 0).
# Finished electronic records sit between the 4.5 dB/oct analyser line (-4.5) and pink noise (0) in a full drop.
BRIGHTNESS_AIM = -6.0                 # what the tone fit lifts a dull mix to: the careful side of the reference
TONE_TOLERANCE_DB = 0.5               # a mix this close under the aim is left alone
BRIGHTNESS_RANGE = (-7.5, -1.5)       # outside this the check warns
TONE_SHELF_HZ = 3000.0
MAX_TONE_SHELF_DB = 5.0               # a larger lift repairs a problem that belongs to the sounds
TONE_FIXED_ROLES = set(compose.DRUM_ROLES) | {"sub", "bass"}          # drum peaks and low-end weight carry the balance: left as they are
STEM_OVERSAMPLING = 1
LOUDNESS_TOLERANCE_LU = 0.7
LIMITER_KEY = ("fast_lookahead_limiter_1913", "fastLookaheadLimiter")
LIMITER_GAIN_RANGE = (-20.0, 20.0)
TRUE_PEAK_LIMIT_DB = -0.3
TRUE_PEAK_CEILING_DB = -1.0
MIN_CREST_DB = 7.0
MIN_LOW_CORRELATION = 0.6
VOCAL_BODY_MARGIN_DB = 0.0
VOCAL_CONSONANT_MARGIN_DB = 2.0
VOCAL_MAX_MARGIN_DB = 9.0                 # judged in the densest section: a verse value would hide a chorus that falls short
MIN_VOCAL_SECTION_S = 1.0                 # a section with less sung time than this gets no value of its own
KICK_MARGIN_DB = 0.0
DRUMS_VS_REST_RANGE_LU = (-7.0, 5.0)
MASK_WINDOW_DB = 6.0
ACTIVE_WINDOW_DB = 12.0
TAIL_CUT_DB = -45.0
STFT_SIZE, STFT_HOP = 2048, 512
ROLE_KEYWORDS = [("vocal_bg", ("harmony", "backing", "choir", "bgv")), ("vocal", ("vocal", "vox", "voice", "sing")),
                 ("kick", ("kick", "bd", "bassdrum")), ("snare", ("snare", "sd")), ("clap", ("clap",)),
                 ("hat", ("hat", "hh", "shaker", "cabasa", "maracas")), ("cymbal", ("crash", "ride", "cymbal")),
                 ("perc", ("perc", "tom", "rim", "conga", "bongo", "clave", "cowbell", "tamb")),
                 ("sub", ("sub",)), ("bass", ("bass", "303", "acid", "reese")), ("pad", ("pad", "string", "atmo", "drone")),
                 ("pluck", ("pluck", "arp", "bell", "guitar")), ("keys", ("piano", "key", "organ", "stab", "chord", "rhodes")),
                 ("fx", ("fx", "riser", "noise", "sweep", "impact", "sfx", "trigger")), ("lead", ("lead", "melody", "synth"))]


# -- roles ----------------------------------------------------------------------------------------------
def guess_roles(project: Project) -> dict[str, str]:
    """Mix role per track for projects without a plan file: by name, then plugin, then pitch range."""
    roles = {}
    notes = project.all_notes()
    for track in project.tracks(TRACK_INSTRUMENT):
        lowered = track.name.lower()
        role = next((role for role, words in ROLE_KEYWORDS if any(word in lowered for word in words)), None)
        if role is None and track.plugin == "kicker":
            role = "kick"
        if role is None and track.name in notes:
            median = float(np.median([n.pitch for n in notes[track.name]]))
            lengths = float(np.median([n.length for n in notes[track.name]]))
            role = "bass" if median < 48 else "pad" if lengths >= 4 else "lead"
        roles[track.name] = role or "lead"
    by_keyword = lambda text: next((role for role, words in ROLE_KEYWORDS if any(word in text.lower() for word in words)), None)
    inner = " ".join(project.bb_notes())
    for track in project.tracks(TRACK_BB):          # a Beat/Bassline track is rendered as one stem: usually the drums
        own = None if track.name.lower().startswith(BB_DEFAULT_NAME) else by_keyword(track.name)      # the default name contains "bass"
        roles[track.name] = own or ("kick" if any(word in inner.lower() for word in ("kick", "bassdrum", "bd")) else "perc")
    for track in project.tracks(TRACK_SAMPLE):
        roles[track.name] = by_keyword(track.name) or "fx"
    return roles


def roles_of(project_path: str, project: Project) -> dict[str, dict]:
    """{track name: {'role', 'level_db'}} from the plan file, falling back to guesses."""
    plan = compose.load_plan(project_path)
    guessed = guess_roles(project)
    if plan is None:
        return {name: {"role": role, "level_db": 0.0} for name, role in guessed.items()}
    return {name: plan["parts"].get(name, {"role": guessed[name], "level_db": 0.0}) for name in guessed}


# -- stems ----------------------------------------------------------------------------------------------
def _isolated(project_path: str, keep: int, total_beats: float) -> Project:
    """Copy of the project where only track number `keep` still has clips; mixer, effects and automation stay."""
    project = Project.load(project_path)
    project.mixer.fx(0).el.set("enabled", "0")
    for index, track in enumerate(project.tracks()):
        if index == keep or track.type not in (TRACK_INSTRUMENT, TRACK_SAMPLE):
            continue
        for clip in track.el.findall("pattern") + track.el.findall("sampletco"):
            track.el.remove(clip)
    project.set_length(total_beats)                 # removed clips must not shorten the stem
    return project


def _render_isolated(project_path: str, out_dir: str, only: set[str] | None = None) -> dict[str, str]:
    """One render per track from a copy that holds only that track: far cheaper than soloing, because LMMS
    still synthesizes muted tracks. Renders run side by side. `only` limits the work to the named tracks."""
    project = Project.load(project_path)
    total_beats = project.length_beats()
    wanted = [(i, t.name) for i, t in enumerate(project.tracks()) if t.type in (TRACK_INSTRUMENT, TRACK_SAMPLE)
              and (only is None or t.name in only)]
    stem = os.path.splitext(project_path)[0]
    os.makedirs(out_dir, exist_ok=True)
    for name in os.listdir(out_dir) if only is None else []:      # stems of an earlier arrangement would be mistaken for parts
        if re.fullmatch(r"\d+_.*\.wav", name):
            os.remove(os.path.join(out_dir, name))

    def one(item: tuple[int, str]) -> tuple[str, str]:
        index, name = item
        temporary = f"{stem}.stem{index}-tmp.mmp"       # same folder, so sample paths still resolve
        _isolated(project_path, index, total_beats).save(temporary)
        wav = os.path.join(out_dir, f"{index + 1:02d}_{re.sub(r'[^A-Za-z0-9]+', '_', name)}.wav")
        try:
            render.render(temporary, wav, oversampling=STEM_OVERSAMPLING)
        finally:
            os.remove(temporary)
        return name, wav
    with ThreadPoolExecutor(settings.stem_workers()) as pool:
        return dict(pool.map(one, wanted))


def render_stems(project_path: str, out_dir: str) -> dict[str, str]:
    """Render every track alone with the master effects bypassed; returns {track name: wav path} in project order.

    Bypassing the master chain keeps the stems linear: their levels add up to the pre-master mix
    and do not shift when the limiter is driven harder later.
    """
    project = Project.load(project_path)
    if not any(t.type == TRACK_BB for t in project.tracks()):
        return _render_isolated(project_path, out_dir)
    # Beat/Bassline projects: their instruments live inside the BB container, so let LMMS solo each track itself.
    project.mixer.fx(0).el.set("enabled", "0")
    temporary = os.path.splitext(project_path)[0] + ".stems-tmp.mmp"
    project.save(temporary)
    try:
        paths = render.render_stems(temporary, out_dir)
    finally:
        os.remove(temporary)
    by_index = {int(os.path.basename(p).split("_", 1)[0]): p for p in paths if os.path.basename(p).split("_", 1)[0].isdigit()}
    rendered = [t for t in project.tracks() if t.type in (TRACK_INSTRUMENT, TRACK_BB, TRACK_SAMPLE)]
    return {track.name: by_index[i + 1] for i, track in enumerate(rendered) if i + 1 in by_index}


def measure_stems(stems: dict[str, str]) -> dict[str, dict]:
    result = {}
    for name, path in stems.items():
        x, rate = audio.load(path)
        result[name] = {"path": path, "loudness": audio.active_loudness(x, rate), "peak_db": audio.sample_peak_db(x),
                        "silent": audio.sample_peak_db(x) < -70.0}
    return result


def _anchor(measured: dict, roles: dict) -> str | None:
    for wanted in ("kick", "snare", "bass", "sub"):
        candidates = [n for n in measured if roles.get(n, {}).get("role") == wanted and not measured[n]["silent"]
                      and "trigger" not in n.lower()]
        if candidates:
            return max(candidates, key=lambda n: measured[n]["loudness"])
    alive = [n for n in measured if not measured[n]["silent"]]
    return max(alive, key=lambda n: measured[n]["loudness"]) if alive else None


def level_targets(measured: dict, roles: dict, genre: str | None) -> tuple[str | None, dict[str, float]]:
    """Target active loudness per part, relative to the anchor.

    Every part gets the role's loudness (role level + genre shift + the part's own offset). Percussive roles
    also have a peak ceiling against the kick's peak (same shifts) and take the lower of the two, because a
    loudness meter under-reads short sounds.
    """
    anchor = _anchor(measured, roles)
    if anchor is None:
        return None, {}
    profile = genres.get(genre)
    anchor_role = roles[anchor]["role"]
    if anchor_role in compose.DRUM_ROLES:
        anchor_target = measured[anchor]["loudness"] + (ANCHOR_PEAK_DB - measured[anchor]["peak_db"])
    else:
        anchor_target = ANCHOR_LOUDNESS
    anchor_peak = measured[anchor]["peak_db"] + anchor_target - measured[anchor]["loudness"]

    def offset(name: str) -> float:
        role = roles[name]["role"]
        return (profile["levels"].get(role, compose.LEVEL_OF_ROLE.get(role, -6.0)) + compose.MIX_TASTE.get(role, 0.0)
                + roles[name].get("level_db", 0.0))

    def shift(name: str) -> float:
        """How far this part is meant to sit from its role's standard level (genre and own offset together)."""
        return offset(name) - compose.LEVEL_OF_ROLE.get(roles[name]["role"], -6.0)

    targets = {}
    for name in measured:
        if measured[name]["silent"] or "trigger" in name.lower():
            continue
        targets[name] = anchor_target + offset(name) - offset(anchor)
        ceiling = compose.PEAK_OF_ROLE.get(roles[name]["role"])
        if ceiling is not None and name != anchor and anchor_role in compose.DRUM_ROLES:
            peak_limit = anchor_peak + ceiling + shift(name) - shift(anchor)
            targets[name] = min(targets[name], measured[name]["loudness"] + peak_limit - measured[name]["peak_db"])
    return anchor, targets


def _own_channel(project: Project, name: str) -> int | None:
    """The mixer channel of a track when no other track shares it (0 = master is never 'own')."""
    number = lambda track: int(track.settings.get("fxch", "0")) if track.settings is not None else 0
    track = project.track(name)
    if track.type != TRACK_INSTRUMENT:
        return None
    users = [t for t in project.tracks(TRACK_INSTRUMENT) if number(t) == number(track)]
    return number(track) if number(track) > 0 and len(users) == 1 else None


def apply_level(project: Project, name: str, delta_db: float) -> None:
    """Change a part's level by delta_db. Uses its own mixer fader when it has one: that gain sits after the
    channel effects, so the change is exact; a shared channel falls back to the track volume."""
    factor = 10 ** (delta_db / 20)
    track = project.track(name)
    channel = _own_channel(project, name)
    if channel is not None:
        fader = project.mixer.volume(channel)
        wanted = fader.get() * factor
        fader.set(round(float(np.clip(wanted, MIN_FADER, MAX_FADER)), 4))
        factor = wanted / fader.get()                 # what the fader range could not cover
    if abs(factor - 1.0) > 1e-3:
        track.param("vol").set(round(min(track.param("vol").get() * factor, MAX_TRACK_VOLUME), 2))


def balance(project_path: str, work_dir: str, genre: str | None = None, verify: bool = False, tone_fit: bool = True) -> dict:
    """Set every part's level so its stem sits at the role target. Rewrites the project file.

    One stem pass is enough: fader gain is linear, so the stems are scaled by the same amount
    instead of being rendered again. verify=True renders them again and reports what is left.
    """
    project = Project.load(project_path)
    roles = roles_of(project_path, project)
    stems = render_stems(project_path, os.path.join(work_dir, "stems"))
    measured = measure_stems(stems)
    anchor, targets = level_targets(measured, roles, genre)
    tone = None
    if tone_fit:
        tone = fit_tone(project, stems, roles, genre, {n: targets[n] - measured[n]["loudness"] for n in targets})
        if tone and tone["shelf_db"]:                     # the shelf changed loudness and peaks: set the levels from the lifted stems
            measured = measure_stems(stems)
            anchor, targets = level_targets(measured, roles, genre)
    changes, skipped = {}, []
    for name, target in targets.items():
        delta = target - measured[name]["loudness"]
        if abs(delta) < 0.3:
            continue
        if project.track(name).type != TRACK_INSTRUMENT:
            # Beat/Bassline tracks share their instruments and sample tracks have no mixer channel in LMMS 1.2:
            # their levels are left for the user to set in LMMS.
            skipped.append(f"{name} ({delta:+.1f} dB from its target)")
            continue
        apply_level(project, name, delta)
        x, rate = audio.load(stems[name])
        audio.save(stems[name], x * 10 ** (delta / 20), rate)
        changes[name] = round(delta, 2)
    project.save(project_path)
    result = {"anchor": anchor, "changes_db": changes, "not_adjusted": skipped, "stems": stems, "tone": tone,
              "vocal_presence": fit_vocal_presence(project_path, stems, work_dir)}
    if verify:
        stems = render_stems(project_path, os.path.join(work_dir, "stems"))
        again = measure_stems(stems)
        result["left_db"] = {n: round(targets[n] - again[n]["loudness"], 2) for n in targets if not again[n]["silent"]}
        result["stems"] = stems
    return result


def brightness_shift(genre: str | None) -> float:
    """Dark genres (their profile lowers the 'air' band) are allowed to be that much duller."""
    return genres.get(genre)["bands"].get("air", 0.0)


def fit_tone(project: Project, stems: dict[str, str], roles: dict[str, dict], genre: str | None, gains_db: dict[str, float]) -> dict | None:
    """Brighten a dull mix with one high shelf on the melodic parts, the effects and the vocals.

    gains_db are the level changes the balance is about to make, so the sum of the stems with those gains is the
    mix and the lift can be fitted without rendering: the shelf is applied offline to the densest 20 s until the
    highs reach the reference. Each lifted part is held at its loudness, because the level pass that follows will
    do the same: a part gets brighter without getting louder. Drums and the low end are not touched, which
    keeps the drum peaks and the limiter's work unchanged. The stems are rewritten with the shelf.
    """
    liftable = [n for n in stems if roles[n]["role"] not in TONE_FIXED_ROLES and _own_channel(project, n) is not None]
    if not liftable:
        return None
    # One stem in memory at a time: a long song with many parts does not fit otherwise.
    gain = lambda name: 10 ** (gains_db.get(name, 0.0) / 20)
    mix_sum, rate = None, 44100
    for name, path in stems.items():
        x, rate = audio.load(path)
        size = len(x) if mix_sum is None else min(len(mix_sum), len(x))
        mix_sum = x[:size] * gain(name) if mix_sum is None else mix_sum[:size] + x[:size] * gain(name)
    start, end = audio.loudest_span(mix_sum, rate)
    del mix_sum
    rest, windows = 0.0, []
    for name, path in stems.items():
        window = audio.load(path)[0][start:end] * gain(name)
        if name not in liftable:
            rest = rest + window
        elif audio.sample_peak_db(window) > -70.0:
            windows.append(window)
    if not windows:
        return None
    loudness = [audio.integrated_lufs(w, rate) for w in windows]

    def predicted(gain_db: float) -> float:
        total = rest
        for window, before in zip(windows, loudness):
            lifted = audio.shelf(window, rate, TONE_SHELF_HZ, gain_db, True)
            total = total + lifted * 10 ** ((before - audio.integrated_lufs(lifted, rate)) / 20)
        return audio.brightness_db(total, rate)

    aim, before = BRIGHTNESS_AIM + brightness_shift(genre), predicted(0.0)
    result = {"before_db": round(before, 1), "aim_db": round(aim, 1), "shelf_db": 0.0}
    if before >= aim - TONE_TOLERANCE_DB:
        return result
    low, high = 0.0, MAX_TONE_SHELF_DB
    if predicted(high) > aim:
        for _ in range(6):                                # bisection: brightness rises steadily with the shelf gain
            middle = (low + high) / 2
            low, high = (middle, high) if predicted(middle) < aim else (low, middle)
    gain_db = round(high, 1)
    for name in liftable:
        fx.eq(project.mixer.fx(_own_channel(project, name)), high_shelf=(TONE_SHELF_HZ, gain_db))
        x, _ = audio.load(stems[name])
        audio.save(stems[name], audio.shelf(x, rate, TONE_SHELF_HZ, gain_db, True), rate)
    result.update(shelf_db=gain_db, predicted_db=round(predicted(gain_db), 1), parts=len(liftable))
    return result


def fit_vocal_presence(project_path: str, stems: dict[str, str], work_dir: str) -> dict | None:
    """Lift the lead vocal's presence band until its consonants clear the backing. Rewrites the project file.

    Voices differ by many dB in how much they carry between 1.3 and 5 kHz, so the lift is fitted to the measured
    margin instead of being a fixed EQ setting. Only the vocal stems are rendered again. What the largest lift
    cannot close is left for the vocal checks to report.
    """
    project = Project.load(project_path)
    roles = roles_of(project_path, project)
    leads = [n for n in stems if roles.get(n, {}).get("role") == "vocal" and _own_channel(project, n) is not None]
    backing = [n for n in stems if roles.get(n, {}).get("role") not in ("vocal", "vocal_bg") and "trigger" not in n.lower()]
    if not leads or not backing:
        return None
    (voice, rate), (rest, _) = _sum_stems(stems, leads), _sum_stems(stems, backing)
    margin = presence_db(voice, rest, rate, audio.CONSONANT_BAND)
    if margin is None or margin >= VOCAL_CONSONANT_MARGIN_DB + PRESENCE_SAFETY_DB:
        return None if margin is None else {"margin_db": round(margin, 1), "lift_db": 0.0}
    lift = round(min(VOCAL_CONSONANT_MARGIN_DB + PRESENCE_SAFETY_DB - margin, MAX_PRESENCE_LIFT_DB), 1)
    for name in leads:
        fx.eq(project.mixer.fx(_own_channel(project, name)), peaks=[(PRESENCE_HZ, lift, PRESENCE_OCTAVES)])
    project.save(project_path)
    stems.update(_render_isolated(project_path, os.path.join(work_dir, "stems"), only=set(leads)))
    voice, _ = _sum_stems(stems, leads)
    return {"margin_db": round(margin, 1), "lift_db": lift, "margin_after_db": round(presence_db(voice, rest, rate, audio.CONSONANT_BAND), 1)}


# -- master loudness ----------------------------------------------------------------------------------
def _master_limiter(project: Project):
    for effect in project.mixer.fx(0).effects():
        key = {a.get("name"): a.get("value") for a in effect.findall("key/attribute")}
        if (key.get("file", "").removesuffix(".so"), key.get("plugin")) == LIMITER_KEY:
            return effect
    return None


def trim_true_peak(wav_path: str, ceiling_db: float = TRUE_PEAK_CEILING_DB) -> float:
    """Lower the whole file just enough that its true peak is at the ceiling; returns the gain applied in dB (<= 0).

    The LMMS limiter works on sample peaks, so inter-sample peaks can overshoot by a dB or two.
    """
    x, rate = audio.load(wav_path)
    gain_db = min(0.0, ceiling_db - audio.true_peak_db(x))
    if gain_db < 0:
        audio.save(wav_path, x * 10 ** (gain_db / 20), rate)
    return round(gain_db, 2)


def _window_peaks_db(x: np.ndarray, rate: int) -> np.ndarray:
    """Peak level of every 10 ms window that is not near-silent, in dBFS."""
    size = int(PEAK_WINDOW_S * rate)
    mono_peak = np.abs(x).max(axis=1)
    windows = mono_peak[:len(mono_peak) // size * size].reshape(-1, size).max(axis=1)
    return 20.0 * np.log10(windows[windows > 10 ** (QUIET_WINDOW_DB / 20)])


def master_to_loudness(project_path: str, work_dir: str, target_lufs: float, max_reduction_db: float = MAX_LIMITER_REDUCTION_DB) -> dict:
    """Raise the master limiter's drive toward target_lufs, but only as far as it stays clean. Adds a limiter if none exists.

    The mix is rendered once without the limiter. From that render follow both the drive the target needs and
    the drive at which the limiter would have to cut more than max_reduction_db from the loudest moments
    (their 99.5th percentile). The lower of the two is used: a limiter that works harder than a few dB audibly
    pumps and smears the kick, and a slightly quieter clean master is the better result.
    """
    project = Project.load(project_path)
    limiter = _master_limiter(project)
    if limiter is None:
        limiter = fx.limiter(project.mixer.fx(0))
        project.save(project_path)
    wav, bare_wav = os.path.join(work_dir, "mix.wav"), os.path.join(work_dir, "mix-before-limiter.wav")
    bare = Project.load(project_path)
    bare.mixer.fx(0).el.remove(_master_limiter(bare))
    temporary = os.path.splitext(project_path)[0] + ".nolimiter-tmp.mmp"          # same folder, so sample paths still resolve
    bare.save(temporary)
    try:
        render.render(temporary, bare_wav)
    finally:
        os.remove(temporary)
    x, rate = audio.load(bare_wav)
    os.remove(bare_wav)
    bare_lufs = audio.integrated_lufs(x, rate)
    loud_peak = float(np.percentile(_window_peaks_db(x, rate), REDUCTION_PERCENTILE))
    ceiling = fx.control(limiter, "Limit (dB)").get()
    clean_gain = ceiling + max_reduction_db - loud_peak
    gain = fx.control(limiter, "Input gain (dB)")
    steps = []
    wanted = target_lufs - bare_lufs
    for _ in range(MASTER_PASSES):
        gain.set(round(float(np.clip(min(wanted, clean_gain), *LIMITER_GAIN_RANGE)), 2))
        project.save(project_path)
        render.render(project_path, wav)
        trim = trim_true_peak(wav)
        y, _ = audio.load(wav)
        reached = audio.integrated_lufs(y, rate)
        steps.append({"limiter_gain_db": gain.get(), "true_peak_trim_db": trim, "lufs": round(reached, 2)})
        if abs(target_lufs - reached) <= LOUDNESS_TOLERANCE_LU or gain.get() >= clean_gain - 0.05:
            break
        wanted = gain.get() + (target_lufs - reached)          # limiting and the peak trim cost a little loudness: one correction
    capped = reached < target_lufs - LOUDNESS_TOLERANCE_LU
    reduction = max(0.0, loud_peak + gain.get() - ceiling)
    note = (f"stopped at {reached:.1f} LUFS: reaching {target_lufs:g} would make the limiter cut more than {max_reduction_db:g} dB from the loudest "
            "moments. Lower the peaks that stick out (kick, snare, clap) or thicken the arrangement for a louder clean master") if capped else ""
    return {"target_lufs": target_lufs, "reached_lufs": round(reached, 2), "before_limiter_lufs": round(bare_lufs, 2), "limiter_reduction_db": round(reduction, 1),
            "clean_gain_limit_db": round(clean_gain, 2), "capped": capped, "steps": steps, "wav": wav, "note": note}


def repeat_check(project_path: str, wav_path: str, work_dir: str) -> dict:
    """Render the project once more and compare with wav_path: the same project must give the same audio."""
    second = os.path.join(work_dir, "repeat-check.wav")
    render.render(project_path, second)
    trim_true_peak(second)
    (first, _), (again, _) = audio.load(wav_path), audio.load(second)
    os.remove(second)
    if first.shape == again.shape and np.array_equal(first, again):
        return finding("info", "repeatable", "a second render of the project is identical, sample for sample")
    length = min(len(first), len(again))
    residual = audio.rms_db(first[:length] - again[:length]) - audio.rms_db(first[:length])
    if residual < INAUDIBLE_RESIDUAL_DB:
        return finding("info", "nearly_repeatable", f"a second render differs from the first by a residue {-residual:.0f} dB below the mix, far below hearing. "
                       "LMMS's LB302 synth and some plugins start a render with slightly different internal state; lint names the parts that can do this",
                       residual_db=round(residual, 1))
    return finding("warn", "not_repeatable", f"a second render differs from the first (difference {residual:.0f} dB below the mix): "
                   "run lint for the usual causes (peak controllers, DrumSynth presets, unseeded randomness, or LMMS running on several cores)",
                   residual_db=round(residual, 1))


# -- checks ---------------------------------------------------------------------------------------------
def _band_frames(x: np.ndarray, rate: int, band: tuple[float, float]) -> np.ndarray:
    """Power inside a band for every STFT frame of the mono sum."""
    freqs, _, stft = signal.stft(audio.to_mono(x), rate, nperseg=STFT_SIZE, noverlap=STFT_SIZE - STFT_HOP, boundary=None, padded=False)
    inside = (freqs >= band[0]) & (freqs < band[1])
    return (np.abs(stft[inside]) ** 2).sum(axis=0)


def _sum_stems(stems: dict[str, str], names: list[str]) -> tuple[np.ndarray, int]:
    total, rate = None, 44100
    for name in names:
        x, rate = audio.load(stems[name])
        if total is None:
            total = x.copy()
        else:
            length = min(len(total), len(x))
            total = total[:length] + x[:length]
    return (total if total is not None else np.zeros((1, 2))), rate


def band_margins(front: np.ndarray, back: np.ndarray, rate: int, band: tuple[float, float],
                 sections: list[tuple[str, float, float]] = ()) -> dict | None:
    """How far `front` sits above `back` inside a band while `front` is sounding: over the whole song and per section.

    sections are (name, start s, end s). The result holds 'whole', 'sections' {name: dB} and 'densest', the section
    whose backing is loudest in the band under the sounding frames. One number for the whole song lets a sparse
    verse lift the mean and hide a chorus where the front falls short, so the per-section values are what to read.
    """
    length = min(len(front), len(back))
    a, b = _band_frames(front[:length], rate, band), _band_frames(back[:length], rate, band)
    if not len(a) or a.max() <= 0:
        return None
    active = a > a.max() * 10 ** (-ACTIVE_WINDOW_DB / 10)
    if not active.any():
        return None
    margin = lambda keep: float(10 * np.log10(a[keep].mean() / max(b[keep].mean(), 1e-20)))
    centres = (np.arange(len(a)) * STFT_HOP + STFT_SIZE / 2) / rate
    result = {"whole": margin(active), "sections": {}, "densest": None}
    backing = {}
    for name, start, end in sections:
        keep = active & (centres >= start) & (centres < end)
        if keep.sum() * STFT_HOP >= MIN_VOCAL_SECTION_S * rate:
            result["sections"][name] = margin(keep)
            backing[name] = b[keep].mean()
    if backing:
        result["densest"] = max(backing, key=backing.get)
    return result


def presence_db(front: np.ndarray, back: np.ndarray, rate: int, band: tuple[float, float]) -> float | None:
    """How far `front` sits above `back` inside a band, measured only while `front` is sounding (whole song)."""
    margins = band_margins(front, back, rate, band)
    return None if margins is None else margins["whole"]


def _section_seconds(plan: dict | None) -> list[tuple[str, float, float]]:
    """(name, start s, end s) of every section in the plan file."""
    if not plan or not plan.get("sections"):
        return []
    seconds_per_bar = plan["timesig"][0] * 4.0 / plan["timesig"][1] * 60.0 / plan["bpm"]
    return [(s["name"], s["start_bar"] * seconds_per_bar, (s["start_bar"] + s["bars"]) * seconds_per_bar) for s in plan["sections"]]


def check_master(x: np.ndarray, rate: int, genre: str | None = None, target_lufs: float | None = None) -> list[dict]:
    """Delivery and tonal-balance checks on the rendered mix."""
    profile = genres.get(genre)
    summary = audio.summary(x, rate)
    target = target_lufs if target_lufs is not None else profile["lufs"]
    bands = ", ".join(f"{band} {level:+.1f}" for band, level in summary["bands_db"].items())
    table = [f"{summary['lufs_integrated']} LUFS integrated (target {target}), loudness range {summary['loudness_range_lu']} LU, "
             f"true peak {summary['true_peak_db']} dBTP, crest {summary['crest_db']} dB, length {summary['duration_s']} s",
             f"stereo correlation {summary['stereo_correlation']} (low end {summary['low_end_correlation']}), width {summary['stereo_width']}",
             f"band levels in dB against the whole mix: {bands}",
             f"brightness of the densest 20 s: highs {summary['loud_brightness_db']:+.1f} dB against the mids (pink noise 0, usual analyser reference -4.5)"]
    found = [finding("info", "master_summary", "master measurements", **summary, table=table)]
    if summary["clipped_runs"]:
        found.append(finding("error", "clipping", f"{summary['clipped_runs']} clipped spots: lower the limiter input gain or the loudest part"))
    if summary["true_peak_db"] > TRUE_PEAK_LIMIT_DB:
        found.append(finding("warn", "true_peak", f"true peak {summary['true_peak_db']} dBTP is above {TRUE_PEAK_LIMIT_DB}: lossy encoding may clip; lower the limiter ceiling"))
    if abs(summary["lufs_integrated"] - target) > 1.5:
        found.append(finding("warn", "loudness", f"integrated loudness {summary['lufs_integrated']} LUFS, target {target}: run master_to_loudness"))
    if summary["crest_db"] < MIN_CREST_DB:
        found.append(finding("warn", "over_limited", f"crest factor {summary['crest_db']} dB is below {MIN_CREST_DB}: the limiter is working too hard, reduce its input gain or tame the loudest part"))
    if summary["stereo_correlation"] < 0.0:
        found.append(finding("error", "phase", f"stereo correlation {summary['stereo_correlation']} is negative: parts cancel in mono, reduce widening"))
    if summary["low_end_correlation"] < MIN_LOW_CORRELATION:
        found.append(finding("warn", "wide_low_end", f"low-end correlation {summary['low_end_correlation']}: keep kick and sub mono"))
    if summary["leading_silence_s"] > 0.5:
        found.append(finding("warn", "leading_silence", f"{summary['leading_silence_s']} s of silence before the first sound"))
    if audio.rms_db(x[-int(0.1 * rate):]) > TAIL_CUT_DB:
        found.append(finding("warn", "tail_cut", "the file ends while sound is still ringing: add tail bars (Song.tail_bars) or shorten the reverb"))
    brightness = summary["loud_brightness_db"]
    dull, bright = (limit + brightness_shift(genre) for limit in BRIGHTNESS_RANGE)
    if not dull <= brightness <= bright:
        found.append(finding("warn", "brightness", f"the densest passage is {'dull' if brightness < dull else 'bright'}: highs above 2.8 kHz are {brightness:+.1f} dB "
                             f"against the mids, usual {dull:+.1f} to {bright:+.1f}", brightness=brightness, low=dull, high=bright))
    for band, (low, high) in BAND_TARGETS.items():
        shift = profile["bands"].get(band, 0.0)
        level = summary["bands_db"][band]
        if not low + shift <= level <= high + shift:
            direction = "too strong" if level > high + shift else "too weak"
            found.append(finding("warn", f"band_{band}", f"{band} band is {direction}: {level} dB, usual range {low + shift:.0f} to {high + shift:.0f}",
                                 level=level, low=low + shift, high=high + shift))
    return found


def kick_hiss_db(x: np.ndarray, rate: int) -> float | None:
    """Level of 2-10 kHz against 30-200 Hz in the body of the kick, i.e. from 30 ms after each hit on.

    A clean kick is a low tone after its click: about -60 dB or lower here. Noise or distortion that lasts as
    long as the kick shows as a much higher value and is heard as hiss or fuzz on every beat.
    """
    freqs, _, stft = signal.stft(audio.to_mono(x), rate, nperseg=HISS_FFT, noverlap=HISS_FFT // 2, boundary=None, padded=False)
    power = np.abs(stft) ** 2
    low = power[(freqs >= 30) & (freqs < 200)].sum(axis=0)
    high = power[(freqs >= 2000) & (freqs < 10000)].sum(axis=0)
    if not len(low) or low.max() <= 0:
        return None
    total = low + high
    frames_after_hit = int(np.ceil(HISS_SKIP_S * rate / (HISS_FFT // 2)))
    onset = np.zeros(len(total), dtype=bool)
    floor = total.max() * 1e-6
    onset[1:] = total[1:] > 4.0 * np.maximum(total[:-1], floor)           # a jump of 6 dB starts a hit
    onset[0] = total[0] > floor                                            # a hit on the very first sample
    recent = np.convolve(onset, np.ones(frames_after_hit + 1), mode="full")[:len(onset)] > 0
    body = (low > low.max() * 10 ** (-ACTIVE_WINDOW_DB / 10)) & ~recent
    if body.sum() < 4:
        return None
    return float(10 * np.log10(max(high[body].mean(), 1e-30) / low[body].mean()))


def _consonant_advice(stems: dict[str, str], backing: list[str], role, voice: np.ndarray, rate: int, missing_db: float) -> str:
    """Name the fix that fits what covers the consonants: the music (dipped by Song.duck_for_vocals) or the drums (which it leaves alone)."""
    groups = {"drums": [n for n in backing if role(n) in compose.DRUM_ROLES], "music": [n for n in backing if role(n) not in compose.DRUM_ROLES]}
    margins = {}
    for name, members in groups.items():
        if members:
            margin = presence_db(voice, _sum_stems(stems, members)[0], rate, audio.CONSONANT_BAND)
            if margin is not None:
                margins[name] = margin
    if margins and min(margins, key=margins.get) == "drums":
        return (f"hats, claps and snares own this band under the vocal, so raise the vocal's level_db by about {missing_db:.0f} dB "
                "or thin out the bright drums while it sings")
    return (f"raise presence_db in Song.duck_for_vocals by about {missing_db / PRESENCE_BAND_SHARE:.0f} dB, "
            "or lower the bright parts under the vocal")


def check_stems(stems: dict[str, str], roles: dict[str, dict], genre: str | None = None, plan: dict | None = None) -> list[dict]:
    """Part-balance checks from solo stems: role levels, kick and vocal presence, drums against the rest, masking.

    plan (the song's plan file) gives the sections, so the vocal margins are also reported per section.
    """
    found = []
    measured = measure_stems(stems)
    alive = [n for n in stems if not measured[n]["silent"] and "trigger" not in n.lower()]
    role = lambda name: roles.get(name, {}).get("role", "lead")
    anchor, targets = level_targets(measured, roles, genre)
    table = {n: {"role": role(n), "loudness": round(measured[n]["loudness"], 1), "target": round(targets[n], 1),
                 "off_by": round(measured[n]["loudness"] - targets[n], 1), "peak_db": round(measured[n]["peak_db"], 1)} for n in alive if n in targets}
    rows = [f"{name:16s} {row['role']:8s} {row['loudness']:6.1f} LUFS while playing, target {row['target']:6.1f} ({row['off_by']:+.1f}), peak {row['peak_db']:6.1f} dBFS"
            for name, row in table.items()]
    found.append(finding("info", "part_levels", f"part loudness against role targets (anchor: {anchor})", parts=table, table=rows))
    for name, row in table.items():
        if abs(row["off_by"]) > LEVEL_TOLERANCE_LU * 2:
            word = "louder" if row["off_by"] > 0 else "quieter"
            found.append(finding("warn", "part_level", f"'{name}' ({row['role']}) is {abs(row['off_by'])} LU {word} than its role target; run balance or set level_db on purpose"))

    if table:
        loudest = max(row["loudness"] for row in table.values())
        buried = [f"{name} ({row['loudness'] - loudest:+.0f} LU)" for name, row in table.items() if row["loudness"] < loudest - BURIED_LU]
        if buried:
            found.append(finding("warn", "part_buried", f"{len(buried)} part(s) sit more than {BURIED_LU:g} LU under the loudest part and will hardly be heard: "
                                 "raise them (level_db) or remove them", examples=buried))
    kicks = [n for n in alive if role(n) == "kick"]
    others = lambda excluded: [n for n in alive if n not in excluded]
    if kicks and others(kicks):
        front, rate = _sum_stems(stems, kicks)
        back, _ = _sum_stems(stems, others(kicks))
        margin = presence_db(front, back, rate, audio.KICK_BAND)
        if margin is not None:
            severity = "warn" if margin < KICK_MARGIN_DB else "info"
            found.append(finding(severity, "kick_presence", f"kick sits {margin:+.1f} dB against everything else in {audio.KICK_BAND} Hz at its hits"
                                 + (" - it is buried: lower or high-pass the bass, deepen the sidechain, or raise the kick" if severity == "warn" else ""),
                                 margin_db=round(margin, 1)))
    for name in kicks:
        x, rate = audio.load(stems[name])
        hiss = kick_hiss_db(x, rate)
        if hiss is not None and hiss > KICK_HISS_LIMIT_DB:
            found.append(finding("warn", "kick_hiss", f"'{name}' carries noise or distortion through its whole body (2-10 kHz is only {-hiss:.0f} dB under "
                                 "its low end 30 ms after the hit; a clean kick is 60 dB or more under). It is heard as hiss or fuzz on every beat. "
                                 "Right for a distorted hardcore kick, wrong for most others: pick a cleaner kick", hiss_db=round(hiss, 1)))
    drums = [n for n in alive if role(n) in compose.DRUM_ROLES]
    rest = [n for n in alive if role(n) not in compose.DRUM_ROLES]
    if drums and rest:
        (d, rate), (r, _) = _sum_stems(stems, drums), _sum_stems(stems, rest)
        gap = audio.active_loudness(d, rate) - audio.active_loudness(r, rate)
        low, high = DRUMS_VS_REST_RANGE_LU
        severity = "warn" if not low <= gap <= high else "info"
        hint = " - the beat is buried under the music" if gap < low else " - the beat swamps the music" if gap > high else ""
        found.append(finding(severity, "drums_vs_rest", f"drums are {gap:+.1f} LU against all other parts (usual {low:+.0f} to {high:+.0f}){hint}", gap_lu=round(gap, 1)))

    vocals = [n for n in alive if role(n) == "vocal"]
    backing = [n for n in alive if role(n) not in ("vocal", "vocal_bg")]
    if vocals and backing:
        (v, rate), (b, _) = _sum_stems(stems, vocals), _sum_stems(stems, backing)
        sections = _section_seconds(plan)
        for code, band, need in (("vocal_body", audio.VOCAL_BODY_BAND, VOCAL_BODY_MARGIN_DB),
                                 ("vocal_consonants", audio.CONSONANT_BAND, VOCAL_CONSONANT_MARGIN_DB)):
            margins = band_margins(v, b, rate, band, sections)
            if margins is None:
                continue
            margin, densest = margins["whole"], margins["densest"]
            # The floor is judged over the whole song; the ceiling where the backing is densest (usually a chorus),
            # because a sparse verse lifts the whole-song value and would call a vocal 'too loud' that the chorus still covers.
            ceiling_margin = margins["sections"][densest] if densest else margin
            severity = "warn" if margin < need or ceiling_margin > VOCAL_MAX_MARGIN_DB else "info"
            hint = (" - words will be hard to follow: " + _consonant_advice(stems, backing, role, v, rate, need - margin)
                    if margin < need and code == "vocal_consonants" else " - the voice is covered: lower pads and leads under it or raise the vocal" if margin < need
                    else " - the vocal towers over the music: lower it or fill the backing" if ceiling_margin > VOCAL_MAX_MARGIN_DB else "")
            where = f", {ceiling_margin:+.1f} dB in the densest section {densest} (at most {VOCAL_MAX_MARGIN_DB:+.0f} there)" if densest else ""
            rows = [f"{name:14s} {value:+6.1f} dB" + (" (densest)" if name == densest else "") for name, value in margins["sections"].items()]
            found.append(finding(severity, code, f"lead vocal is {margin:+.1f} dB against the backing in {band[0]}-{band[1]} Hz (need {need:+.0f} or more){where}{hint}",
                                 margin_db=round(margin, 1), densest_section=densest, densest_margin_db=round(ceiling_margin, 1),
                                 sections={name: round(value, 1) for name, value in margins["sections"].items()}, table=rows))

    spectra = {}
    for name in alive:
        x, rate = audio.load(stems[name])
        freqs, power = audio.spectrum(x, rate)
        spectra[name] = {band: audio.power_db(audio.band_power(freqs, power, low, high)) for band, (low, high) in audio.BANDS.items()}
    clashes = []
    for band in audio.BANDS:
        ranked = sorted(alive, key=lambda n: -spectra[n][band])[:3]
        if len(ranked) >= 2 and spectra[ranked[0]][band] - spectra[ranked[1]][band] < MASK_WINDOW_DB and spectra[ranked[0]][band] > -50:
            clashes.append({"band": band, "parts": ranked[:2], "levels_db": [round(spectra[n][band], 1) for n in ranked[:2]]})
    rows = [f"{clash['band']:9s} {clash['parts'][0]} ({clash['levels_db'][0]} dB) and {clash['parts'][1]} ({clash['levels_db'][1]} dB)" for clash in clashes]
    found.append(finding("info", "band_owners", "bands where the two strongest parts are within a few dB of each other (they can mask each other; decide which one owns the band)",
                         clashes=clashes, table=rows))
    return found


def check_sections(x: np.ndarray, rate: int, plan: dict | None) -> list[dict]:
    """Loudness per section, so the energy curve can be compared with the intended arrangement."""
    if not plan or not plan.get("sections"):
        return []
    seconds_per_bar = plan["timesig"][0] * 4.0 / plan["timesig"][1] * 60.0 / plan["bpm"]
    rows = []
    for section in plan["sections"]:
        start, end = int(section["start_bar"] * seconds_per_bar * rate), int((section["start_bar"] + section["bars"]) * seconds_per_bar * rate)
        piece = x[start:end]
        rows.append({"section": section["name"], "lmms_bar": section["start_bar"] + 1, "bars": section["bars"],
                     "lufs": round(audio.integrated_lufs(piece, rate), 1) if len(piece) > rate else None,
                     "centroid_hz": round(audio.spectral_centroid(piece, rate)) if len(piece) > rate else None})
    table = [f"{row['section']:14s} from bar {row['lmms_bar']:3d}, {row['bars']:3d} bars: {row['lufs']} LUFS, brightness centre {row['centroid_hz']} Hz" for row in rows]
    return [finding("info", "section_energy", "loudness and brightness per section: peaks should fall where the arrangement intends", sections=rows, table=table)]
