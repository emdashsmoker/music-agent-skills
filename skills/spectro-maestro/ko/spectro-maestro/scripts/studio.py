#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
# Part of Spectro Maestro. See LICENSE and THIRD-PARTY-NOTICES.md at the root of the skill.
"""Spectro Maestro command line. Run `python studio.py <command> -h` for the options of a command.

Song files are YAML specs; `render` and `export` also accept a project JSON written by an earlier run.
`doctor` reports what this machine has and needs; it runs before any package is installed.
Settings (folders, outside tools, offline mode) come from options, SPECTRO_MAESTRO_<NAME> environment variables
or a JSON config file; `doctor` lists them."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from foundry import settings  # noqa: E402  (standard library only)

GLOBAL_OPTIONS = ("--config",)


def _doctor_requested(argv: list) -> bool:
    """`doctor` must answer even when no package is installed yet, so it is recognised before anything is imported."""
    words = [word for index, word in enumerate(argv) if not word.startswith("-") and (index == 0 or argv[index - 1] not in GLOBAL_OPTIONS)]
    return bool(words) and words[0] == "doctor"


def _early_doctor(argv: list) -> int:
    for index, word in enumerate(argv):
        if word in GLOBAL_OPTIONS and index + 1 < len(argv):
            settings.override(word.lstrip("-"), argv[index + 1])
    from foundry import doctor
    return doctor.run()


def _utf8_console() -> None:
    """Lyrics and phoneme symbols must not crash a console that uses a legacy code page (Windows)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


_utf8_console()
if __name__ == "__main__" and _doctor_requested(sys.argv[1:]):
    sys.exit(_early_doctor(sys.argv[1:]))

try:
    import yaml  # noqa: E402
    from foundry import export, genres, instruments, songfile, spec  # noqa: E402
except ImportError as error:
    print(f"ERROR: a required package is missing ({error}). Run `{os.path.basename(sys.executable)} {os.path.abspath(__file__)} doctor` "
          "to see what to install.", file=sys.stderr)
    sys.exit(2)

DEFAULT_FORMATS = "wav,mp3,mid"


def _fail(error: Exception) -> int:
    print(f"ERROR: {error}", file=sys.stderr)
    return 2


def _out_dir(args) -> str:
    """Output folder: next to the song, named after it (a project JSON shares the folder of its song)."""
    return args.output or os.path.splitext(args.song)[0].removesuffix(".project") + "_out"


def cmd_genres(args) -> int:
    if args.genre:
        data = genres.load(args.genre)
        print(f"{data.get('name', args.genre)}  bpm {data['bpm'][0]}-{data['bpm'][1]} (default {data['bpm'][2]})")
        print(f"keys: {', '.join(data['keys'])}\n\n{data.get('about', '').strip()}")
        return 0
    for genre_id in genres.available():
        data = genres.load(genre_id)
        print(f"{genre_id:22s} {data['bpm'][0]:>3}-{data['bpm'][1]:<3} bpm  {data.get('name', '')}: {data.get('summary', '')}")
    return 0


def cmd_new(args) -> int:
    song = genres.starter_song(args.genre, args.title, args.bpm, args.key)
    if os.path.exists(args.output) and not args.force:
        return _fail(FileExistsError(f"{args.output} exists; pass --force to overwrite"))
    class Plain(yaml.SafeDumper):                       # templates share blocks through anchors; write them out in full
        def ignore_aliases(self, data):
            return True
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as handle:
        yaml.dump(song, handle, Dumper=Plain, sort_keys=False, allow_unicode=True, width=160, default_flow_style=None)
    print(f"wrote {args.output}  ({song['bpm']} bpm, {song['key']}, {len(song['sections'])} sections, {len(song['tracks'])} tracks)")
    return 0


def cmd_instruments(args) -> int:
    for kind, names in instruments.all_names().items():
        if args.kind in (None, kind):
            print(f"[{kind}] " + " ".join(names))
    return 0


def cmd_audition(args) -> int:
    """Render one instrument alone (a note, or a short pattern) with a picture of it."""
    import numpy as np
    from foundry import dsp, fx, plots, theory
    patch = yaml.safe_load(args.patch) if args.patch else {}
    resolved = instruments.resolve({"base": args.inst, **patch} if patch else args.inst)
    ctx = fx.FxContext(args.bpm, 1)
    pitches = [theory.note_to_midi(n) for n in args.notes.split(",")]
    notes = [[i * args.beats, args.beats * args.gate, p, args.velocity] for i, p in enumerate(pitches)]
    n = int((len(notes) * args.beats * 60 / args.bpm + 1.0) * dsp.SR)
    audio = instruments.render_track(resolved, notes, ctx, n, 1)
    audio = audio / (np.max(np.abs(audio)) + 1e-9) * 0.8
    os.makedirs(args.output, exist_ok=True)
    wav = export.write_audio(os.path.join(args.output, f"{args.inst}.wav"), audio)
    png = plots.audition(audio, os.path.join(args.output, f"{args.inst}.png"))
    mono = dsp.to_mono(audio)
    spectrum = np.abs(np.fft.rfft(mono))
    freqs = np.fft.rfftfreq(len(mono), 1 / dsp.SR)
    envelope = dsp.one_pole_smooth(np.abs(mono), 0.01)
    above = np.nonzero(envelope > envelope.max() * 0.1)[0]
    print(json.dumps({"wav": wav, "png": png, "kind": resolved["kind"],
                      "centroid_hz": round(float(np.sum(freqs * spectrum) / np.sum(spectrum))),
                      "peak_hz": round(float(freqs[np.argmax(spectrum)]), 1),
                      "time_above_minus20db_s": round(float((above[-1] - above[0]) / dsp.SR), 3) if len(above) else 0}))
    return 0


def cmd_lint(args) -> int:
    from foundry import lint
    try:
        project = songfile.load(args.song)
    except (spec.SpecError, KeyError) as error:
        return _fail(error)
    issues = lint.check_project(project)
    if not args.no_vocal:
        issues += lint.check_vocals(project, args.models)
    print(lint.format_report(project, issues))
    return 1 if any(i["level"] == "error" for i in issues) else 0


def cmd_render(args) -> int:
    from foundry import mixer, plots, qa
    started = time.time()
    try:
        project = songfile.load(args.song, args.sections)
    except (spec.SpecError, KeyError) as error:
        return _fail(error)
    out_dir = _out_dir(args)
    build = os.path.join(out_dir, "build")
    os.makedirs(build, exist_ok=True)
    profile = genres.profile_of(project["meta"].get("genre"))
    only = [name.strip() for name in args.only.split(",")] if args.only else None
    stem_dir = os.path.join(out_dir, "stems")
    rendered = mixer.render(project, build, profile, only, stem_dir if args.stems else None)
    name = os.path.splitext(os.path.basename(args.song))[0].replace(".project", "")
    written = []
    for fmt in [f.strip() for f in args.formats.split(",") if f.strip()]:
        target = os.path.join(out_dir, f"{name}.{fmt}")
        written.append(export.write_midi(project, target) if fmt == "mid" else export.write_audio(target, rendered["master"]))
    written.append(export.save_project(project, os.path.join(out_dir, f"{name}.project.json")))
    for bus, audio in rendered["buses"].items():
        export.write_audio(os.path.join(stem_dir, f"bus_{bus}.flac"), audio)
    report = {"mix": rendered["report"]}
    if not args.no_qa:
        qa_dir = os.path.join(out_dir, "qa")
        metrics = qa.measure(project, rendered)
        found = qa.findings(metrics, profile.get("qa"))
        report.update({"metrics": metrics, "findings": found})
        pictures = [plots.overview(project, rendered, os.path.join(qa_dir, "overview.png")),
                    plots.spectrogram(rendered["master"], os.path.join(qa_dir, "spectrogram.png"), project),
                    plots.spectrum(rendered, os.path.join(qa_dir, "spectrum.png"),
                                   tuple((profile.get("qa") or {}).get("slope_db_per_octave", qa.THRESHOLDS["slope_db_per_octave"]))),
                    plots.arrangement(project, os.path.join(qa_dir, "arrangement.png")),
                    plots.pianoroll(project, os.path.join(qa_dir, "pianoroll.png")),
                    plots.stereo(rendered["master"], os.path.join(qa_dir, "stereo.png"), project)]
        print("\n== metrics ==")
        print(json.dumps({k: v for k, v in metrics.items() if k not in ("sections", "vocal_by_section")}, ensure_ascii=False))
        print("== sections ==")
        for row in metrics["sections"]:
            print(f"  {row['name']:14s} energy {row['energy']:.2f}  {row['lufs']:6.1f} LUFS  centroid {row['centroid_hz']:5d} Hz  {row['buses_lufs']}")
        print(f"== findings ({len(found)}) ==")
        for item in found:
            print(f"  [{item['key']}] {item['value']} (expected {item['range']}): {item['message']}. Try: {item['try']}")
        print("== pictures to look at ==\n  " + "\n  ".join(pictures))
    with open(os.path.join(out_dir, "report.json"), "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=1)
    print("== files ==\n  " + "\n  ".join(written))
    print(f"done in {time.time() - started:.0f} s")
    return 0


def cmd_plot(args) -> int:
    """Extra pictures on demand: a piano roll of one section, a zoomed spectrogram, an effect-chain response."""
    import soundfile as sf
    from foundry import fx, plots
    project = songfile.load(args.song)
    out_dir = _out_dir(args)
    qa_dir = os.path.join(out_dir, "qa")
    if args.pianoroll:
        print(plots.pianoroll(project, os.path.join(qa_dir, f"pianoroll_{args.pianoroll}.png"), args.pianoroll, args.bars))
    if args.spectrogram:
        audio, _ = sf.read(args.spectrogram)
        window = (args.start, args.end) if args.end else None
        tag = os.path.splitext(os.path.basename(args.spectrogram))[0]
        print(plots.spectrogram(audio, os.path.join(qa_dir, f"spectrogram_{tag}_{int(args.start)}_{int(args.end or 0)}.png"),
                                None if window else project, args.top, window))
    if args.chain:
        track = next(t for t in project["tracks"] if t["name"] == args.chain)
        chain = (track.get("mix") or {}).get("inserts") or []
        print(plots.chain_response(chain, os.path.join(qa_dir, f"chain_{args.chain}.png"), fx.FxContext(project["meta"]["bpm"])))
    return 0


def cmd_export(args) -> int:
    try:
        project = songfile.load(args.song)
    except (spec.SpecError, KeyError) as error:
        return _fail(error)
    out_dir = _out_dir(args)
    name = os.path.splitext(os.path.basename(args.song))[0].replace(".project", "")
    for target in [t.strip() for t in args.to.split(",")]:
        if target == "json":
            print(export.save_project(project, os.path.join(out_dir, f"{name}.project.json")))
        elif target == "midi":
            print(export.write_midi(project, os.path.join(out_dir, f"{name}.mid")))
        elif target == "lmms":
            from foundry import daw_lmms
            print(daw_lmms.write(project, os.path.join(out_dir, "lmms"), name, os.path.join(out_dir, "stems")))
        elif target == "dawproject":
            from foundry import daw_dawproject
            print(daw_dawproject.write(project, os.path.join(out_dir, f"{name}.dawproject"), os.path.join(out_dir, "stems")))
        else:
            return _fail(ValueError(f"unknown export target {target!r}; use json, midi, lmms, dawproject"))
    return 0


def cmd_import_midi(args) -> int:
    from foundry import importers
    song = importers.midi_to_spec(args.midi, args.bpm, args.key)
    with open(args.output, "w", encoding="utf-8") as handle:
        yaml.safe_dump(song, handle, sort_keys=False, allow_unicode=True, width=200, default_flow_style=None)
    print(f"wrote {args.output}: {len(song['tracks'])} tracks, {song['sections'][0]['bars']} bars. Assign instruments and roles, then render.")
    return 0


def cmd_lmms_check(args) -> int:
    """LMMS is an outside program that many users do not have or want; this command is the only one that needs it."""
    from foundry import lmms_tool
    command, how = lmms_tool.find()
    if not command:
        print("LMMS was not found on this machine, so the exported project was not re-rendered. The export itself is unaffected.\n"
              "If a check in LMMS is wanted: install LMMS in the form that suits this system (see references/export.md), or point\n"
              "the setting `lmms` (option --lmms, variable SPECTRO_MAESTRO_LMMS) at an existing one, e.g. an AppImage file.")
        return 3
    if args.song.lower().endswith(".mmp"):
        project_file, seconds = args.song, None
        out_dir = args.output or os.path.dirname(os.path.abspath(args.song))
    else:
        from foundry import daw_lmms
        project = songfile.load(args.song)
        out_dir = os.path.join(_out_dir(args), "lmms")
        name = os.path.splitext(os.path.basename(args.song))[0].replace(".project", "")
        project_file = os.path.join(out_dir, f"{name}.mmp")
        seconds = project["meta"]["beats"] * 60.0 / project["meta"]["bpm"]
        if not os.path.isfile(project_file):
            daw_lmms.write(project, out_dir, name, os.path.join(_out_dir(args), "stems"))
    print(f"[lmms] {' '.join(command)}  ({how})")
    try:
        report = lmms_tool.check(project_file, os.path.join(out_dir, "lmms_check.wav"), seconds)
    except RuntimeError as error:
        return _fail(error)
    print(json.dumps(report))
    if report["clipped_samples"]:
        print("the LMMS render clips: lower the track volumes in the project")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", help="JSON settings file (default: ./spectro-maestro.json, then the user config folder)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("genres", help="list genres, or show one genre's conventions")
    p.add_argument("genre", nargs="?")
    p.set_defaults(run=cmd_genres)

    p = sub.add_parser("new", help="write a starter song spec for a genre")
    p.add_argument("genre")
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--title")
    p.add_argument("--bpm", type=float)
    p.add_argument("--key")
    p.add_argument("--force", action="store_true")
    p.set_defaults(run=cmd_new)

    p = sub.add_parser("instruments", help="list instrument names")
    p.add_argument("--kind", choices=["drum", "sweep", "synth"])
    p.set_defaults(run=cmd_instruments)

    p = sub.add_parser("audition", help="render one instrument alone, with a picture")
    p.add_argument("inst")
    p.add_argument("-o", "--output", default="audition")
    p.add_argument("--notes", default="C3", help="comma separated note names played in sequence")
    p.add_argument("--beats", type=float, default=2.0)
    p.add_argument("--gate", type=float, default=0.8)
    p.add_argument("--velocity", type=float, default=0.8)
    p.add_argument("--bpm", type=float, default=120.0)
    p.add_argument("--patch", help="YAML overrides, e.g. '{filter: {cutoff: 900}}'")
    p.set_defaults(run=cmd_audition)

    p = sub.add_parser("lint", help="check harmony, ranges, structure and lyrics before rendering")
    p.add_argument("song")
    p.add_argument("--no-vocal", action="store_true", help="skip lyric checks (they need the vocal engine)")
    p.add_argument("--models", help="directory holding voice models")
    p.set_defaults(run=cmd_lint)

    p = sub.add_parser("render", help="render audio, MIDI, QA report and pictures")
    p.add_argument("song")
    p.add_argument("-o", "--output")
    p.add_argument("--formats", default=DEFAULT_FORMATS, help="comma list of wav, flac, ogg, mp3, mid")
    p.add_argument("--sections", help="render only these sections (fast preview)")
    p.add_argument("--only", help="render only these tracks")
    p.add_argument("--stems", action="store_true", help="also write one stem per track")
    p.add_argument("--no-qa", action="store_true")
    p.add_argument("--models", help="directory holding voice models")
    p.set_defaults(run=cmd_render)

    p = sub.add_parser("plot", help="extra pictures: piano roll of a section, zoomed spectrogram, effect chain response")
    p.add_argument("song")
    p.add_argument("-o", "--output")
    p.add_argument("--pianoroll", metavar="SECTION")
    p.add_argument("--bars", type=int, default=16)
    p.add_argument("--spectrogram", metavar="AUDIO_FILE")
    p.add_argument("--start", type=float, default=0.0)
    p.add_argument("--end", type=float)
    p.add_argument("--top", type=float, default=16000.0)
    p.add_argument("--chain", metavar="TRACK")
    p.set_defaults(run=cmd_plot)

    p = sub.add_parser("export", help="write project JSON, MIDI, LMMS project or DAWproject")
    p.add_argument("song")
    p.add_argument("--to", required=True, help="comma list of json, midi, lmms, dawproject")
    p.add_argument("-o", "--output")
    p.set_defaults(run=cmd_export)

    p = sub.add_parser("import-midi", help="turn a MIDI file into a song spec")
    p.add_argument("midi")
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--bpm", type=float)
    p.add_argument("--key", default="C major")
    p.set_defaults(run=cmd_import_midi)

    p = sub.add_parser("lmms-check", help="optional: re-render an exported LMMS project in LMMS and measure the result")
    p.add_argument("song", help="song file (its exported LMMS project is used) or a .mmp file")
    p.add_argument("-o", "--output")
    p.add_argument("--lmms", help="command that starts LMMS (setting lmms), e.g. a path to an AppImage")
    p.set_defaults(run=cmd_lmms_check)

    p = sub.add_parser("doctor", help="report this machine: packages, outside tools, settings, what is missing")
    p.set_defaults(run=lambda args: __import__("foundry.doctor", fromlist=["run"]).run())

    from foundry import vocal_cli
    vocal_cli.register(sub)
    return parser


def main() -> int:
    from foundry.singing import VocalError
    args = build_parser().parse_args()
    try:
        settings.override("config", args.config)
        for option, name in (("models", "models_dir"), ("asr_model", "asr_model"), ("lmms", "lmms")):
            settings.override(name, getattr(args, option, None))
        if hasattr(args, "asr_model"):
            args.asr_model = settings.get("asr_model")
        return args.run(args)
    except (spec.SpecError, VocalError, settings.SettingsError, KeyError, FileNotFoundError) as error:      # mistakes in the input, not program faults
        return _fail(error.args[0] if error.args else error)


if __name__ == "__main__":
    sys.exit(main())
