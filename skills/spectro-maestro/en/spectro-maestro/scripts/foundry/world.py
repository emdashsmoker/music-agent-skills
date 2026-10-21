# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
# Part of Spectro Maestro. See LICENSE and THIRD-PARTY-NOTICES.md at the root of the skill.
"""WORLD vocoder access (pyworld).

Standard library only, so the environment report can use it before any package is installed."""
from __future__ import annotations

import sys
import types


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
