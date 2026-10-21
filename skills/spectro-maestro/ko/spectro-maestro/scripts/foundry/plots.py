# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
# Part of Spectro Maestro. See LICENSE and THIRD-PARTY-NOTICES.md at the root of the skill.
"""Pictures of the song for visual review: what a producer checks on meters and analysers.

Every figure answers one question; the caption line at the top of each function states it.
One blue family for data, one orange accent for what needs attention."""
from __future__ import annotations

import os

import logging

import matplotlib
matplotlib.use("Agg")
logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)     # bold math fonts are not needed here
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager
from scipy import signal

from . import dsp, qa, theory, world
from .dsp import SR

BLUE, ACCENT, GREY, DARK = "#6B8EC2", "#F5A962", "#B8C4D6", "#2F4468"
BUS_SHADES = {"drums": "#2F4468", "bass": "#4A6FA5", "music": "#6B8EC2", "vocals": "#F5A962", "fx": "#B8C4D6"}
_FONT = next((f.name for f in font_manager.fontManager.ttflist if "NanumGothic" in f.name), "DejaVu Sans")
plt.rcParams.update({"font.family": _FONT, "font.size": 12, "font.weight": "bold", "axes.labelweight": "bold",
                     "axes.spines.top": False, "axes.spines.right": False, "axes.grid": False,
                     "figure.facecolor": "white", "axes.facecolor": "white", "savefig.dpi": 110})


def _save(fig, path: str) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def _section_marks(ax, project: dict, labels: bool = True, y: float = 1.01) -> None:
    spb = 60.0 / project["meta"]["bpm"]
    for section in project["sections"]:
        start = section["start"] * spb
        ax.axvline(start, color=GREY, lw=0.8)
        if labels:
            ax.text(start, y, " " + section["name"], transform=ax.get_xaxis_transform(), fontsize=10, color=DARK,
                    rotation=30, ha="left", va="bottom")


def overview(project: dict, rendered: dict, path: str) -> str:
    """Does the level follow the planned energy of each section, and which bus carries it?"""
    master = rendered["master"]
    seconds = len(master) / SR
    fig, axes = plt.subplots(3, 1, figsize=(15, 9.5), sharex=True, gridspec_kw={"height_ratios": [1.1, 1, 1]})
    hop = max(1, len(master) // 3000)
    count = len(master) // hop
    mono = dsp.to_mono(master)[:count * hop].reshape(count, hop)
    t = np.arange(count) * hop / SR
    axes[0].fill_between(t, mono.min(axis=1), mono.max(axis=1), color=BLUE, lw=0)
    axes[0].set_ylim(-1.05, 1.05)
    axes[0].set_ylabel("waveform")
    _section_marks(axes[0], project)
    loud = dsp.block_loudness(master, SR, 3.0, 0.5)
    lt = np.arange(len(loud)) * 0.5 + 1.5
    axes[1].plot(lt, loud, color=DARK, lw=1.8)
    axes[1].set_ylim(max(-45, np.percentile(loud, 2) - 3), max(loud) + 2)
    axes[1].set_ylabel("short-term LUFS")
    plan = axes[1].twinx()
    spb = 60.0 / project["meta"]["bpm"]
    for section in project["sections"]:
        a, b = section["start"] * spb, (section["start"] + section["bars"] * project["meta"]["meter"]) * spb
        plan.plot([a, b], [section["energy"]] * 2, color=ACCENT, lw=3, solid_capstyle="butt")
    plan.set_ylim(0, 1.05)
    plan.set_ylabel("planned energy", color=ACCENT)
    plan.spines["right"].set_visible(True)
    _section_marks(axes[1], project, False)
    for name, bus in rendered["buses"].items():
        level = dsp.block_loudness(bus, SR, 3.0, 0.5)
        axes[2].plot(np.arange(len(level)) * 0.5 + 1.5, np.where(level > -60, level, np.nan), color=BUS_SHADES.get(name, BLUE),
                     lw=2.2 if name == "vocals" else 1.6, label=name)
    axes[2].set_ylabel("bus LUFS")
    axes[2].set_xlabel("time (s)")
    axes[2].legend(loc="lower center", ncol=5, frameon=False, fontsize=11)
    _section_marks(axes[2], project, False)
    axes[2].set_xlim(0, seconds)
    return _save(fig, path)


def spectrogram(audio: np.ndarray, path: str, project: dict | None = None, top_hz: float = 16000.0,
                seconds: tuple | None = None) -> str:
    """Where is the energy in frequency over time: holes, harsh bands, filter sweeps, masking?"""
    mono = dsp.to_mono(audio)
    offset = 0.0
    if seconds:
        offset = seconds[0]
        mono = mono[int(seconds[0] * SR):int(seconds[1] * SR)]
    nper = 4096
    hop = max(512, len(mono) // 2400)
    freqs, times, spec = signal.stft(mono, SR, nperseg=nper, noverlap=nper - hop, boundary=None)
    level = 20 * np.log10(np.abs(spec) + 1e-7)
    edges = np.geomspace(30.0, top_hz, 181)
    centres = np.sqrt(edges[:-1] * edges[1:])
    # Low bands are narrower than one analysis bin: those rows are read between the two nearest bins,
    # otherwise the low end of the picture would show empty stripes that are not in the music.
    position = np.clip(centres / freqs[1], 0, len(freqs) - 2)
    below = np.floor(position).astype(int)
    between = (1.0 - (position - below))[:, None] * level[below] + (position - below)[:, None] * level[below + 1]
    rows = np.stack([level[(freqs >= lo) & (freqs < hi)].max(axis=0) if ((freqs >= lo) & (freqs < hi)).any() else between[i]
                     for i, (lo, hi) in enumerate(zip(edges[:-1], edges[1:]))])
    fig, ax = plt.subplots(figsize=(15, 6.5))
    top = np.percentile(rows, 99.5)
    ax.pcolormesh(times + offset, centres, rows, cmap="Blues", vmin=top - 70, vmax=top,
                  shading="nearest")
    ax.set_yscale("log")
    ax.set_yticks([50, 100, 200, 500, 1000, 2000, 5000, 10000], ["50", "100", "200", "500", "1k", "2k", "5k", "10k"])
    ax.set_ylabel("frequency (Hz)")
    ax.set_xlabel("time (s)")
    if project and not seconds:
        _section_marks(ax, project)
    return _save(fig, path)


def spectrum(rendered: dict, path: str, slope_range: tuple = qa.THRESHOLDS["slope_db_per_octave"]) -> str:
    """Is the tonal balance inside the usual corridor, and which bus owns each band?"""
    fig, ax = plt.subplots(figsize=(13, 6.5))
    centres, levels = qa.third_octave_spectrum(rendered["master"])
    pivot = np.interp(1000.0, centres, levels)
    octaves = np.log2(centres / 1000.0)
    shade = (centres >= 80) & (centres <= 8000)
    ax.fill_between(centres[shade], (pivot + slope_range[0] * octaves)[shade] - 3, (pivot + slope_range[1] * octaves)[shade] + 3,
                    color=GREY, alpha=0.35, lw=0)
    for name, bus in rendered["buses"].items():
        c, l = qa.third_octave_spectrum(bus)
        ax.plot(c, l, color=BUS_SHADES.get(name, BLUE), lw=1.6)
        peak = int(np.argmax(l))
        ax.text(c[peak], l[peak] + 0.8, name, color=BUS_SHADES.get(name, BLUE), fontsize=12, ha="center")
    ax.plot(centres, levels, color="black", lw=2.6)
    ax.text(centres[-1], levels[-1], " master", fontsize=12, va="center")
    ax.set_xscale("log")
    ax.set_xticks([31, 63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000],
                  ["31", "63", "125", "250", "500", "1k", "2k", "4k", "8k", "16k"])
    ax.set_xlim(20, 22000)
    ax.set_ylim(levels.max() - 55, levels.max() + 6)
    ax.set_xlabel("third-octave band (Hz)")
    ax.set_ylabel("level (dB)")
    return _save(fig, path)


def arrangement(project: dict, path: str) -> str:
    """Which track plays where: is every section populated as planned, are entries and exits clean?"""
    tracks = [t for t in project["tracks"] if t["notes"] or t.get("lines")]
    order = {"drums": 0, "synth": 1, "vocal": 2}
    tracks.sort(key=lambda t: (order.get(t.get("kind"), 1), t.get("role", ""), t["name"]))
    meter, total = project["meta"]["meter"], project["meta"]["beats"]
    bars = int(np.ceil(total / meter))
    grid = np.zeros((len(tracks), bars))
    for row, track in enumerate(tracks):
        spans = [(n[0], n[1]) for n in track["notes"]]
        spans += [(line["start"] + n[0], n[1]) for line in track.get("lines", []) for n in line["notes"]]
        counts = np.zeros(bars)
        for start, dur in spans:                       # a long note fills every bar it sounds in
            first, last = int(start // meter), int(max(start, start + dur - 1e-6) // meter)
            counts[max(0, first):min(bars, last + 1)] += 1
        grid[row] = counts / max(1, counts.max())
    fig, ax = plt.subplots(figsize=(15, 0.42 * len(tracks) + 2.2))
    ax.imshow(np.where(grid > 0, 0.25 + 0.75 * grid, 0), aspect="auto", cmap="Blues", vmin=0, vmax=1.2,
              extent=(0, bars, len(tracks), 0), interpolation="nearest")
    ax.set_yticks(np.arange(len(tracks)) + 0.5, [f"{t['name']} ({t.get('role', '')})" for t in tracks], fontsize=11)
    for section in project["sections"]:
        bar = section["start"] / meter
        ax.axvline(bar, color=ACCENT, lw=1.4)
        ax.text(bar, -0.15, " " + section["name"], fontsize=10, color=DARK, rotation=30, ha="left", va="bottom")
    ax.set_xlabel("bar")
    ax.spines["left"].set_visible(False)
    ax.tick_params(left=False)
    return _save(fig, path)


def pianoroll(project: dict, path: str, section_name: str | None = None, max_bars: int = 16) -> str:
    """Do the notes fit the chords and the key? Orange notes are outside the key."""
    meter = project["meta"]["meter"]
    key = theory.parse_key(project["meta"]["key"])
    section = next((s for s in project["sections"] if s["name"] == section_name), None) or max(
        project["sections"], key=lambda s: s["energy"])
    start = section["start"]
    end = start + min(section["bars"], max_bars) * meter
    pcs = frozenset((pc + section.get("transpose", 0)) % 12 for pc in key.pcs)
    fig, ax = plt.subplots(figsize=(15, 7.5))
    shades = {"bass": "#2F4468", "sub": "#2F4468", "pad": "#B8C4D6", "chord": "#9DB3D4", "keys": "#9DB3D4",
              "lead": "#4A6FA5", "vocal": "#1B2B47", "pluck": "#6B8EC2", "arp": "#6B8EC2", "backing": "#6B8EC2"}
    low, high = 127, 0
    for track in project["tracks"]:
        if track.get("kind") == "drums" or track.get("role") == "fx":
            continue
        notes = [(n[0], n[1], n[2]) for n in track["notes"]]
        notes += [(line["start"] + n[0], n[1], n[2]) for line in track.get("lines", []) for n in line["notes"]]
        labelled = False
        for at, dur, pitch in notes:
            if not (start <= at < end):
                continue
            inside = pitch % 12 in pcs
            ax.barh(pitch, dur, left=(at - start) / meter * meter, height=0.8, align="center",
                    color=shades.get(track.get("role"), BLUE) if inside else ACCENT, edgecolor="white", lw=0.4)
            low, high = min(low, pitch), max(high, pitch)
            if not labelled:
                ax.text(at - start, pitch + 0.9, track["name"], fontsize=10, color=DARK)
                labelled = True
    for chord in project["chords"]:
        if start <= chord["start"] < end:
            ax.axvline(chord["start"] - start, color=GREY, lw=0.8)
            ax.text(chord["start"] - start, 1.01, " " + chord["name"], transform=ax.get_xaxis_transform(), fontsize=12)
    if low <= high:
        ax.set_ylim(low - 2, high + 3)
        ticks = [p for p in range(low - 2, high + 3) if p % 12 == key.tonic]
        ax.set_yticks(ticks, [theory.midi_to_name(p, key.flats) for p in ticks])
    ax.set_xlim(0, end - start)
    ax.set_xticks(np.arange(0, end - start + 1e-9, meter), [str(int(b // meter) + 1) for b in np.arange(0, end - start + 1e-9, meter)])
    ax.set_xlabel(f"bar of section '{section['name']}'")
    ax.set_ylabel("pitch")
    return _save(fig, path)


def stereo(master: np.ndarray, path: str, project: dict | None = None) -> str:
    """Is the image mono-safe: does correlation stay positive, and is the low end centred?"""
    window = SR
    count = len(master) // window
    blocks = master[:count * window].reshape(count, window, 2)
    left, right = blocks[:, :, 0], blocks[:, :, 1]
    corr = np.sum(left * right, axis=1) / (np.sqrt(np.sum(left ** 2, axis=1) * np.sum(right ** 2, axis=1)) + 1e-12)
    fig, axes = plt.subplots(1, 2, figsize=(15, 5), gridspec_kw={"width_ratios": [2.4, 1]})
    axes[0].plot(np.arange(count), corr, color=BLUE, lw=1.6)
    axes[0].axhline(0, color=ACCENT, lw=1.2)
    axes[0].set_ylim(-1, 1.05)
    axes[0].set_ylabel("L/R correlation")
    axes[0].set_xlabel("time (s)")
    if project:
        _section_marks(axes[0], project)
    names, values = [], []
    for name, band in qa.BANDS.items():
        sos = signal.butter(4, band, btype="bandpass", fs=SR, output="sos")
        part = signal.sosfilt(sos, master, axis=0)
        names.append(name)
        values.append(float(np.corrcoef(part[:, 0], part[:, 1])[0, 1]))
    bars = axes[1].barh(names, values, color=[ACCENT if v < 0.2 else BLUE for v in values])
    axes[1].bar_label(bars, fmt="%.2f", padding=3)
    axes[1].set_xlim(min(0, min(values)) - 0.05, 1.15)
    axes[1].set_xlabel("correlation by band")
    axes[1].spines["bottom"].set_visible(False)
    return _save(fig, path)


def audition(audio: np.ndarray, path: str) -> str:
    """What does this sound look like: attack and decay, harmonic content, movement over time?"""
    mono = dsp.to_mono(audio)
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.8))
    t = np.arange(len(mono)) / SR
    axes[0].plot(t, mono, color=BLUE, lw=0.6)
    envelope = dsp.one_pole_smooth(np.abs(mono), 0.01)
    axes[0].plot(t, envelope, color=ACCENT, lw=1.6)
    axes[0].set_xlabel("time (s)")
    axes[0].set_ylabel("waveform and envelope")
    freqs, psd = signal.welch(mono, SR, nperseg=min(8192, len(mono)))
    axes[1].semilogx(freqs[1:], 10 * np.log10(psd[1:] + 1e-14), color=DARK, lw=1.4)
    axes[1].set_xlim(20, 20000)
    axes[1].set_ylim(10 * np.log10(psd.max() + 1e-14) - 80, 10 * np.log10(psd.max() + 1e-14) + 5)
    axes[1].set_xlabel("frequency (Hz)")
    axes[1].set_ylabel("spectrum (dB)")
    f, tt, spec = signal.stft(mono, SR, nperseg=2048, noverlap=1536)
    level = 20 * np.log10(np.abs(spec) + 1e-7)
    axes[2].pcolormesh(tt, f, level, cmap="Blues", vmin=level.max() - 70, vmax=level.max(), shading="auto")
    axes[2].set_ylim(0, 12000)
    axes[2].set_xlabel("time (s)")
    axes[2].set_ylabel("spectrogram (Hz)")
    return _save(fig, path)


def chain_response(chain: list, path: str, ctx) -> str:
    """What does this effect chain do to the tone? Magnitude response measured with an impulse."""
    from . import fx
    impulse = np.zeros(SR)
    impulse[0] = 1.0
    linear = [step for step in chain if step.get("fx") in ("eq", "hpf", "lpf", "tilt")]
    out = fx.apply_chain(impulse, linear, ctx)
    freqs = np.fft.rfftfreq(SR, 1 / SR)
    level = 20 * np.log10(np.abs(np.fft.rfft(dsp.to_mono(out))) + 1e-9)
    fig, ax = plt.subplots(figsize=(11, 4.8))
    ax.semilogx(freqs[20:], level[20:], color=DARK, lw=2.2)
    ax.axhline(0, color=GREY, lw=1)
    ax.set_xlim(20, 20000)
    ax.set_ylim(max(-36, level[20:20000].min() - 2), max(6, level[20:20000].max() + 2))
    ax.set_xlabel("frequency (Hz)")
    ax.set_ylabel("gain (dB)")
    return _save(fig, path)


def vocal_line(audio: np.ndarray, sr: int, path: str, origin: float = 0.0, notes: list | None = None,
               labels: list | None = None, top_hz: float = 6000.0) -> str:
    """Is this line really sung: harmonic stripes through every vowel, pitch on the notes, words in place?
    `notes` are (start_s, dur_s, midi, ...) on the same clock as `origin` (time of the first sample);
    `labels` are (time_s, text) marks such as syllables."""
    pyworld = world.pyworld()
    mono = dsp.to_mono(audio).astype(np.float64)
    fig, axes = plt.subplots(2, 1, figsize=(15, 8.5), sharex=True, gridspec_kw={"height_ratios": [1.5, 1]})
    f, t, spec = signal.stft(mono, sr, nperseg=1024, noverlap=1024 - 128)
    level = 20 * np.log10(np.abs(spec) + 1e-7)
    keep = f <= top_hz
    axes[0].pcolormesh(t + origin, f[keep], level[keep], cmap="Blues", vmin=level.max() - 65, vmax=level.max(), shading="auto")
    axes[0].set_ylabel("frequency (Hz)")
    for index, (when, text) in enumerate(labels or []):
        axes[0].axvline(when, color=ACCENT, lw=0.8, alpha=0.7)
        # neighbouring syllables sit on alternating rows so that fast passages stay readable
        axes[0].text(when, top_hz * (0.96 - 0.07 * (index % 3)), " " + text, color=ACCENT, fontsize=12, va="top")
    f0, times = pyworld.harvest(mono, sr, f0_floor=60.0, f0_ceil=900.0, frame_period=5.0)
    midi = np.where(f0 > 0, 69 + 12 * np.log2(np.maximum(f0, 1e-6) / 440.0), np.nan)
    for note in notes or []:
        axes[1].plot([note[0], note[0] + note[1]], [note[2], note[2]], color=GREY, lw=7, solid_capstyle="butt")
    axes[1].plot(times + origin, midi, color=DARK, lw=1.6)
    sung = [n[2] for n in notes or []] or list(midi[~np.isnan(midi)])
    if sung:
        axes[1].set_ylim(min(sung) - 3, max(sung) + 3)
        ticks = np.arange(int(min(sung)) - 2, int(max(sung)) + 3, 2)
        axes[1].set_yticks(ticks, [theory.midi_to_name(int(p)) for p in ticks])
    axes[1].set_ylabel("pitch: sung (line) on notes (bars)")
    axes[1].set_xlabel("time (s)")
    return _save(fig, path)
