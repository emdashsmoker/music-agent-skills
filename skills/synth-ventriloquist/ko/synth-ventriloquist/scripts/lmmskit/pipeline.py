# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
"""From a saved project to a checked, mastered, exported song: the steps after composing, in order.

lint -> balance part levels -> set master loudness -> render -> check mix, stems, sections, vocals
-> figures -> exports. Every step writes into one output folder and one report, so a review needs
only that folder.
"""
from __future__ import annotations

import json
import os
import shutil

from . import audio, compose, export, genres, lint as lint_tools, mix, render, sounds, visual
from .findings import finding, format_findings, worst
from .project import Project

AUDIO_FORMATS = ("ogg", "mp3")
CLEAN_LOUDNESS_GAP_LU = 3.0           # a clean master this far under the genre target is worth a warning


def _sections_in_seconds(plan: dict | None) -> list[tuple[float, str]]:
    if not plan or not plan.get("sections"):
        return []
    seconds_per_bar = plan["timesig"][0] * 4.0 / plan["timesig"][1] * 60.0 / plan["bpm"]
    return [(section["start_bar"] * seconds_per_bar, section["name"]) for section in plan["sections"]]


def check(project_path: str, out_dir: str, genre: str | None = None, target_lufs: float | None = None, figures: bool = True,
          wav_path: str | None = None, vocals: bool = True, stems: dict[str, str] | None = None, mix_style: str | None = None,
          asr_model: str | None = None) -> dict:
    """Render (unless wav_path and stems are given), run every check and draw the review figures. Returns the report.
    mix_style overrides the plan file's style for the checks (a compose.MIX_STYLES name); asr_model picks the
    recognition model of the vocal check (default: the setting asr_model, else base.en)."""
    os.makedirs(out_dir, exist_ok=True)
    project = Project.load(project_path)
    plan = compose.load_plan(project_path)
    genre = genre or (plan or {}).get("genre")
    style = mix.style_of(plan, mix_style)
    roles = mix.roles_of(project_path, project)
    role_names = {name: info["role"] for name, info in roles.items()}
    wav = wav_path or os.path.join(out_dir, "mix.wav")
    if wav_path is None:
        render.render(project_path, wav)
        mix.trim_true_peak(wav)
    x, rate = audio.load(wav)
    stems = stems or mix.render_stems(project_path, os.path.join(out_dir, "stems"))
    findings = lint_tools.lint(project, plan)
    findings += mix.check_master(x, rate, genre, target_lufs)
    vocal_file = os.path.splitext(project_path)[0] + compose.VOCALS_SUFFIX
    rendered = None
    if vocals and os.path.exists(vocal_file):
        with open(vocal_file, encoding="utf-8") as handle:
            rendered = json.load(handle)
    sung = [(row["audio_start_s"], row["audio_end_s"]) for item in rendered or [] if item["role"] == "vocal" for row in item["lines"]]
    findings += mix.check_stems(stems, roles, genre, plan, sung or None, style)
    findings += mix.check_sections(x, rate, plan)
    if rendered is not None:
        from .vocal import part as vocal_part
        folder = os.path.dirname(os.path.abspath(project_path))
        for item in rendered:
            item["stem"] = os.path.join(folder, item["stem"])          # stored relative to the project
            findings += vocal_part.check_part(item, project.bpm, asr_model, figure_dir=os.path.join(out_dir, "vocals") if figures else None,
                                              beats_per_bar=project.beats_per_bar)
        vocal_part.save_report(os.path.join(out_dir, "vocals.json"), rendered)
    figure_paths = {}
    if figures:
        sections = _sections_in_seconds(plan)
        beat_sections = [(s["start_bar"] * project.beats_per_bar, s["name"]) for s in (plan or {}).get("sections", [])]
        master = next(f for f in findings if f["code"] == "master_summary")["data"]
        profile = genres.get(genre)
        targets = {band: (low + profile["bands"].get(band, 0.0), high + profile["bands"].get(band, 0.0)) for band, (low, high) in mix.BAND_TARGETS.items()}
        figure_paths = {
            "overview": visual.song_overview(wav, os.path.join(out_dir, "fig_overview.png"), sections, os.path.basename(project_path)),
            "balance": visual.band_balance(master["bands_db"], targets, os.path.join(out_dir, "fig_balance.png"), "band balance against the usual range"),
            "arrangement": visual.arrangement(project, os.path.join(out_dir, "fig_arrangement.png"), beat_sections),
            "stems": visual.stem_spectra({n: p for n, p in stems.items() if "trigger" not in n.lower()}, os.path.join(out_dir, "fig_stems.png"),
                                         highlight=[n for n, r in role_names.items() if r in ("vocal", "kick")], title="average spectrum of every part"),
        }
    report = {"project": project_path, "genre": genre, "mix_style": style["name"], "worst": worst(findings), "findings": findings,
              "figures": figure_paths, "wav": wav, "stems": stems}
    with open(os.path.join(out_dir, "report.json"), "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=1, ensure_ascii=False, default=float)
    with open(os.path.join(out_dir, "report.txt"), "w", encoding="utf-8") as handle:
        handle.write(format_findings(findings) + "\n")
    return report


def produce(project_path: str, out_dir: str, genre: str | None = None, target_lufs: float | None = None,
            formats: tuple[str, ...] = AUDIO_FORMATS, balance: bool = True, exports: bool = True, title: str | None = None,
            repeat_check: bool = True, tone_fit: bool = True, mix_style: str | None = None, asr_model: str | None = None) -> dict:
    """Full finishing pass: balance, loudness, checks, figures, audio files, MIDI, DAWproject and JSON.

    mix_style overrides the plan file's style (a compose.MIX_STYLES name) for the balance and the checks. The ducking
    under sung lines is written when the song script saves the project, so a vocal song changes style in the script.
    """
    os.makedirs(out_dir, exist_ok=True)
    plan = compose.load_plan(project_path)
    genre = genre or (plan or {}).get("genre")
    target = target_lufs if target_lufs is not None else genres.get(genre)["lufs"]
    style = mix.style_of(plan, mix_style)
    log = {}
    if balance:
        log["balance"] = mix.balance(project_path, out_dir, genre, tone_fit=tone_fit, style=style)
        stems = log["balance"].pop("stems")
    else:
        stems = mix.render_stems(project_path, os.path.join(out_dir, "stems"))
    log["loudness"] = mix.master_to_loudness(project_path, out_dir, target)
    loudness = log["loudness"]
    # A master held back to keep the limiter clean is judged against the loudness it reached, and the report says so.
    report = check(project_path, out_dir, genre, loudness["reached_lufs"] if loudness["capped"] else target, wav_path=loudness["wav"], stems=stems,
                   mix_style=style["name"], asr_model=asr_model)
    severity = "warn" if loudness["capped"] and loudness["reached_lufs"] < target - CLEAN_LOUDNESS_GAP_LU else "info"
    report["findings"].append(finding(severity, "limiter", f"master limiter cuts {loudness['limiter_reduction_db']} dB from the loudest moments "
                                      f"(limit {mix.MAX_LIMITER_REDUCTION_DB:g}); loudness {loudness['reached_lufs']} LUFS, genre target {target:g}"
                                      + (". " + loudness["note"] if loudness["note"] else "")))
    tone = log.get("balance", {}).get("tone")
    if tone and tone["shelf_db"]:
        left = "" if tone["shelf_db"] < mix.MAX_TONE_SHELF_DB else ". That is the most the fit adds: the rest belongs to the sounds (filters, hats, a bright layer)"
        report["findings"].append(finding("info", "tone_fit", f"tone fit: the densest passage was dull (highs {tone['before_db']:+.1f} dB against the mids), so {tone['parts']} melodic, effect and vocal parts "
                                          f"got a {tone['shelf_db']:+.1f} dB high shelf at {mix.TONE_SHELF_HZ:g} Hz at unchanged loudness. Drums, bass and sub are untouched" + left))
    if repeat_check:
        report["findings"].append(mix.repeat_check(project_path, report["wav"], out_dir))
    report["worst"] = worst(report["findings"])
    with open(os.path.join(out_dir, "report.txt"), "w", encoding="utf-8") as handle:
        handle.write(format_findings(report["findings"]) + "\n")
    report["steps"] = log
    name = os.path.splitext(os.path.basename(project_path))[0]
    title = title or (plan or {}).get("title") or name
    files = {"wav": report["wav"]}
    skipped = [extension for extension in formats if not render.can_write(f".{extension}")]
    if skipped:
        report["findings"].append(finding("info", "audio_formats", f"{', '.join(skipped)} not written: mp3 needs libsndfile 1.1 or later "
                                          "(a newer soundfile) or ffmpeg. See references/setup.md"))
        formats = tuple(extension for extension in formats if extension not in skipped)
    for extension in formats:
        files[extension] = render.convert(report["wav"], os.path.join(out_dir, f"{name}.{extension}"), metadata={"title": title})
    if exports:
        project = Project.load(project_path)
        roles = {n: info["role"] for n, info in mix.roles_of(project_path, project).items()}
        files["midi"] = export.to_midi(project, os.path.join(out_dir, f"{name}.mid"), roles)
        files["json"] = export.to_json(project, os.path.join(out_dir, f"{name}.project.json"))
        files["dawproject"] = export.to_dawproject(project, os.path.join(out_dir, f"{name}.dawproject"), title=title, roles=roles,
                                                   stems={n: p for n, p in report["stems"].items() if "trigger" not in n.lower()})
        files["project"] = shutil.copyfile(project_path, os.path.join(out_dir, os.path.basename(project_path)))
    report["files"] = files
    with open(os.path.join(out_dir, "report.json"), "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=1, ensure_ascii=False, default=float)
    return report


def pack(project_path: str, zip_path: str) -> str:
    """Zip a project with everything it needs to open elsewhere: the .mmp, its plan files and its samples folder."""
    import zipfile
    folder = os.path.dirname(os.path.abspath(project_path))
    base = os.path.splitext(os.path.basename(project_path))[0]
    project = Project.load(project_path)
    sources = {element.get("src", "") for element in project.root.iter() if element.get("src")}
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(os.listdir(folder)):
            if name.startswith(base + ".") and os.path.isfile(os.path.join(folder, name)):
                archive.write(os.path.join(folder, name), name)
        for source in sorted(sources):
            path = os.path.join(folder, render.SAMPLES_SUBDIR, source)
            if not os.path.isabs(source) and os.path.exists(path):
                archive.write(path, os.path.join(render.SAMPLES_SUBDIR, source))
        samples = os.path.join(folder, render.SAMPLES_SUBDIR)
        for root, _, files in os.walk(os.path.join(samples, sounds.KIT_FOLDER)):     # the kit's notice, GPL text and preset sources
            for name in sorted(files):
                if not name.endswith(".wav"):                                       # sounds the song uses were added above
                    path = os.path.join(root, name)
                    archive.write(path, os.path.join(render.SAMPLES_SUBDIR, os.path.relpath(path, samples)))
        archive.writestr("HOW_TO_OPEN.txt", "Open the .mmp in LMMS 1.2 or newer.\n"
                         "Copy the folders inside 'samples' into your LMMS samples folder first (LMMS: Edit > Settings > Paths > "
                         "'LMMS working directory', subfolder 'samples'), otherwise the drum kit and vocal tracks stay silent.\n")
    return zip_path
