# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
"""WORLD vocoder access (pyworld) with the analysis settings shared by the singing code."""
from __future__ import annotations

import sys
import types

import numpy as np

FRAME_S = 0.005                                  # 5 ms analysis and synthesis grid
F0_FLOOR, F0_CEIL = 60.0, 1000.0


def pyworld():
    """Import pyworld. Its __init__ needs pkg_resources only to read a version string; newer setuptools
    no longer ship that module, so a stand-in is provided when it is missing."""
    if "pkg_resources" not in sys.modules:
        try:
            import pkg_resources                 # noqa: F401
        except ModuleNotFoundError:
            stub = types.ModuleType("pkg_resources")
            stub.get_distribution = lambda name: types.SimpleNamespace(version="unknown")
            sys.modules["pkg_resources"] = stub
    import pyworld as module
    return module


def analyze(audio: np.ndarray, sr: int, f0_floor: float = F0_FLOOR, f0_ceil: float = F0_CEIL):
    """(f0, spectral envelope, aperiodicity) on the 5 ms grid. Harvest is slower than DIO but far steadier."""
    pw = pyworld()
    x = np.ascontiguousarray(audio, dtype=np.float64)
    f0, times = pw.harvest(x, sr, f0_floor=f0_floor, f0_ceil=f0_ceil, frame_period=FRAME_S * 1000)
    fft_size = pw.get_cheaptrick_fft_size(sr, f0_floor)       # both estimators must share one spectrum size
    envelope = pw.cheaptrick(x, f0, times, sr, f0_floor=f0_floor, fft_size=fft_size)
    aperiodicity = pw.d4c(x, f0, times, sr, fft_size=fft_size)
    return f0, envelope, aperiodicity


def synthesize(f0: np.ndarray, envelope: np.ndarray, aperiodicity: np.ndarray, sr: int) -> np.ndarray:
    return pyworld().synthesize(np.ascontiguousarray(f0), np.ascontiguousarray(envelope), np.ascontiguousarray(aperiodicity),
                                sr, FRAME_S * 1000)


def quick_f0(audio: np.ndarray, sr: int) -> np.ndarray:
    """Fast f0 track (DIO) for voicing decisions."""
    f0, _ = pyworld().dio(np.ascontiguousarray(audio, dtype=np.float64), sr, f0_floor=F0_FLOOR, f0_ceil=F0_CEIL,
                          frame_period=FRAME_S * 1000)
    return f0
