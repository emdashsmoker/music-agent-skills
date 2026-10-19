# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
# Part of Spectro Maestro. See LICENSE and THIRD-PARTY-NOTICES.md at the root of the skill.
"""Render a project: synthesise stems, balance them by role, sum through buses and returns, master.

Stage order per track: raw stem (cached) -> inserts -> automation -> filters -> sidechain duck ->
loudness target -> pan/width -> bus + sends. Raw stems are cached on disk by content hash, so a
mix-only change re-renders in seconds."""
from __future__ import annotations

import atexit
import hashlib
import json
import os
import shutil

import numpy as np

from . import export, dsp, fx, instruments, mixprofile
from .dsp import SR

ENGINE_VERSION = 4              # bump when synthesis changes so stale caches are not reused
BUS_ORDER = ("drums", "bass", "music", "fx", "vocals")
CARVE_BAND = (1300.0, 5000.0)   # where consonants live; the backing is dipped here while the vocal sings
SILENT_LUFS = -65.0
FADED_TAIL_S = 0.3
TRAILING_SILENCE_LEVEL, TRAILING_SILENCE_S = 1e-4, 0.4     # the file ends this long after the last audible sample
TAIL_FADE_POWER = 2.0           # shape of the fade applied to the tail after the last bar
WORKSPACE_IN_RAM_BYTES = 1.2e9   # bus and send buffers above this total size live in mapped files (songs over about six minutes)


def _log(message: str) -> None:
    print(f"[mix] {message}", flush=True)


def total_samples(project: dict, tail_seconds: float) -> int:
    return int((project["meta"]["beats"] * 60.0 / project["meta"]["bpm"] + tail_seconds) * SR)


def _cache_key(*parts) -> str:
    return hashlib.sha1(json.dumps(parts, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:20]


def _choke_times(project: dict, track: dict, seconds_per_beat: float):
    """Open hats are cut by closed hats, as on a real machine or kit."""
    inst = track["inst"].get("base") if isinstance(track["inst"], dict) else track["inst"]
    if not inst or "hat_open" not in str(inst):
        return None
    times = [note[0] for other in project["tracks"] if other is not track and "hat_closed" in str(other.get("inst"))
             for note in other["notes"]]
    times += [note[0] for note in track["notes"]]
    return np.array(sorted(int(t * seconds_per_beat * SR) for t in times)) if times else None


def render_raw_stem(project: dict, track: dict, ctx: fx.FxContext, n: int, cache_dir: str) -> np.ndarray:
    resolved = instruments.resolve(track["inst"], project.get("patches"))
    seed = project["meta"]["seed"]
    key = _cache_key(ENGINE_VERSION, resolved, track["notes"], ctx.bpm, n, seed, track["name"])
    path = os.path.join(cache_dir, f"{key}.npy")
    if os.path.exists(path):
        return np.load(path)
    from .spec import stable_seed
    chokes = _choke_times(project, track, 60.0 / ctx.bpm)
    audio = instruments.render_track(resolved, track["notes"], ctx, n, stable_seed(seed, track["name"]), chokes)
    np.save(path, audio.astype(np.float32))
    return audio


def _segment_curve(n: int, segments: list, neutral: float, seconds_per_beat: float, log: bool,
                   resume: np.ndarray | None = None) -> np.ndarray | None:
    """Per-sample automation curve from [start_beat, end_beat, from, to] ramps; `neutral` elsewhere.
    A ramp's end value stays in force until the next note starts (`resume`: sorted note onsets in beats) or the
    next ramp begins: the tails of the notes it shaped keep their setting. Without this a filter that closed over
    the outro would spring open on the final reverb tail."""
    if not segments:
        return None
    curve = np.full(n, neutral, dtype=np.float32)
    ordered = sorted(segments)
    for index, (start, end, first, last) in enumerate(ordered):
        a, b = int(start * seconds_per_beat * SR), min(n, int(end * seconds_per_beat * SR))
        if b > a:
            t = np.linspace(0.0, 1.0, b - a)
            curve[a:b] = first * (last / first) ** t if log else first + (last - first) * t
        until = ordered[index + 1][0] if index + 1 < len(ordered) else np.inf
        if resume is not None and len(resume):
            later = resume[np.searchsorted(resume, end - 1e-6):]
            until = min(until, float(later[0]) if len(later) else np.inf)
        hold_end = n if np.isinf(until) else min(n, int(until * seconds_per_beat * SR))
        if resume is not None and hold_end > b:
            curve[b:hold_end] = last
    return curve


def apply_automation(x: np.ndarray, automation: list, seconds_per_beat: float, resume: np.ndarray | None = None) -> np.ndarray:
    """`resume` holds the note onsets (beats) of what is being automated; see _segment_curve."""
    by_param = {}
    for param, start, end, first, last in automation or []:
        by_param.setdefault(param, []).append((start, end, first, last))
    n = len(x)
    curve = _segment_curve(n, by_param.get("lpf"), 20000.0, seconds_per_beat, True, resume)
    if curve is not None:
        x = dsp.tv_filter(x, "lp", curve, 0.9, SR, 4, 128)
    curve = _segment_curve(n, by_param.get("hpf"), 20.0, seconds_per_beat, True, resume)
    if curve is not None:
        x = dsp.tv_filter(x, "hp", curve, 0.9, SR, 4, 128)
    curve = _segment_curve(n, by_param.get("volume"), 0.0, seconds_per_beat, False, resume)
    if curve is not None:
        gain = np.power(np.float32(10.0), curve / np.float32(20.0))
        x = (np.asarray(x, dtype=np.float32).T * gain).T
    return x


def _onsets(tracks: list) -> np.ndarray:
    """Sorted start beats of every note and sung line of these tracks."""
    starts = [note[0] for track in tracks for note in track.get("notes", [])]
    starts += [line["start"] for track in tracks for line in track.get("lines", [])]
    return np.array(sorted(starts), dtype=float)


def _place(x: np.ndarray, pan: float, width: float, mono: bool) -> np.ndarray:
    """Stereo placement of a processed stem (constant-power pan, optional width change)."""
    angle = (np.clip(pan, -1.0, 1.0) + 1.0) * np.pi / 4
    left, right = np.float32(np.cos(angle) * np.sqrt(2.0)), np.float32(np.sin(angle) * np.sqrt(2.0))
    if mono or x.ndim == 1:
        centre = x if x.ndim == 1 else x.mean(axis=1)
        out = np.empty((len(centre), 2), dtype=np.float32)
        out[:, 0], out[:, 1] = centre * left, centre * right
        return out
    stereo = fx.width(x, width).astype(np.float32) if width != 1.0 else x.astype(np.float32)
    if pan:
        stereo *= np.array([left, right], dtype=np.float32)
    return stereo


def _sidechain_triggers(project: dict, seconds_per_beat: float) -> np.ndarray:
    source = (project.get("mix") or {}).get("sidechain_source")
    times = [note[0] for track in project["tracks"]
             if (track["name"] == source if source else track.get("role") == "kick") for note in track["notes"]]
    return np.array(sorted(set(int(t * seconds_per_beat * SR) for t in times)), dtype=np.int64)


def _band_carve(music: np.ndarray, vocal: np.ndarray, depth_db: float) -> np.ndarray:
    """Dip the backing in the consonant band while the vocal is active, leaving the rest untouched."""
    from scipy import signal
    sos = signal.butter(2, CARVE_BAND, btype="bandpass", fs=SR, output="sos")
    band = signal.sosfiltfilt(sos, music, axis=0).astype(np.float32)
    level = dsp.lin_to_db(np.abs(dsp.to_mono(vocal)), 1e-5)
    follow = dsp.one_pole_smooth(fx._release_follow(level, 0.25), 0.03)
    presence = np.clip((follow + 45.0) / 15.0, 0.0, 1.0)            # fully on above about -30 dBFS
    gain = dsp.db_to_lin(depth_db * presence) - 1.0
    return music + (band.T * gain).T.astype(np.float32)


def master_chain(mix, settings: dict, ctx: fx.FxContext) -> tuple:
    """Bring the summed mix to the target loudness under the peak ceiling. Returns (audio, stats).
    `mix` may be a one-element list: the array is then taken out of it and released as soon as it is filtered."""
    source = mix.pop() if isinstance(mix, list) else mix
    x = dsp.static_filter(source, "hp", 22.0, 0.7071, 0.0, SR, 2)
    del source
    if settings.get("mono_below"):
        x = fx.width(x, 1.0, float(settings["mono_below"]))
    if settings.get("eq"):
        x = fx.eq(x, settings["eq"])
    if settings.get("glue"):
        body = dsp.loud_part_lufs(x)
        x = fx.comp(x, threshold=body + 8.0, ratio=1.6, attack=0.03, release=0.25, knee=8.0)
    x = np.asarray(x, dtype=np.float32)
    target, ceiling = float(settings["lufs"]), float(settings["ceiling"])
    knee = float(dsp.db_to_lin(ceiling + 2.0)) if settings.get("clip") else None    # tanh shaves the tallest transients first
    peak = dsp.peak_envelope(x)

    def reduction_for(gain: float) -> np.ndarray:
        envelope = peak * gain
        if knee:
            envelope = knee * np.tanh(envelope / knee)
        return fx.limiter_reduction(envelope, ceiling)

    # The loudness after clipping and limiting is not linear in the input gain, so approach the target in a few steps.
    gain_db = target - dsp.integrated_lufs(x)
    for _ in range(6):
        gain = float(dsp.db_to_lin(gain_db))
        trial = x * np.float32(gain)
        if knee:
            trial = np.float32(knee) * np.tanh(trial / np.float32(knee))
        trial *= dsp.db_to_lin(-reduction_for(gain)).astype(np.float32)[:, None]
        measured = dsp.integrated_lufs(trial)
        if abs(target - measured) < 0.1:
            break
        gain_db += target - measured
    for _ in range(2):                                   # final pass on the real clipped signal; once more if it lands off target
        gain = float(dsp.db_to_lin(gain_db))
        y = x * np.float32(gain)
        if knee:
            y = dsp.oversampled(y, lambda s: knee * np.tanh(s / knee), 2).astype(np.float32)
        final_peak = dsp.peak_envelope(y) if knee else peak * gain
        pushed = fx.limiter_reduction(final_peak, ceiling)
        gain_curve = dsp.db_to_lin(-pushed)
        y *= gain_curve.astype(np.float32)[:, None]
        measured = dsp.integrated_lufs(y)
        if abs(target - measured) < 0.25:
            break
        gain_db += target - measured
    true_peak = float(dsp.lin_to_db(np.max(final_peak * gain_curve)))
    stats = {"lufs": round(measured, 2), "true_peak_db": round(true_peak, 2),
             "gain_db": round(float(gain_db), 2), "limiter_p95_db": round(float(np.percentile(pushed, 95)), 2),
             "limiter_max_db": round(float(pushed.max()), 2), "target_lufs": target}
    return y, stats


def _workspace(n: int, names: list, build_dir: str) -> dict:
    """Zeroed stereo buffers for buses and sends. A long song gets them as files mapped into memory, so the
    operating system can page them out; a short song keeps them in RAM, which is faster."""
    if n * 8 * len(names) <= WORKSPACE_IN_RAM_BYTES:
        return {name: np.zeros((n, 2), dtype=np.float32) for name in names}
    folder = os.path.join(build_dir, "work")
    os.makedirs(folder, exist_ok=True)
    atexit.register(shutil.rmtree, folder, True)
    return {name: np.lib.format.open_memmap(os.path.join(folder, f"{name}.npy"), mode="w+", dtype=np.float32, shape=(n, 2))
            for name in names}


def render(project: dict, build_dir: str, profile: dict | None = None, only: list | None = None,
           stem_dir: str | None = None, style: dict | None = None) -> dict:
    """Full render. Returns {'master', 'buses': {name: array}, 'report': {...}, 'stems': [paths]}.
    With `stem_dir` every track is written there as it is mixed (at its level in the mix, before mastering);
    track audio is never kept in memory, so a fifteen-minute song fits in a few gigabytes.
    style is the mix style (mixprofile.style_of) whose offsets apply to the role levels and the vocal carve."""
    profile = profile or {}
    style = style or mixprofile.style_of(project)
    cache_dir = os.path.join(build_dir, "cache")
    os.makedirs(cache_dir, exist_ok=True)
    meta = project["meta"]
    ctx = fx.FxContext(meta["bpm"], meta["seed"])
    seconds_per_beat = 60.0 / meta["bpm"]
    master = mixprofile.master_settings(project, profile, style)
    # a musical fade-out leaves nothing to ring on, so the file ends shortly after the last bar
    n = total_samples(project, FADED_TAIL_S if float(master.get("fade_out") or 0.0) > 0 else float(master["tail"]))
    triggers = _sidechain_triggers(project, seconds_per_beat)
    returns_cfg = mixprofile.return_settings(project, profile)
    names = list(BUS_ORDER) + [f"send_{name}" for name in returns_cfg]
    space = _workspace(n, names, build_dir)
    buses = {name: space[name] for name in BUS_ORDER}
    sends = {name: space[f"send_{name}"] for name in returns_cfg}
    report_tracks, stem_paths, duck_shapes = {}, [], {}
    raw = x = stereo = None

    for track in project["tracks"]:
        if only and track["name"] not in only:
            continue
        settings = mixprofile.track_settings(track, profile, style)
        if settings.get("mute"):
            continue
        layers = [(track["name"], None, settings)]
        if track.get("kind") == "vocal":
            from .vocal import render_vocal_track        # heavy dependencies are loaded only when a song sings
            layers = [(name, audio, {**settings, **overrides})
                      for name, audio, overrides in render_vocal_track(project, track, n, build_dir, profile)]
        for name, audio, layer_settings in layers:
            raw = audio if audio is not None else render_raw_stem(project, track, ctx, n, cache_dir)
            if not np.any(raw):
                _log(f"{name}: silent, skipped")
                continue
            x = fx.apply_chain(raw, layer_settings["inserts"], ctx)
            x = apply_automation(x, track.get("automation"), seconds_per_beat, _onsets([track]))
            if layer_settings.get("hpf"):
                x = dsp.static_filter(x, "hp", float(layer_settings["hpf"]), 0.7071, 0.0, SR, 2)
            if layer_settings.get("lpf"):
                x = dsp.static_filter(x, "lp", float(layer_settings["lpf"]), 0.7071, 0.0, SR, 2)
            duck = float(layer_settings.get("duck") or 0.0)
            if duck < 0 and len(triggers):
                release = float(layer_settings.get("duck_release", master["sidechain_release"])) * seconds_per_beat
                if release not in duck_shapes:
                    duck_shapes[release] = fx.duck_shape(n, triggers, 0.004, release, 0.02)
                x = fx.apply_duck(np.asarray(x, dtype=np.float32), duck_shapes[release], duck)
            measured = dsp.loud_part_lufs(x)
            if measured < SILENT_LUFS:
                _log(f"{name}: below {SILENT_LUFS} LUFS after processing, skipped")
                continue
            target = mixprofile.REFERENCE_LUFS + float(layer_settings["level"]) + float(layer_settings["gain_db"])
            gain = float(dsp.db_to_lin(target - measured))
            stereo = _place(x * np.float32(gain), float(layer_settings.get("pan", 0.0)), float(layer_settings.get("width", 1.0)),
                            bool(layer_settings.get("mono")))
            bus = layer_settings["bus"]
            buses[bus] += stereo
            is_vocal = bus == "vocals"
            for send, level in (("reverb", layer_settings.get("reverb", 0.0)), ("delay", layer_settings.get("delay", 0.0))):
                if level:
                    sends[("vox_" if is_vocal else "") + send] += stereo * np.float32(level)
            report_tracks[name] = {"role": track.get("role"), "bus": bus, "raw_lufs": round(measured, 2),
                                   "target_lufs": round(target, 2), "gain_db": round(target - measured, 2),
                                   "peak_db": round(float(dsp.lin_to_db(np.max(np.abs(stereo)))), 2)}
            if stem_dir:
                stem_paths.append(export.write_audio(os.path.join(stem_dir, f"{name}.flac"), stereo))
            _log(f"{name}: {measured:.1f} -> {target:.1f} LUFS ({target - measured:+.1f} dB) on {bus}")

    del raw, x, stereo                                   # the last track's buffers would otherwise live through mastering
    for name in BUS_ORDER:
        chain = (profile.get("buses") or {}).get(name, mixprofile.BUS_CHAINS[name])
        if chain and np.any(buses[name]):
            buses[name] = np.asarray(fx.apply_chain(buses[name], chain, ctx), dtype=np.float32)
    carve = float(master.get("vocal_carve") or 0.0)
    if carve < 0 and np.any(buses["vocals"]):
        buses["music"] = _band_carve(buses["music"], buses["vocals"], carve)

    mix = np.zeros((n, 2), dtype=np.float32)
    for name in BUS_ORDER:
        mix += buses[name]
    for name, cfg in returns_cfg.items():                # one return at a time: its send is freed before the next
        dry = sends.pop(name)
        if not np.any(dry):
            continue
        if "time" in cfg:
            wet = fx.delay(dry, cfg["time"], cfg.get("feedback", 0.35), 1.0, True, cfg.get("damp", 4500.0),
                           cfg.get("lowcut", 300.0), ctx)
        else:
            wet = fx.reverb(dry, cfg.get("decay", 2.0), cfg.get("predelay", 0.02), cfg.get("damp", 6000.0),
                            cfg.get("lowcut", 250.0), cfg.get("size", 1.0), 1.0, ctx)
        del dry
        wet = np.asarray(wet, dtype=np.float32)
        if cfg.get("duck", 0.0) < 0 and len(triggers):
            release = master["sidechain_release"] * seconds_per_beat
            if release not in duck_shapes:
                duck_shapes[release] = fx.duck_shape(n, triggers, 0.004, release)
            wet = fx.apply_duck(wet, duck_shapes[release], cfg["duck"])
        mix += wet
        buses["vocals" if name.startswith("vox_") else "fx"] += wet       # returns travel with their bus stem
        del wet
    mix = apply_automation(mix, project.get("master_automation"), seconds_per_beat, _onsets(project["tracks"]))
    fade = float(master.get("fade_out") or 0.0) * seconds_per_beat
    envelope = np.ones(n, dtype=np.float32)
    song_end = min(n, int(meta["beats"] * seconds_per_beat * SR))
    if n > song_end:                                     # what rings on after the last bar dies away over the whole tail
        envelope[song_end:] = (1.0 - np.linspace(0.0, 1.0, n - song_end)) ** TAIL_FADE_POWER
    if fade > 0:                                         # a musical fade-out ends with the last bar
        start = max(0, song_end - int(fade * SR))
        envelope[start:song_end] = np.linspace(1.0, 0.0, song_end - start) ** 2
        envelope[song_end:] = 0.0
    mix *= envelope[:, None]
    del duck_shapes
    handed = [mix]                                       # mastering takes the only reference and frees it early
    del mix
    mastered, stats = master_chain(handed, master, ctx)
    gain = float(dsp.db_to_lin(stats["gain_db"]))
    bus_report = {name: round(dsp.loud_part_lufs(buses[name]), 2) for name in BUS_ORDER if np.any(buses[name])}
    _log(f"master: {stats}")
    scale = (envelope * np.float32(gain))[:, None]
    audible = {}
    for name in BUS_ORDER:                               # scaled in place: a copy of every bus would double the memory
        if np.any(buses[name]):
            buses[name] *= scale
            audible[name] = buses[name]
    mastered = np.asarray(mastered, dtype=np.float32)
    loud = np.nonzero(np.abs(mastered).max(axis=1) > TRAILING_SILENCE_LEVEL)[0]
    keep = min(n, max(song_end, int(loud[-1]) if len(loud) else 0) + int(TRAILING_SILENCE_S * SR))
    mastered, audible = mastered[:keep], {name: bus[:keep] for name, bus in audible.items()}     # no dead air after the tail
    return {"master": mastered, "buses": audible,
            "stems": stem_paths, "premaster_gain": gain,
            "report": {"mix_style": style["name"], "tracks": report_tracks, "buses_lufs": bus_report, "master": stats,
                       "settings": {"master": master, "returns": returns_cfg}}}
