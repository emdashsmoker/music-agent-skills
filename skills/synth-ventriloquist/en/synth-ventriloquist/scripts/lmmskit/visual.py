# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
"""Figures for reviewing a song by eye: what an agent looks at instead of listening.

Each figure answers one review question and is drawn so problems show as shapes:
a buried kick is a missing low stripe, harsh highs are a dark upper band, a dead line
ending is noise where harmonic stripes should be.
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager
from scipy import signal

from . import audio, settings, theory
from .project import TRACK_INSTRUMENT, Project
from .vocal import world

MAIN, ACCENT, INK, FAINT = "#6B8EC2", "#F5A962", "#1F2A44", "#DCE5F2"
SPECTROGRAM_CMAP = "Blues"
DYNAMIC_RANGE_DB = 70.0
FREQ_MIN, FREQ_MAX = 30.0, 16000.0
FREQ_TICKS = [50, 100, 250, 500, 1000, 2000, 5000, 10000]
DPI = 110
VOCAL_TOP_HZ = 6000.0                # a voice's harmonics are read as stripes up to here; above is consonant noise
VOCAL_STFT_N, VOCAL_STFT_HOP = 1024, 128
VOCAL_DYNAMIC_RANGE_DB = 65.0
SYLLABLE_LABEL_ROWS = 3              # neighbouring syllable labels alternate over this many rows so fast lines stay readable
IPA_FALLBACK_FONT = "DejaVu Sans"    # ships with matplotlib and has the IPA letters (ə ɪ ɚ ...) that the Korean-first fonts lack
NOTE_BAR_WIDTH = 7
PITCH_MARGIN_SEMITONES = 3


def _style() -> None:
    installed = {f.name for f in font_manager.fontManager.ttflist}
    family = next((name for name in settings.get("figure_fonts") if name in installed), "sans-serif")
    plt.rcParams.update({"font.family": family, "font.weight": "bold", "font.size": 12, "axes.labelweight": "bold",
                         "axes.titleweight": "bold", "axes.titlesize": 13, "axes.spines.top": False,
                         "axes.spines.right": False, "axes.grid": False, "figure.facecolor": "white",
                         "axes.edgecolor": INK, "text.color": INK, "axes.labelcolor": INK, "xtick.color": INK,
                         "ytick.color": INK, "axes.unicode_minus": False})


def _save(fig, path: str) -> str:
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    return path


def _log_spectrogram(mono: np.ndarray, rate: int, n_fft: int, hop: int, bins: int = 160):
    """Magnitude spectrogram resampled onto a log-frequency axis, in dB relative to its maximum."""
    freqs, times, stft = signal.stft(mono, rate, nperseg=n_fft, noverlap=n_fft - hop, boundary=None, padded=False)
    power = np.abs(stft) ** 2
    edges = np.geomspace(FREQ_MIN, min(FREQ_MAX, rate / 2), bins + 1)
    rows = []
    for low, high in zip(edges[:-1], edges[1:]):
        inside = (freqs >= low) & (freqs < high)
        rows.append(power[inside].mean(axis=0) if inside.any() else power[np.argmin(np.abs(freqs - (low + high) / 2))])
    image = 10 * np.log10(np.maximum(np.array(rows), 1e-14))
    time_edges = np.append(times, times[-1] + hop / rate) - (times[0] if len(times) else 0.0)
    return time_edges, edges, image - image.max()


def _draw_spectrogram(ax, mono, rate, n_fft=2048, hop=None, t0=0.0):
    hop = hop or max(128, len(mono) // 1400)
    times, edges, image = _log_spectrogram(mono, rate, n_fft, hop)
    ax.pcolormesh(times + t0, edges, image, cmap=SPECTROGRAM_CMAP, vmin=-DYNAMIC_RANGE_DB, vmax=0, shading="flat", rasterized=True)
    ax.set_yscale("log")
    ax.set_ylim(FREQ_MIN, edges[-1])
    ax.set_yticks([f for f in FREQ_TICKS if f <= edges[-1]])
    ax.set_yticklabels([f"{f}" if f < 1000 else f"{f // 1000}k" for f in FREQ_TICKS if f <= edges[-1]])
    ax.set_ylabel("Hz")


LABEL_CHARS_ACROSS = 150             # section-label characters that fit across a full-width axis at the label size


def _fitted_labels(sections, span: float) -> list[tuple[float, str]]:
    """Section labels cut to the room before the next section line, so neighbours never overlap."""
    result = []
    for index, (start, label) in enumerate(sections or []):
        end = sections[index + 1][0] if index + 1 < len(sections) else span
        room = max(3, int((end - start) / max(span, 1e-9) * LABEL_CHARS_ACROSS) - 1)
        result.append((start, label if len(label) <= room else label[:room - 1] + "."))
    return result


def _mark_sections(ax, sections, y_text=None):
    """sections: [(start seconds, label)]"""
    span = ax.get_xlim()[1]
    for start, label in _fitted_labels(sections, span):
        ax.axvline(start, color=ACCENT, linewidth=1.2)
        if y_text is not None:
            ax.text(start, y_text, " " + label, color=ACCENT, va="top", ha="left", fontsize=12)


def song_overview(wav_path: str, out_path: str, sections: list[tuple[float, str]] | None = None, title: str = "") -> str:
    """Whole song at a glance: loudness curve with section marks above a log-frequency spectrogram.

    Look for: energy that follows the arrangement, a continuous low stripe where the kick/bass play,
    no band that stays dark (over-full) or white (empty) through the whole song.
    """
    _style()
    x, rate = audio.load(wav_path)
    mono = audio.to_mono(x)
    duration = len(mono) / rate
    fig, (top, bottom) = plt.subplots(2, 1, figsize=(16, 8), sharex=True, gridspec_kw={"height_ratios": [1, 2.4], "hspace": 0.08})
    times, loudness = audio.short_term_lufs(x, rate)
    top.plot(times, np.maximum(loudness, -50), color=MAIN, linewidth=2.2)
    top.set_ylabel("LUFS (3 s)")
    top.set_ylim(-45, 0)
    top.set_title(title or wav_path, loc="left")
    _mark_sections(top, sections, y_text=-1)
    _draw_spectrogram(bottom, mono, rate, n_fft=4096)
    _mark_sections(bottom, sections)
    bottom.set_xlim(0, duration)
    bottom.set_xlabel("seconds")
    return _save(fig, out_path)


def spectrogram(wav_path: str, out_path: str, start: float = 0.0, end: float | None = None, title: str = "",
                marks: list[tuple[float, str]] | None = None) -> str:
    """Close-up of a time range (a drum fill, one vocal line). marks: [(seconds, label)] drawn as orange labels."""
    _style()
    x, rate = audio.load(wav_path)
    mono = audio.to_mono(x)[int(start * rate):int(end * rate) if end else None]
    fig, (wave, spec) = plt.subplots(2, 1, figsize=(15, 6.5), sharex=True, gridspec_kw={"height_ratios": [1, 3], "hspace": 0.08})
    t = start + np.arange(len(mono)) / rate
    step = max(1, len(mono) // 6000)
    wave.plot(t[::step], mono[::step], color=MAIN, linewidth=0.8)
    wave.set_ylim(-1, 1)
    wave.set_ylabel("amplitude")
    wave.set_title(title or wav_path, loc="left")
    _draw_spectrogram(spec, mono, rate, n_fft=1024, hop=max(64, len(mono) // 1500), t0=start)
    for position, label in marks or []:
        spec.text(position, FREQ_MAX * 0.75, label, color=ACCENT, ha="left", va="top", fontsize=12)
    spec.set_xlabel("seconds")
    return _save(fig, out_path)


def vocal_line(audio_data: np.ndarray, rate: int, out_path: str, origin: float = 0.0, notes: list[tuple[float, float, float]] | None = None,
               labels: list[tuple[float, str]] | None = None, top_hz: float = VOCAL_TOP_HZ, title: str = "") -> str:
    """Is this line really sung: harmonic stripes through every vowel, pitch on the notes, words in place?

    Top: linear-frequency spectrogram to top_hz with a syllable mark at every label. Bottom: the sung pitch
    (Harvest) as a line over the written notes as bars. `notes` are (start_s, duration_s, midi) and `labels`
    (time_s, text), both on the clock where `origin` is the time of the first sample (lines.melody_in_seconds()
    puts a melody on the song clock; rendered parts store the syllable spans on it already).
    """
    _style()
    mono = audio.to_mono(audio_data).astype(np.float64)
    fig, (spec, pitch) = plt.subplots(2, 1, figsize=(15, 8.5), sharex=True, gridspec_kw={"height_ratios": [1.5, 1], "hspace": 0.08})
    freqs, times, stft = signal.stft(mono, rate, nperseg=VOCAL_STFT_N, noverlap=VOCAL_STFT_N - VOCAL_STFT_HOP)
    level = 20 * np.log10(np.abs(stft) + 1e-7)
    keep = freqs <= top_hz
    spec.pcolormesh(times + origin, freqs[keep], level[keep], cmap=SPECTROGRAM_CMAP, vmin=level.max() - VOCAL_DYNAMIC_RANGE_DB,
                    vmax=level.max(), shading="auto", rasterized=True)
    spec.set_ylabel("Hz")
    spec.set_title(title, loc="left")
    for index, (when, text) in enumerate(labels or []):
        spec.axvline(when, color=ACCENT, linewidth=0.8, alpha=0.7)
        spec.text(when, top_hz * (0.96 - 0.07 * (index % SYLLABLE_LABEL_ROWS)), " " + text, color=ACCENT, fontsize=12, va="top",
                  fontfamily=[*plt.rcParams["font.family"], IPA_FALLBACK_FONT])
    f0, frame_times = world.harvest_f0(mono, rate)
    sung_midi = np.where(f0 > 0, 69 + 12 * np.log2(np.maximum(f0, 1e-6) / 440.0), np.nan)
    for start, duration, midi in notes or []:
        pitch.plot([start, start + duration], [midi, midi], color=FAINT, linewidth=NOTE_BAR_WIDTH, solid_capstyle="butt")
    pitch.plot(frame_times + origin, sung_midi, color=INK, linewidth=1.6)
    shown = [midi for _, _, midi in notes or []] or [m for m in sung_midi if not np.isnan(m)]
    if shown:
        pitch.set_ylim(min(shown) - PITCH_MARGIN_SEMITONES, max(shown) + PITCH_MARGIN_SEMITONES)
        ticks = np.arange(int(min(shown)) - 2, int(max(shown)) + 3, 2)
        pitch.set_yticks(ticks, [theory.name(int(p)) for p in ticks])
    pitch.set_ylabel("pitch: sung (line) on notes (bars)")
    pitch.set_xlabel("seconds")
    return _save(fig, out_path)


def compare_spectrograms(items: list[tuple[str, str]], out_path: str, start: float = 0.0, end: float | None = None,
                         marks: list[tuple[float, str]] | None = None, fmax: float = 5000.0) -> str:
    """Stacked before/after spectrograms on a shared time axis. items: [(label, wav path)]. Linear Hz up to fmax,
    which shows voiced harmonics as horizontal stripes and whisper as noise."""
    _style()
    fig, axes = plt.subplots(len(items), 1, figsize=(15, 4.2 * len(items)), sharex=True, squeeze=False)
    for ax, (label, path) in zip(axes[:, 0], items):
        x, rate = audio.load(path)
        mono = audio.to_mono(x)[int(start * rate):int(end * rate) if end else None]
        freqs, times, stft = signal.stft(mono, rate, nperseg=1024, noverlap=1024 - 128)
        image = 20 * np.log10(np.maximum(np.abs(stft), 1e-7))
        keep = freqs <= fmax
        ax.pcolormesh(times + start, freqs[keep], image[keep] - image.max(), cmap=SPECTROGRAM_CMAP, vmin=-DYNAMIC_RANGE_DB, vmax=0,
                      shading="auto", rasterized=True)
        ax.set_title(label, loc="left")
        ax.set_ylabel("Hz")
        for position, text in marks or []:
            ax.text(position, fmax * 0.96, text, color=ACCENT, ha="left", va="top", fontsize=12)
    axes[-1, 0].set_xlabel("seconds")
    return _save(fig, out_path)


def band_balance(levels: dict[str, float], targets: dict[str, tuple[float, float]], out_path: str, title: str = "") -> str:
    """Measured band levels (dots) against target ranges (bars). A dot outside its bar turns orange."""
    _style()
    names = list(levels)
    fig, ax = plt.subplots(figsize=(9, 4.8))
    for row, band in enumerate(names):
        low, high = targets.get(band, (levels[band], levels[band]))
        ax.barh(row, high - low, left=low, color=FAINT, height=0.55)
        inside = low <= levels[band] <= high
        ax.plot(levels[band], row, "o", color=MAIN if inside else ACCENT, markersize=13)
        ax.text(levels[band], row + 0.38, f"{levels[band]:.1f}", ha="center", va="bottom", fontsize=12, color=INK if inside else ACCENT)
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names)
    ax.invert_yaxis()
    ax.spines["bottom"].set_visible(False)
    ax.set_xlabel("band level, dB relative to full mix")
    ax.set_title(title, loc="left")
    return _save(fig, out_path)


def stem_spectra(stems: dict[str, str], out_path: str, highlight: list[str] | None = None, title: str = "") -> str:
    """Average spectrum of each stem on one plot: where parts overlap is where they mask each other."""
    _style()
    fig, ax = plt.subplots(figsize=(13, 6))
    centres = np.geomspace(FREQ_MIN, FREQ_MAX, 60)
    for name, path in stems.items():
        x, rate = audio.load(path)
        if audio.sample_peak_db(x) < -70.0:
            continue
        freqs, power = audio.spectrum(x, rate)
        levels = [audio.power_db(audio.band_power(freqs, power, c / 1.06, c * 1.06)) for c in centres]
        strong = name in (highlight or [])
        ax.plot(centres, levels, color=ACCENT if strong else MAIN, linewidth=2.6 if strong else 1.2, alpha=1.0 if strong else 0.6)
        peak = int(np.argmax(levels))
        ax.text(centres[peak], levels[peak] + 1, name, fontsize=12, ha="center", color=ACCENT if strong else INK)
    ax.set_xscale("log")
    ax.set_xticks(FREQ_TICKS)
    ax.set_xticklabels([f"{f}" if f < 1000 else f"{f // 1000}k" for f in FREQ_TICKS])
    ax.set_ylim(-90, 0)
    ax.set_xlabel("Hz")
    ax.set_ylabel("dBFS per 1/6 octave")
    ax.set_title(title, loc="left")
    return _save(fig, out_path)


def arrangement(project: Project, out_path: str, sections: list[tuple[float, str]] | None = None, title: str = "") -> str:
    """Which track plays in which bar (one row per track). Shows build-ups, breakdowns and empty stretches."""
    _style()
    from . import compose
    notes = compose.notes_with_vocals(project, project.path)
    beats_per_bar = project.beats_per_bar
    names = list(notes)
    fig, ax = plt.subplots(figsize=(16, max(3.0, 0.42 * len(names) + 1.4)))
    for row, name in enumerate(names):
        bars = sorted({bar for n in notes[name] for bar in range(int(n.start // beats_per_bar), int((n.start + n.length - 1e-6) // beats_per_bar) + 1)})
        ax.broken_barh([(bar, 1) for bar in bars], (row - 0.38, 0.76), color=MAIN)
    total_bars = max(1.0, project.length_beats() / beats_per_bar)
    for start_bar, label in _fitted_labels([(beats / beats_per_bar, label) for beats, label in sections or []], total_bars):
        ax.axvline(start_bar, color=ACCENT, linewidth=1.2)
        ax.text(start_bar, -0.9, " " + label, color=ACCENT, fontsize=12, va="center")
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names)
    ax.set_ylim(len(names) - 0.4, -1.4)
    ax.set_xlim(0, max(1.0, project.length_beats() / beats_per_bar))
    ax.set_xlabel("bar")
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.set_title(title or "arrangement", loc="left")
    return _save(fig, out_path)


def piano_roll(project: Project, out_path: str, start_bar: float = 0, bars: float = 8, tracks: list[str] | None = None,
               scale_pitch_classes: set[int] | None = None, title: str = "") -> str:
    """Notes of the chosen tracks over a bar range. Notes outside the given scale are drawn in orange."""
    _style()
    beats_per_bar = project.beats_per_bar
    low_beat, high_beat = start_bar * beats_per_bar, (start_bar + bars) * beats_per_bar
    from . import compose
    notes = {name: [n for n in items if low_beat <= n.start < high_beat] for name, items in compose.notes_with_vocals(project, project.path).items()
             if tracks is None or name in tracks}
    notes = {name: items for name, items in notes.items() if items}
    fig, ax = plt.subplots(figsize=(16, 7))
    pitches = [n.pitch for items in notes.values() for n in items] or [60]
    for name, items in notes.items():
        for n in items:
            outside = scale_pitch_classes is not None and n.pitch % 12 not in scale_pitch_classes
            ax.barh(n.pitch, n.length / beats_per_bar, left=n.start / beats_per_bar, height=0.8,
                    color=ACCENT if outside else MAIN, alpha=0.85, edgecolor="white", linewidth=0.4)
        first = min(items, key=lambda n: n.start)
        ax.text(first.start / beats_per_bar, first.pitch + 0.9, name, fontsize=12, color=INK)
    for bar in range(int(start_bar), int(start_bar + bars) + 1):
        ax.axvline(bar, color=FAINT, linewidth=1, zorder=0)
    ticks = [p for p in range(min(pitches) - 1, max(pitches) + 2) if p % 12 == 0]
    ax.set_yticks(ticks)
    ax.set_yticklabels([f"C{p // 12 - 1}" for p in ticks])
    ax.set_ylim(min(pitches) - 2, max(pitches) + 3)
    ax.set_xlim(start_bar, start_bar + bars)
    ax.set_xlabel("bar")
    ax.set_title(title or "piano roll", loc="left")
    return _save(fig, out_path)


def contact_sheet(wav_path: str, names: list[str], slot_seconds: float, out_path: str, columns: int = 6) -> str:
    """Grid of small spectrograms, one per auditioned sound (see audition.profile)."""
    _style()
    x, rate = audio.load(wav_path)
    mono = audio.to_mono(x)
    rows = -(-len(names) // columns)
    fig, axes = plt.subplots(rows, columns, figsize=(3.0 * columns, 2.2 * rows), squeeze=False)
    for index, ax in enumerate(axes.flat):
        ax.set_xticks([])
        ax.set_yticks([])
        if index >= len(names):
            ax.axis("off")
            continue
        slot = mono[int(index * slot_seconds * rate):int((index + 1) * slot_seconds * rate)]
        times, edges, image = _log_spectrogram(slot, rate, 1024, 256, bins=64)
        ax.pcolormesh(times, edges, image, cmap=SPECTROGRAM_CMAP, vmin=-DYNAMIC_RANGE_DB, vmax=0, shading="flat", rasterized=True)
        ax.set_yscale("log")
        ax.set_yticks([])
        ax.minorticks_off()
        ax.set_title(names[index], fontsize=12, loc="left", pad=2)
    return _save(fig, out_path)


def curves(series: dict[str, tuple[np.ndarray, np.ndarray]], out_path: str, ylabel: str, title: str = "",
           sections: list[tuple[float, str]] | None = None) -> str:
    """Generic labelled line plot (automation, ducking depth, per-section loudness)."""
    _style()
    fig, ax = plt.subplots(figsize=(14, 4.5))
    for index, (name, (xs, ys)) in enumerate(series.items()):
        ax.plot(xs, ys, color=MAIN if index == 0 else ACCENT, linewidth=2)
        ax.text(xs[-1], ys[-1], " " + name, va="center", fontsize=12)
    _mark_sections(ax, sections)
    ax.set_ylabel(ylabel)
    ax.set_title(title, loc="left")
    return _save(fig, out_path)
