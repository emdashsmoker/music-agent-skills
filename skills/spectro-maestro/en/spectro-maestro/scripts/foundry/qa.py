# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
# Part of Spectro Maestro. See LICENSE and THIRD-PARTY-NOTICES.md at the root of the skill.
"""Measurements of a rendered song, and the findings drawn from them.

The model cannot hear the mix, so every judgement a mix engineer makes by ear is restated here as
a number with a plain-language finding. Thresholds are starting points from common practice;
a finding is a prompt to look at the plots and decide, not an automatic verdict."""
from __future__ import annotations

import numpy as np
from scipy import signal, stats

from . import dsp
from .dsp import SR

BANDS = {"sub": (20, 60), "bass": (60, 250), "low_mid": (250, 500), "mid": (500, 2000), "high_mid": (2000, 6000),
         "high": (6000, 16000)}
VOCAL_BODY, VOCAL_CONSONANT = (300.0, 3400.0), (1300.0, 5000.0)
KICK_BAND = (40.0, 120.0)
ENDING_BEFORE_S, ENDING_AFTER_S = 0.5, (0.1, 0.4)
ENDING_LOUD_RANGE_DB = 20.0     # the last half second counts as playing when it is within this range of the song's level
MIN_SUNG_FRAMES, MIN_SUNG_SHARE = 40, 0.08      # 50 ms frames: at least 2 s and 8 % of a section must be sung to judge it

# name: (low, high) acceptable range. Genre profiles may override any of them under `qa:`.
THRESHOLDS = {
    "true_peak_db": (-99.0, -0.3),
    "crest_db": (6.0, 16.0),                # below: squashed, above: limp or one spike dominating
    "limiter_p95_db": (0.0, 5.0),           # sustained limiting beyond this audibly pumps and distorts
    "slope_db_per_octave": (-4.5, -0.7),    # tilt of third-octave band levels, 80 Hz..8 kHz
    "low_share_db": (-9.0, -1.5),           # energy below 120 Hz relative to the whole mix
    "high_share_db": (-30.0, -11.0),        # energy above 6 kHz relative to the whole mix
    "correlation": (0.2, 1.0),
    "mono_loss_db": (-3.0, 0.5),
    "low_correlation": (0.8, 1.0),          # bass must survive mono playback
    "drums_vs_rest_db": (-5.0, 7.0),        # drum bus loudness against everything else while drums play
    "kick_vs_bass_db": (-3.0, 40.0),        # in the kick band at kick hits: negative means the bass covers the kick
    "vocal_body_db": (0.0, 12.0),           # vocal against backing, 300..3400 Hz, while singing
    "vocal_consonant_db": (2.0, 14.0),      # same in 1.3..5 kHz where consonants are read
    "energy_rank_correlation": (0.5, 1.0),  # planned section energy against measured loudness
    "ending_drop_db": (-99.0, 18.0),        # level just before the last bar line against just after it
}


def _band_power(mono: np.ndarray, band: tuple) -> float:
    sos = signal.butter(4, band, btype="bandpass", fs=SR, output="sos")
    return float(np.mean(signal.sosfilt(sos, mono) ** 2))


def _db(power: float) -> float:
    return float(10.0 * np.log10(max(power, 1e-14)))


def third_octave_spectrum(x: np.ndarray) -> tuple:
    """Long-term average level per third-octave band: (centre_hz, level_db)."""
    freqs, psd = signal.welch(dsp.to_mono(x), SR, nperseg=8192)
    centres = 1000.0 * 2.0 ** (np.arange(-17, 13) / 3.0)          # 20 Hz .. 16 kHz
    levels = []
    for centre in centres:
        low, high = centre / 2 ** (1 / 6), centre * 2 ** (1 / 6)
        chosen = (freqs >= low) & (freqs < high)
        levels.append(_db(np.sum(psd[chosen]) * (freqs[1] - freqs[0])) if chosen.any() else -140.0)
    return centres, np.array(levels)


def spectral_slope(x: np.ndarray) -> float:
    centres, levels = third_octave_spectrum(x)
    chosen = (centres >= 80) & (centres <= 8000)
    return float(np.polyfit(np.log2(centres[chosen]), levels[chosen], 1)[0])


def _frames(x: np.ndarray, seconds: float = 0.05) -> np.ndarray:
    """Mean-square level per short frame (mono)."""
    mono = dsp.to_mono(x)
    hop = int(seconds * SR)
    count = len(mono) // hop
    return np.mean(mono[:count * hop].reshape(count, hop) ** 2, axis=1) if count else np.zeros(0)


def _band_frames(x: np.ndarray, band: tuple, seconds: float = 0.05) -> np.ndarray:
    sos = signal.butter(4, band, btype="bandpass", fs=SR, output="sos")
    return _frames(signal.sosfilt(sos, dsp.to_mono(x)), seconds)


def _section_slices(project: dict) -> list:
    spb = 60.0 / project["meta"]["bpm"]
    meter = project["meta"]["meter"]
    return [(s, int(s["start"] * spb * SR), int((s["start"] + s["bars"] * meter) * spb * SR)) for s in project["sections"]]


def measure(project: dict, rendered: dict) -> dict:
    """All numbers. `rendered` is the dict returned by mixer.render."""
    master, buses = rendered["master"], rendered["buses"]
    mono = dsp.to_mono(master)
    peak = float(np.max(np.abs(master)))
    rms = float(np.sqrt(np.mean(master ** 2)))
    total = float(np.mean(mono ** 2)) + 1e-14
    blocks = {"master": dsp.block_loudness(master), **{name: dsp.block_loudness(bus) for name, bus in buses.items()}}
    hop = int(dsp.LUFS_HOP_S * SR)
    short_term = dsp.block_loudness(master, SR, 3.0, 1.0)
    active = short_term[short_term > -60]
    left, right = master[:, 0], master[:, 1]
    low_sos = signal.butter(4, 120, btype="lowpass", fs=SR, output="sos")
    low = signal.sosfilt(low_sos, master, axis=0)
    out = {
        "duration_s": round(len(master) / SR, 2),
        "lufs": round(dsp.lufs_of_blocks(blocks["master"]), 2),
        "true_peak_db": rendered["report"]["master"].get("true_peak_db") or round(dsp.true_peak_db(master), 2),
        "crest_db": round(float(dsp.lin_to_db(peak) - dsp.lin_to_db(rms)), 2),
        "loudness_range_lu": round(float(np.percentile(active, 95) - np.percentile(active, 10)), 2) if len(active) else 0.0,
        "clipped_samples": int(np.sum(np.abs(master) >= 0.9999)),
        "dc_offset": round(float(np.abs(master.mean())), 6),
        "correlation": round(float(np.corrcoef(left, right)[0, 1]), 3),
        "low_correlation": round(float(np.corrcoef(low[:, 0], low[:, 1])[0, 1]), 3),
        "mono_loss_db": round(dsp.integrated_lufs(np.stack([mono, mono], axis=1)) - dsp.integrated_lufs(master), 2),
        "slope_db_per_octave": round(spectral_slope(master), 2),
        "bands_db": {name: round(_db(_band_power(mono, band) / total), 2) for name, band in BANDS.items()},
    }
    out["low_share_db"] = round(_db(float(np.mean(signal.sosfilt(low_sos, mono) ** 2)) / total), 2)
    out["high_share_db"] = out["bands_db"]["high"]
    out["limiter_p95_db"] = rendered["report"]["master"]["limiter_p95_db"]
    out["start_peak_db"] = round(float(dsp.lin_to_db(np.max(np.abs(master[:441])))), 1)
    out["end_level_db"] = round(float(dsp.lin_to_db(np.sqrt(np.mean(master[-4410:] ** 2)))), 1)

    # --- sections: does the arrangement deliver the planned energy?
    sections = []
    for section, a, b in _section_slices(project):
        part = master[a:b]
        if len(part) < SR // 2:
            continue
        freqs, psd = signal.welch(dsp.to_mono(part), SR, nperseg=4096)
        row = {"name": section["name"], "type": section["type"], "energy": section["energy"],
               "lufs": round(dsp.lufs_of_blocks(blocks["master"][a // hop:max(a // hop + 1, b // hop - 3)]), 2),
               "centroid_hz": round(float(np.sum(freqs * psd) / (np.sum(psd) + 1e-20))),
               "buses_lufs": {name: value for name, value in (
                   (name, round(dsp.loud_part_of_blocks(blocks[name][a // hop:max(a // hop + 1, b // hop - 3)]), 1))
                   for name in buses) if value > -69.0}}
        sections.append(row)
    out["sections"] = sections
    if len(sections) >= 3 and len({s["energy"] for s in sections}) > 1:
        out["energy_rank_correlation"] = round(float(stats.spearmanr([s["energy"] for s in sections],
                                                                     [s["lufs"] for s in sections])[0]), 2)

    # --- drums against the rest
    if "drums" in buses:
        rest = sum(bus for name, bus in buses.items() if name != "drums")
        if np.any(rest):
            drum_f, rest_f = _frames(buses["drums"], 0.4), _frames(rest, 0.4)
            both = (drum_f > 1e-7) & (rest_f > 1e-7)
            if both.sum() > 4:
                out["drums_vs_rest_db"] = round(_db(np.mean(drum_f[both])) - _db(np.mean(rest_f[both])), 2)
    # --- kick against bass in the low band, measured at kick hits
    kick_notes = [n[0] for t in project["tracks"] if t.get("role") == "kick" for n in t["notes"]]
    if kick_notes and "bass" in buses and "drums" in buses:
        spb = 60.0 / project["meta"]["bpm"]
        drum_low, bass_low = _band_frames(buses["drums"], KICK_BAND, 0.02), _band_frames(buses["bass"], KICK_BAND, 0.02)
        index = np.unique(np.clip((np.array(kick_notes) * spb / 0.02).astype(int)[:, None] + np.arange(0, 4), 0,
                                  len(drum_low) - 1))
        if np.mean(bass_low[index]) > 1e-9:
            out["kick_vs_bass_db"] = round(_db(np.mean(drum_low[index])) - _db(np.mean(bass_low[index])), 2)
    # --- vocal against backing
    if "vocals" in buses:
        backing = sum(bus for name, bus in buses.items() if name != "vocals")
        singing = _frames(buses["vocals"]) > 10 ** (-45 / 10)
        if singing.sum() > 10 and np.any(backing):
            for key, band in (("vocal_body_db", VOCAL_BODY), ("vocal_consonant_db", VOCAL_CONSONANT)):
                vocal_band, backing_band = _band_frames(buses["vocals"], band), _band_frames(backing, band)
                out[key] = round(_db(np.mean(vocal_band[singing])) - _db(np.mean(backing_band[singing])), 2)
            out["vocal_by_section"] = []
            for section, a, b in _section_slices(project):
                fa, fb = a // int(0.05 * SR), b // int(0.05 * SR)
                chosen = singing[fa:fb]
                if chosen.sum() > max(MIN_SUNG_FRAMES, MIN_SUNG_SHARE * len(chosen)):     # a tail ringing into the next section is not singing
                    vocal_band = _band_frames(buses["vocals"][a:b], VOCAL_CONSONANT)
                    backing_band = _band_frames(backing[a:b], VOCAL_CONSONANT)
                    m = min(len(vocal_band), len(chosen))
                    out["vocal_by_section"].append({"name": section["name"], "consonant_db": round(
                        _db(np.mean(vocal_band[:m][chosen[:m]])) - _db(np.mean(backing_band[:m][chosen[:m]])), 2)})
    # --- how the song ends: a full-level last bar followed by nothing is heard as the music being cut off
    spb = 60.0 / project["meta"]["bpm"]
    song_end = int(project["meta"]["beats"] * spb * SR)
    before = mono[max(0, song_end - int(ENDING_BEFORE_S * SR)):song_end]
    after = mono[song_end + int(ENDING_AFTER_S[0] * SR):song_end + int(ENDING_AFTER_S[1] * SR)]
    if len(before) and _db(float(np.mean(before ** 2))) > _db(total) - ENDING_LOUD_RANGE_DB:      # a faded ending is not a stop
        out["ending_drop_db"] = round(_db(float(np.mean(before ** 2))) - (_db(float(np.mean(after ** 2))) if len(after) else -140.0), 1)
    # --- unexpected silence inside the song
    level = _frames(master, 0.1)
    song_frames = int(project["meta"]["beats"] * spb / 0.1)
    quiet = level[:song_frames] < 10 ** (-55 / 10)
    gaps, run = [], 0
    for index, flag in enumerate(np.append(quiet, False)):
        if flag:
            run += 1
        else:
            if run * 0.1 >= 2 * spb and index < len(quiet):       # a quiet run reaching the last bar is a fade, not a hole
                gaps.append([round((index - run) * 0.1, 1), round(run * 0.1, 1)])
            run = 0
    out["silences_s"] = gaps
    return out


EXPLAIN = {
    "true_peak_db": ("inter-sample peaks exceed the ceiling", "lower master ceiling or reduce master gain"),
    "crest_db": ("dynamics are {side}: {low} means over-compressed, {high} means spiky or under-filled",
                 "ease the master target / tame the loudest transient, or fill the arrangement"),
    "limiter_p95_db": ("the limiter works hard most of the time", "lower master lufs target or rebalance the loudest bus"),
    "slope_db_per_octave": ("overall tone is {side}: {low} means dull or bass-heavy, {high} means thin or harsh",
                            "adjust bus balance first, then master eq (tilt)"),
    "low_share_db": ("low end (<120 Hz) is {side} against the full mix", "trim kick/bass/sub levels or their decay"),
    "high_share_db": ("top end (>6 kHz) is {side}", "trim hats/cymbals/noise or open/close filters on leads and pads"),
    "correlation": ("stereo image is out of phase in places", "reduce width or chorus on wide pads and leads"),
    "mono_loss_db": ("the mix loses level in mono", "narrow the widest layer"),
    "low_correlation": ("bass is not mono-compatible", "keep bass and kick mono (mix.mono: true)"),
    "drums_vs_rest_db": ("drums are {side} against the other buses: {low} means the beat is buried, {high} means it swallows the mix",
                         "trim drum roles (mix.gain_db) or the music bus, check sidechain depth"),
    "kick_vs_bass_db": ("kick and bass fight for the low band ({side})", "raise sidechain duck on the bass, shorten its notes at kick hits, or retune"),
    "vocal_body_db": ("vocal body is {side} against the backing: {low} means buried, {high} means detached",
                      "trim vocal gain_db; thin pads and leads under the vocal"),
    "vocal_consonant_db": ("consonant band of the vocal is {side} against the backing: {low} means words get masked",
                           "deepen master.vocal_carve, thin leads/hats in vocal sections, or add presence on the vocal"),
    "ending_drop_db": ("the song stops dead: the last bar plays at full level and almost nothing rings on after it",
                       "add `ending: hit` (a final held chord) or `ending: fade` to the song, or write a closing "
                       "section of your own that thins out"),
    "energy_rank_correlation": ("measured section loudness does not follow the planned energy curve",
                                "compare sections in the overview plot; thin the quiet sections or strengthen the drops"),
}


VOCAL_WINDOW_KEYS = ("vocal_body_db", "vocal_consonant_db")


def thresholds_for(profile_qa: dict | None, vocal_window_shift: float = 0.0) -> dict:
    """The QA limits in force: the defaults, the genre profile's overrides, and the vocal windows moved by the mix
    style's shift (a forward style expects more vocal, a blended one less)."""
    limits = {**THRESHOLDS, **(profile_qa or {})}
    for key in VOCAL_WINDOW_KEYS:
        low, high = limits[key]
        limits[key] = (low + vocal_window_shift, high + vocal_window_shift)
    return limits


def findings(metrics: dict, thresholds: dict | None = None) -> list:
    """Turn out-of-range metrics into findings: [{'key', 'value', 'range', 'message', 'try'}].
    thresholds are the limits in force (thresholds_for), else the defaults."""
    limits = {**THRESHOLDS, **(thresholds or {})}
    out = []
    for key, (low, high) in limits.items():
        value = metrics.get(key)
        if value is None or low <= value <= high:
            continue
        side = "low" if value < low else "high"
        message, advice = EXPLAIN.get(key, ("out of range", ""))
        out.append({"key": key, "value": value, "range": [low, high], "side": side,
                    "message": message.format(side=side, low="low", high="high"), "try": advice})
    if metrics.get("clipped_samples"):
        out.append({"key": "clipped_samples", "value": metrics["clipped_samples"], "range": [0, 0], "side": "high",
                    "message": "samples at full scale", "try": "lower the master ceiling"})
    if metrics.get("silences_s"):
        out.append({"key": "silences_s", "value": metrics["silences_s"], "range": [], "side": "high",
                    "message": "silent stretches inside the song ([start_s, length_s])",
                    "try": "intended breaks are fine; otherwise check the section's play list"})
    for row in metrics.get("vocal_by_section", []):
        if row["consonant_db"] < limits["vocal_consonant_db"][0]:
            out.append({"key": "vocal_consonant_db@" + row["name"], "value": row["consonant_db"],
                        "range": list(limits["vocal_consonant_db"]), "side": "low",
                        "message": f"vocal consonants are masked in section {row['name']}",
                        "try": "thin the backing in this section or lift the vocal there"})
    return out
