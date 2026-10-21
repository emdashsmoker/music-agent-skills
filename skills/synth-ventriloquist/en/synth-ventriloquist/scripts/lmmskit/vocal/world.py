# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
"""WORLD vocoder access (pyworld) with the analysis settings shared by the singing code."""
from __future__ import annotations

import numpy as np

FRAME_S = 0.005                                  # 5 ms analysis and synthesis grid
F0_FLOOR, F0_CEIL = 60.0, 1000.0
PERIODIC_BAND_HZ = 4000.0                        # periodicity is read from the aperiodicity below this
VOICED_MIN_PERIODICITY = 0.5                     # below this a frame is breath or hiss, whatever the pitch tracker says
VOICED_LEVEL_RANGE_DB = 24.0                     # frames this far under the loud frames are closures and pauses
LOUD_PERCENTILE = 90


def pyworld():
    """Import pyworld. An import error naming pkg_resources is covered under Troubleshooting in references/setup.md."""
    import pyworld as module
    return module


def harvest_f0(audio: np.ndarray, sr: int, f0_floor: float = F0_FLOOR, f0_ceil: float = F0_CEIL) -> tuple[np.ndarray, np.ndarray]:
    """(f0 in Hz, frame times in seconds) on the 5 ms grid from Harvest alone. Harvest is slower than DIO but far
    steadier; the pitch checks and the vocal_line figure need this track and no envelope."""
    x = np.ascontiguousarray(audio, dtype=np.float64)
    return pyworld().harvest(x, sr, f0_floor=f0_floor, f0_ceil=f0_ceil, frame_period=FRAME_S * 1000)


def analyze(audio: np.ndarray, sr: int, f0_floor: float = F0_FLOOR, f0_ceil: float = F0_CEIL):
    """(f0, spectral envelope, aperiodicity) on the 5 ms grid."""
    pw = pyworld()
    x = np.ascontiguousarray(audio, dtype=np.float64)
    f0, times = harvest_f0(x, sr, f0_floor, f0_ceil)
    fft_size = pw.get_cheaptrick_fft_size(sr, f0_floor)       # both estimators must share one spectrum size
    envelope = pw.cheaptrick(x, f0, times, sr, f0_floor=f0_floor, fft_size=fft_size)
    aperiodicity = pw.d4c(x, f0, times, sr, fft_size=fft_size)
    return f0, envelope, aperiodicity


def periodicity(aperiodicity: np.ndarray, sr: int) -> np.ndarray:
    """Share of the energy below 4 kHz that is periodic, per frame (0 = noise, 1 = pure voice)."""
    bins = max(1, int(aperiodicity.shape[1] * PERIODIC_BAND_HZ / (0.5 * sr)))
    return 1.0 - aperiodicity[:, :bins].mean(axis=1)


def truly_voiced(f0: np.ndarray, envelope: np.ndarray, aperiodicity: np.ndarray, sr: int) -> np.ndarray:
    """Voiced frames. The pitch tracker reports a pitch through aspiration, hiss and even stop closures, so a frame
    counts only when it is also periodic and not far below the loud frames of the take."""
    level = 10.0 * np.log10(envelope.sum(axis=1) + 1e-12)
    loud = np.percentile(level, LOUD_PERCENTILE) if len(level) else 0.0
    return (f0 > 0) & (periodicity(aperiodicity, sr) >= VOICED_MIN_PERIODICITY) & (level >= loud - VOICED_LEVEL_RANGE_DB)


def synthesize(f0: np.ndarray, envelope: np.ndarray, aperiodicity: np.ndarray, sr: int) -> np.ndarray:
    return pyworld().synthesize(np.ascontiguousarray(f0), np.ascontiguousarray(envelope), np.ascontiguousarray(aperiodicity),
                                sr, FRAME_S * 1000)


def quick_f0(audio: np.ndarray, sr: int) -> np.ndarray:
    """Fast f0 track (DIO) for voicing decisions."""
    f0, _ = pyworld().dio(np.ascontiguousarray(audio, dtype=np.float64), sr, f0_floor=F0_FLOOR, f0_ceil=F0_CEIL,
                          frame_period=FRAME_S * 1000)
    return f0
