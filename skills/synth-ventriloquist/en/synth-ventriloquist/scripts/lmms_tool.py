#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
"""Command line for the lmmskit toolkit. Run `python lmms_tool.py <command> -h` for the options of a command.

Songs themselves are written as short Python scripts with lmmskit.compose (see SKILL.md); this tool covers
everything around them: environment check, inspection and lint of any .mmp, rendering, mixing by measurement,
checks with figures, exports, and the vocal utilities.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _print(data) -> None:
    print(json.dumps(data, indent=1, ensure_ascii=False, default=float))


PACKAGES = {  # import name: (name to install, what is missing without it)
    "numpy": ("numpy", "core"), "scipy": ("scipy", "core"), "soundfile": ("soundfile", "core"), "matplotlib": ("matplotlib", "review figures"),
    "onnxruntime": ("onnxruntime", "all vocals"), "kokoro_onnx": ("kokoro-onnx", "Kokoro voices and English fallback pronunciation"),
    "pyworld": ("pyworld", "speech voices singing"), "onnx": ("onnx", "Piper timing and the Kokoro 'held' method"),
    "piper": ("piper-tts", "Piper voices"), "faster_whisper": ("faster-whisper", "recognition check of sung lines"),
    "yaml": ("pyyaml", "singer voicebanks"), "xmlschema": ("xmlschema", "DAWproject schema validation (optional)"),
    "imageio_ffmpeg": ("imageio-ffmpeg", "an ffmpeg binary without administrator rights (optional, only when ffmpeg is missing)"),
}


def cmd_doctor(args) -> None:
    """Report what this machine has and what each missing piece disables. Changes nothing."""
    import importlib.util
    from lmmskit import kit, render, settings
    status = {"environment": settings.environment()}
    candidates = settings.lmms_candidates()
    if candidates:
        version = render.lmms_version()
        status["lmms"] = {"used": render.find_lmms(), "found_by": candidates[0]["source"], "sandbox": candidates[0]["sandbox"],
                          "version": version, "data_dir": render.find_data_dir(), "one_core_renders": render.can_pin(),
                          "other_candidates": [" ".join(c["command"]) for c in candidates[1:]]}
        if not render.version_is_tested(version):
            status["lmms"]["note"] = (f"this toolkit was written against LMMS {render.TESTED_LMMS_SERIES}x; "
                                      "run selftest to see whether this version renders its projects correctly")
    else:
        status["lmms"] = {"error": "not found in the settings, on the PATH, in the usual folders or as a Flatpak: see references/setup.md"}
    status["ffmpeg"] = settings.ffmpeg_path() or "missing: ogg, mp3 and flac output unavailable (WAV works)"
    status["python_packages"] = {install: ("ok" if importlib.util.find_spec(name) else f"missing: {purpose}")
                                 for name, (install, purpose) in PACKAGES.items()}
    kit_state = kit.status()
    status["drum_kit"] = {"folder": kit_state["folder"], "state": "ready" if kit_state["ready"] else
                          "not built yet: made automatically on first use (a few seconds, needs LMMS), or now with the `kit` command"}
    status["settings"] = {key: settings.get(key) for key in settings.KEYS}
    _print(status)


def cmd_kit(args) -> None:
    """Show the drum kit made on this machine, or build it."""
    from lmmskit import kit
    if args.build or args.rebuild:
        if args.rebuild or not kit.status()["ready"]:
            _print(kit.build())
            return
    _print(kit.status())


def cmd_configure(args) -> None:
    """Show the settings, or store some in a settings file."""
    from lmmskit import settings
    if not args.set and not args.unset:
        _print({key: {"value": settings.get(key), "env": variable, "meaning": meaning} for key, (variable, _, meaning) in settings.KEYS.items()})
        print("settings files, later ones win:", *settings.settings_files(), sep="\n  ")
        return
    values = {key: None for key in args.unset}
    for item in args.set:
        key, _, text = item.partition("=")
        values[key] = settings._typed(key, text)
    target = os.path.abspath(settings.PROJECT_SETTINGS_NAME) if args.here else None
    print("saved to", settings.save(values, target))


def cmd_genres(args) -> None:
    from lmmskit import genres
    _print(genres.get(args.name) if args.name else genres.names())


def cmd_sounds(args) -> None:
    from lmmskit import audition, sounds
    if not args.names:
        by_role: dict[str, list[str]] = {}
        for name, patch in sorted(sounds.PATCHES.items()):
            by_role.setdefault(patch["role"], []).append(name)
        _print(by_role)
        return
    names = list(sounds.PATCHES) if args.names == ["all"] else args.names
    result = audition.profile({name: name for name in names}, args.out)
    print(audition.table(result))
    if args.out:
        from lmmskit import visual
        print(visual.contact_sheet(os.path.join(args.out, "audition.wav"), list(result), audition.SLOT_SECONDS, os.path.join(args.out, "sounds.png")))


def cmd_inspect(args) -> None:
    from lmmskit import export
    from lmmskit.project import Project
    _print(export.inspect(Project.load(args.project)))


def cmd_lint(args) -> None:
    from lmmskit import compose, lint
    from lmmskit.findings import format_findings
    from lmmskit.project import Project
    found = lint.lint(Project.load(args.project), compose.load_plan(args.project), key=args.key)
    print(format_findings(found))


def cmd_render(args) -> None:
    from lmmskit import mix, render
    from lmmskit.project import Project, excerpt
    project_path = args.project
    if args.bars:
        project = Project.load(args.project)
        first, count = (float(v) for v in args.bars.split(":"))
        project_path = os.path.splitext(args.project)[0] + ".excerpt.mmp"
        excerpt(project, (first - 1) * project.beats_per_bar, count * project.beats_per_bar).save(project_path)
    wav = args.out if args.out.endswith(".wav") else os.path.splitext(args.out)[0] + ".wav"
    render.render(project_path, wav)
    if args.trim:
        print("true-peak trim dB:", mix.trim_true_peak(wav))
    if not args.out.endswith(".wav"):
        render.convert(wav, args.out)
    if args.bars:
        os.remove(project_path)
    print(args.out)


def cmd_balance(args) -> None:
    from lmmskit import mix
    _print(mix.balance(args.project, args.work, args.genre, tone_fit=not args.no_tone_fit))


def cmd_master(args) -> None:
    from lmmskit import mix
    _print(mix.master_to_loudness(args.project, args.work, args.lufs))


def cmd_check(args) -> None:
    from lmmskit import pipeline
    from lmmskit.findings import format_findings
    report = pipeline.check(args.project, args.out, args.genre, args.lufs, figures=not args.no_figures)
    print(format_findings(report["findings"]))
    print("figures:", report["figures"])


def cmd_produce(args) -> None:
    from lmmskit import pipeline
    from lmmskit.findings import format_findings
    report = pipeline.produce(args.project, args.out, args.genre, args.lufs, balance=not args.no_balance, repeat_check=not args.no_repeat_check,
                              tone_fit=not args.no_tone_fit)
    print(format_findings(report["findings"]))
    _print({"files": report["files"], "figures": report["figures"], "steps": report["steps"]})


def cmd_export(args) -> None:
    from lmmskit import export, mix
    from lmmskit.project import Project
    project = Project.load(args.project)
    roles = {name: info["role"] for name, info in mix.roles_of(args.project, project).items()}
    if args.midi:
        print(export.to_midi(project, args.midi, roles))
    if args.json:
        print(export.to_json(project, args.json))
    if args.dawproject:
        stems = mix.render_stems(args.project, args.stems) if args.stems else None
        print(export.to_dawproject(project, args.dawproject, roles=roles, stems=stems))
        try:
            print("schema errors:", export.validate_dawproject(args.dawproject))
        except ImportError:
            print("schema not validated (pip install xmlschema)")
    if args.mmp:
        print(project.save(args.mmp))


def cmd_import_json(args) -> None:
    from lmmskit import export
    print(export.from_json(args.json).save(args.out))


def cmd_pack(args) -> None:
    from lmmskit import pipeline
    print(pipeline.pack(args.project, args.out))


def cmd_voices(args) -> None:
    from lmmskit.vocal import engines, tts
    if args.voice:
        info = engines.describe_voice(args.voice)
        if args.voice.startswith("kokoro:") and args.range:
            from lmmskit.vocal import kokoro_native
            info["held_method_range"] = kokoro_native.clean_range(args.voice)
        _print(info)
    else:
        _print({"defaults": tts.DEFAULT_VOICE, "voices": tts.VOICES})


def cmd_sing(args) -> None:
    from lmmskit.vocal import asr, engines, lines
    options = {"fix_ending": False} if args.no_ending_fix else {}
    sung, report = engines.render_line(args.voice, lines.Line(args.text, args.melody), args.bpm, method=args.method, lang=args.lang, cache=args.cache, **options)
    lines.write_wav(args.out, sung.audio)
    report["recognition"] = asr.score_line(sung.audio, 44100, args.text, language=args.lang) if not args.no_asr else None
    _print(report)
    print(args.out)


def cmd_compare(args) -> None:
    from lmmskit.vocal import lyrics
    _print(lyrics.compare(args.voice, args.melody, args.texts, args.bpm, cache=args.cache, out_dir=args.out, method=args.method, lang=args.lang))


def cmd_lyric_lint(args) -> None:
    from lmmskit.findings import format_findings
    from lmmskit.vocal import lines, lyrics
    print(format_findings(lyrics.lint_line(args.voice, lines.Line(args.text, args.melody), args.bpm, role=args.kind)) or "no findings")


def _selftest_song(folder: str, vocal: bool) -> str:
    from lmmskit.compose import Song
    song = Song("Self Test", 128, "A minor", "house")
    song.structure([("a", 8)])
    chords = song.chords("a", "Am F C G", repeats=2)
    song.add("kick", "house_kick").hits("a", "x---x---x---x---", bars=8)
    song.add("hat", "909_hat").hits("a", "--x---x---x---x-", bars=8)
    song.add("bass", "moog_bass").riff("a", chords, ". . R . . . R . . . R . . R . 8", octave=1)
    song.add("pad", "warm_pad").chords("a", chords, octave=3)
    if vocal:
        song.vocal("lead vocal", "kokoro:af_heart").line(("a", 4), "Hold on to the morning light", "E4/1 E4/0.5 G4/0.5 A4/1 A4/0.5 G4/0.5 E4/2")
    song.sidechain("kick", ["bass", "music"], depth_db=5)
    song.sweep("pad", "a", 8, 500, 8000)
    song.master()
    return song.save(os.path.join(folder, "selftest.mmp"))


def cmd_selftest(args) -> None:
    """Build, render, check and export a tiny song to prove the installation works."""
    import hashlib
    import shutil
    import tempfile
    from lmmskit import compose, export, lint, pipeline, render, settings
    from lmmskit.project import Project
    failures = []

    def record(name: str, passed: bool, detail: str = "") -> None:
        print(f"{'ok  ' if passed else 'FAIL'} {name}{' - ' + detail if detail else ''}")
        if not passed:
            failures.append(name)
    with tempfile.TemporaryDirectory() as folder:
        path = _selftest_song(folder, args.vocal)
        found = lint.lint(Project.load(path), compose.load_plan(path))
        record("project written and lint clean", not [f for f in found if f["severity"] != "info"], "; ".join(f["code"] for f in found if f["severity"] != "info"))
        digests = []
        for index in (1, 2):
            with open(render.render(path, os.path.join(folder, f"render{index}.wav")), "rb") as handle:
                digests.append(hashlib.md5(handle.read()).hexdigest())
        record("two renders are identical", digests[0] == digests[1])
        formats = pipeline.AUDIO_FORMATS if settings.ffmpeg_path() else ()
        report = pipeline.produce(path, os.path.join(folder, "out"), formats=formats, repeat_check=False)
        master = next(f["data"] for f in report["findings"] if f["code"] == "master_summary")
        record("balance, loudness and mix checks", report["worst"] != "error" and master["lufs_integrated"] > -30, f"{master['lufs_integrated']} LUFS, true peak {master['true_peak_db']} dBTP")
        record("audio files", all(os.path.getsize(report["files"][f]) > 1024 for f in ("wav", *formats)), "ogg and mp3 skipped: ffmpeg missing" if not formats else "")
        record("figures", all(os.path.exists(p) for p in report["figures"].values()) and len(report["figures"]) >= 4)
        midi_notes = export.read_midi_notes(report["files"]["midi"])
        record("MIDI export reads back", len(midi_notes.get("kick", [])) == 32, f"{len(midi_notes.get('kick', []))} kick notes")
        record("JSON export restores the project", export.from_json(report["files"]["json"]).to_bytes() == Project.load(report["files"]["project"]).to_bytes())
        try:
            errors = export.validate_dawproject(report["files"]["dawproject"])
            record("DAWproject validates against the schema", not errors, "; ".join(errors[:2]))
        except ImportError:
            record("DAWproject written", os.path.getsize(report["files"]["dawproject"]) > 1024, "schema check skipped: xmlschema missing")
        if args.vocal:
            scores = [f for f in report["findings"] if f["code"] == "vocal_scores"]
            record("sung line rendered and recognised", bool(scores) and min(scores[0]["data"]["scores"]) > 0.5, scores[0]["message"] if scores else "no vocal report")
    print("self-test passed" if not failures else f"self-test failed: {', '.join(failures)}")
    if failures:
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)

    def add(name, function, *arguments):
        sub = commands.add_parser(name, help=function.__doc__ or "")
        for flags, options in arguments:
            sub.add_argument(*flags, **options)
        sub.set_defaults(run=function)
    project = (("project",), {"help": ".mmp or .mmpz file"})
    genre = (("--genre",), {"default": None, "help": "genre profile (default: from the plan file)"})
    voice = (("--voice",), {"required": True, "help": "kokoro:<v>, piper:<v> or diffsinger:<folder>[#colour]"})
    melody = (("--melody",), {"required": True, "help": "e.g. 'E4/1 G4/0.5 A4/2'"})
    bpm = (("--bpm",), {"type": float, "default": 120.0})
    method = (("--method",), {"default": "auto", "choices": ["auto", "stretched", "held"]})
    lang = (("--lang",), {"default": "en"})
    cache = (("--cache",), {"default": None, "help": "folder for cached lines"})
    add("doctor", cmd_doctor)
    add("kit", cmd_kit, (("--build",), {"action": "store_true", "help": "make the kit now if it is not complete"}),
        (("--rebuild",), {"action": "store_true", "help": "make the whole kit again (records the drum-machine hits anew)"}))
    add("configure", cmd_configure,
        (("--set",), {"action": "append", "default": [], "metavar": "KEY=VALUE", "help": "store a setting (repeatable). A command is written as a JSON list"}),
        (("--unset",), {"action": "append", "default": [], "metavar": "KEY", "help": "remove a stored setting (repeatable)"}),
        (("--here",), {"action": "store_true", "help": "write lmmskit.json in the current folder instead of the user's settings file"}))
    add("selftest", cmd_selftest, (("--vocal",), {"action": "store_true", "help": "also sing one line with the default speech voice"}))
    add("genres", cmd_genres, (("name",), {"nargs": "?", "help": "show one profile"}))
    add("sounds", cmd_sounds, (("names",), {"nargs": "*", "help": "patch names to audition, or 'all'"}), (("--out",), {"default": None}))
    add("inspect", cmd_inspect, project)
    add("lint", cmd_lint, project, (("--key",), {"default": None, "help": "e.g. 'A minor' when there is no plan file"}))
    add("render", cmd_render, project, (("-o", "--out"), {"required": True, "help": ".wav, .ogg, .mp3 or .flac"}),
        (("--bars",), {"default": None, "help": "first:count, e.g. 33:8 renders 8 bars from LMMS bar 33"}),
        (("--trim",), {"action": "store_true", "help": "lower to -1 dBTP if needed"}))
    tone = (("--no-tone-fit",), {"action": "store_true", "help": "keep the tone as mixed: no high shelf on a dull mix"})
    add("balance", cmd_balance, project, genre, tone, (("--work",), {"required": True, "help": "work folder for stems"}))
    add("master", cmd_master, project, (("--lufs",), {"type": float, "required": True}), (("--work",), {"required": True}))
    add("check", cmd_check, project, genre, (("-o", "--out"), {"required": True}), (("--lufs",), {"type": float, "default": None}),
        (("--no-figures",), {"action": "store_true"}))
    add("produce", cmd_produce, project, genre, (("-o", "--out"), {"required": True}), (("--lufs",), {"type": float, "default": None}),
        (("--no-balance",), {"action": "store_true", "help": "keep the fader levels as they are"}), tone,
        (("--no-repeat-check",), {"action": "store_true", "help": "skip the second render that proves the result is repeatable"}))
    add("export", cmd_export, project, (("--midi",), {"default": None}), (("--json",), {"default": None}), (("--dawproject",), {"default": None}),
        (("--stems",), {"default": None, "help": "folder: render stems and include them in the .dawproject"}),
        (("--mmp",), {"default": None, "help": "save a copy as .mmp or .mmpz"}))
    add("import-json", cmd_import_json, (("json",), {}), (("-o", "--out"), {"required": True}))
    add("pack", cmd_pack, project, (("-o", "--out"), {"required": True, "help": "zip to write"}))
    add("voices", cmd_voices, (("voice",), {"nargs": "?"}), (("--range",), {"action": "store_true", "help": "probe the Kokoro 'held' range"}))
    add("sing", cmd_sing, voice, melody, bpm, method, lang, cache, (("--text",), {"required": True}), (("-o", "--out"), {"required": True}),
        (("--no-asr",), {"action": "store_true"}),
        (("--no-ending-fix",), {"action": "store_true", "help": "speech voices: leave the last syllable as spoken"}))
    add("compare", cmd_compare, voice, melody, bpm, method, lang, cache, (("texts",), {"nargs": "+", "help": "candidate wordings"}),
        (("--out",), {"default": None, "help": "folder for the candidate WAVs"}))
    add("lyric-lint", cmd_lyric_lint, voice, melody, bpm, (("--text",), {"required": True}), (("--kind",), {"default": "verse"}))
    args = parser.parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
