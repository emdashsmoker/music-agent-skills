# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
"""Finding records shared by every check (lint, mix, vocals) and their text rendering."""
from __future__ import annotations

SEVERITY_ORDER = {"error": 0, "warn": 1, "info": 2}


def finding(severity: str, code: str, message: str, **data) -> dict:
    """severity: 'error' (must fix), 'warn' (look at it), 'info' (context for judgement)."""
    return {"severity": severity, "code": code, "message": message, "data": data}


def format_findings(findings: list[dict], examples: int = 4) -> str:
    lines = []
    for item in sorted(findings, key=lambda f: SEVERITY_ORDER[f["severity"]]):
        lines.append(f"[{item['severity'].upper():5s}] {item['code']}: {item['message']}")
        for example in item["data"].get("examples", [])[:examples]:
            lines.append(f"          - {example}")
        for row in item["data"].get("table", []):
            lines.append(f"          {row}")
    return "\n".join(lines)


def worst(findings: list[dict]) -> str:
    return min((f["severity"] for f in findings), key=lambda s: SEVERITY_ORDER[s], default="info")
