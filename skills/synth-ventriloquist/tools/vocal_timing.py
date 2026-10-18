# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
"""Beat and pitch alignment of rendered lead vocal stems, for any singing engine. A maintainer's tool: it is not
part of the skill package.

Usage:
    python vocal_timing.py measure <run_dir> [--no-asr] [--reuse-asr]   # reads run_dir/vocals.json (render_vocals.py),
                                                                         # writes run_dir/metrics.json
    python vocal_timing.py table <label=run_dir[,run_dir...]> ...        # markdown table; several runs are pooled

The shared pieces (syllables, melody parsing, recognition, periodicity) come from the toolkit of this checkout
(TOOLKIT). The voicing rule is kept here as its own copy, so a change to the toolkit's rule does not move the ruler.
Renders of other commits are measured with the same ruler by pointing render_vocals.py at their checkout.

Per syllable (one note group):
  onset_ms   when the voice really starts, minus the note start. "Really" is spectro-maestro's truly_voiced rule:
             pitch found, periodic below 4 kHz (>= 0.5) and within 24 dB of the take's loud frames. Measured only
             where the start is a landmark: after a voiceless onset consonant, or a vowel opening after a rest.
             A voiced onset (l, m, w, b ...) starts the voice before the beat by design and is left out.
  head_cents median |cents| from the written note over the truly voiced frames of [note start, + HEAD_S).
  periodicity of the middle half of the sung vowel span (autocorrelation at the note's period).
Per line: body_cents (part.pitch_error_cents rule), asr (asr.score_line), lag_ms (speech engines' report).
"""
import json
import os
import sys

import numpy as np
import soundfile as sf

TOOLKIT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "en", "synth-ventriloquist", "scripts")
sys.path.insert(0, TOOLKIT)

from lmmskit.vocal import asr, lines as line_tools, lyrics, phones, world   # noqa: E402

FRAME_S = world.FRAME_S
PERIODIC_BAND_HZ = 4000.0
VOICED_MIN_PERIODICITY = 0.5
VOICED_LEVEL_RANGE_DB = 24.0
LOUD_PERCENTILE = 90
ONSET_SEARCH_S = 0.12              # a voicing onset further than this from the beat belongs to another sound
MIN_VOICED_RUN_S = 0.03            # shorter voiced blips are not a vowel starting
MIN_UNVOICED_RUN_S = 0.01
REST_GAP_S = 0.09                  # sv's LEGATO_GAP_S: a gap this long before a vowel-initial syllable is a rest
HEAD_S = 0.09                      # the stretch part.pitch_error_cents leaves out at the start of a note
MIN_HEAD_FRAMES = 3
TRACKING_ERROR_CENTS = 600         # a head frame this far from its note is a pitch-tracker error (a subharmonic), not singing
BODY_HEAD_S, BODY_TAIL_S = 0.09, 0.04
PIECE_PAD_S = 0.15
MIN_PERIODICITY_SPAN_S = 0.03
ROUGH_PERIODICITY = 0.6
PHONEMIZER_LANG = "en-us"


# ---------------------------------------------------------------- analysis
def analyse(piece: np.ndarray, sr: int) -> dict:
    """WORLD analysis on the 5 ms grid with spectro-maestro's truly_voiced flags."""
    pw = world.pyworld()
    x = np.ascontiguousarray(piece, dtype=np.float64)
    f0, times = world.harvest_f0(x, sr)
    fft_size = pw.get_cheaptrick_fft_size(sr, world.F0_FLOOR)
    sp = pw.cheaptrick(x, f0, times, sr, f0_floor=world.F0_FLOOR, fft_size=fft_size)
    ap = pw.d4c(x, f0, times, sr, fft_size=fft_size)
    bins = max(1, int(ap.shape[1] * PERIODIC_BAND_HZ / (0.5 * sr)))
    periodic = 1.0 - ap[:, :bins].mean(axis=1)
    level = 10.0 * np.log10(sp.sum(axis=1) + 1e-12)
    loud = np.percentile(level, LOUD_PERCENTILE) if len(level) else 0.0
    voiced = (f0 > 0) & (periodic >= VOICED_MIN_PERIODICITY) & (level >= loud - VOICED_LEVEL_RANGE_DB)
    return {"f0": f0, "voiced": voiced}


def voicing_onsets(voiced: np.ndarray) -> np.ndarray:
    """Frame indices where a voiced run of at least MIN_VOICED_RUN_S starts after MIN_UNVOICED_RUN_S of no voice."""
    run, gap = int(round(MIN_VOICED_RUN_S / FRAME_S)), int(round(MIN_UNVOICED_RUN_S / FRAME_S))
    found = []
    for k in range(gap, len(voiced) - run + 1):
        if voiced[k] and not voiced[k - gap:k].any() and voiced[k:k + run].all():
            found.append(k)
    return np.array(found, dtype=int)


# ---------------------------------------------------------------- syllable classes
def onset_classes(text: str, wanted: int) -> list | None:
    """'voiceless', 'voiced' or 'none' for the onset of every sung syllable, from espeak phonemes of the text.

    The engines' own phone lists differ (IPA, voicebank symbols); the text's phonemes are the same for every engine,
    so every render of a line is judged on the same syllables. None when the syllables do not fold to the notes.
    """
    from kokoro_onnx.tokenizer import Tokenizer
    global _TOKENIZER
    if "_TOKENIZER" not in globals():
        _TOKENIZER = Tokenizer()
    symbols = list(_TOKENIZER.phonemize(text, PHONEMIZER_LANG))
    sounds = phones.merge_tokens(symbols, [0.0] * len(symbols), [0.0] * len(symbols))
    syllables = phones.fold_weak_syllables(phones.syllabify(sounds), wanted)
    if len(syllables) != wanted:
        return None
    classes = []
    for syllable in syllables:
        if not syllable.onset:
            classes.append("none")
        elif syllable.onset[-1].symbol[0] in phones.VOICELESS:
            classes.append("voiceless")
        else:
            classes.append("voiced")
    return classes


# ---------------------------------------------------------------- per line
def _cents(f0: np.ndarray, midi: float) -> np.ndarray:
    return 1200.0 * np.log2(f0 / (440.0 * 2.0 ** ((midi - 69.0) / 12.0)))


def measure_line(stem: np.ndarray, sr: int, row: dict, bpm: float, piece_end: float, use_asr: bool) -> dict:
    groups, _lead, _total = line_tools.note_groups(row["melody"], bpm)
    first = row["first_note_s"]
    a = max(0.0, row["audio_start_s"] - PIECE_PAD_S)
    b = min(len(stem) / sr, row["audio_end_s"] + PIECE_PAD_S)
    analysis = analyse(stem[int(a * sr):int(b * sr)], sr)
    f0, voiced = analysis["f0"], analysis["voiced"]
    times = a + np.arange(len(f0)) * FRAME_S
    onset_times = times[voicing_onsets(voiced)]
    classes = onset_classes(row["text"], len(groups)) or ["unknown"] * len(groups)
    spans = row.get("syllables") or []
    syllables, body_errors = [], []
    for index, group in enumerate(groups):
        start = first + group[0].start
        previous_end = first + groups[index - 1][-1].start + groups[index - 1][-1].duration if index else None
        after_rest = previous_end is None or start - previous_end >= REST_GAP_S
        landmark = classes[index] == "voiceless" or (classes[index] == "none" and after_rest)
        onset_ms = None
        if landmark and len(onset_times):
            nearest = onset_times[np.argmin(np.abs(onset_times - start))]
            if abs(nearest - start) <= ONSET_SEARCH_S:
                onset_ms = round(float(nearest - start) * 1000.0, 1)
        heads = []
        for note in group:
            note_start = first + note.start
            inside = (times >= note_start) & (times < note_start + HEAD_S) & voiced
            off = np.abs(_cents(np.where(inside, f0, 440.0), note.pitch))
            inside &= off <= TRACKING_ERROR_CENTS
            if inside.sum() >= MIN_HEAD_FRAMES:
                heads.append(round(float(np.median(off[inside])), 1))
            body = (times > note_start + BODY_HEAD_S) & (times < note_start + note.duration - BODY_TAIL_S) & (f0 > 0)
            body_errors += list(np.abs(_cents(f0[body], note.pitch)))
        periodic = None
        if index < len(spans):
            s, e = spans[index]["start_s"], spans[index]["end_s"]
            lo, hi = s + 0.25 * (e - s), e - 0.25 * (e - s)
            if hi - lo >= MIN_PERIODICITY_SPAN_S:
                middle = 0.5 * (lo + hi)
                note = next((n for n in group if first + n.start <= middle < first + n.start + n.duration), group[-1])
                periodic = round(lyrics.periodicity(stem, sr, 440.0 * 2 ** ((note.pitch - 69) / 12), lo, hi), 3)
        syllables.append({"index": index, "onset_class": classes[index], "after_rest": after_rest, "onset_ms": onset_ms,
                          "landmark": landmark, "head_cents": heads, "periodicity": periodic,
                          "text": spans[index]["text"] if index < len(spans) else ""})
    result = {"text": row["text"], "melody": row["melody"], "lag_ms": (row.get("report") or {}).get("lag_ms"),
              "body_cents": round(float(np.median(body_errors)), 1) if body_errors else None, "syllables": syllables}
    if use_asr:
        piece = stem[int(row["audio_start_s"] * sr):int(piece_end * sr)]
        scored = asr.score_line(piece, sr, row["text"], None, language="en")
        result["asr"] = scored["score"]
        result["heard"] = scored["heard"]
    return result


def _percentile(values: list, q: float) -> float | None:
    return round(float(np.percentile(values, q)), 1) if values else None


def summarize(measured: list) -> dict:
    syllables = [s for line in measured for s in line["syllables"]]
    landmarks = [s for s in syllables if s["landmark"]]
    onsets = [s["onset_ms"] for s in landmarks if s["onset_ms"] is not None]
    heads = [h for s in syllables for h in s["head_cents"]]
    periodic = [s["periodicity"] for s in syllables if s["periodicity"] is not None]
    bodies = [line["body_cents"] for line in measured if line["body_cents"] is not None]
    scores = [line["asr"] for line in measured if line.get("asr") is not None]
    lags = [line["lag_ms"] for line in measured if line.get("lag_ms") is not None]
    return {"lines": len(measured), "syllables": len(syllables), "landmarks": len(landmarks), "onsets": len(onsets),
            "onset_abs_median_ms": _percentile(np.abs(onsets).tolist(), 50), "onset_abs_p90_ms": _percentile(np.abs(onsets).tolist(), 90),
            "onset_signed_median_ms": _percentile(onsets, 50),
            "head_abs_median_cents": _percentile(heads, 50), "head_abs_p90_cents": _percentile(heads, 90), "head_notes": len(heads),
            "body_median_cents": _percentile(bodies, 50),
            "periodicity_mean": round(float(np.mean(periodic)), 3) if periodic else None,
            "periodicity_rough": int(sum(p < ROUGH_PERIODICITY for p in periodic)),
            "asr_mean": round(float(np.mean(scores)), 3) if scores else None, "asr_weak": int(sum(s < asr.WEAK_LINE_SCORE for s in scores)),
            "lag_median_ms": _percentile(lags, 50), "lag_spread_ms": round(float(np.percentile(lags, 90) - np.percentile(lags, 10)), 1) if lags else None}


def measure(run_dir: str, use_asr: bool, reuse_asr: bool = False) -> dict:
    with open(os.path.join(run_dir, "vocals.json"), encoding="utf-8") as handle:
        vocals = json.load(handle)
    earlier = {}
    if reuse_asr and os.path.exists(os.path.join(run_dir, "metrics.json")):       # recognition is the slow part
        with open(os.path.join(run_dir, "metrics.json"), encoding="utf-8") as handle:
            earlier = {(l["text"], l["melody"]): l for l in json.load(handle)["lines"] if l.get("asr") is not None}
        use_asr = use_asr and not earlier
    measured = []
    for part in vocals["parts"]:
        stem, sr = sf.read(part["stem"])
        rows = part["lines"]
        starts = sorted(row["audio_start_s"] for row in rows)
        seen = set()
        for row in rows:
            key = (row["text"].lower(), row["melody"])
            if key in seen:                                  # a repeat is the same cached take
                continue
            seen.add(key)
            following = next((s for s in starts if s > row["audio_start_s"]), row["audio_end_s"])
            line = measure_line(stem, sr, row, vocals["bpm"], min(row["audio_end_s"], following), use_asr)
            if key_of := earlier.get((row["text"], row["melody"])):
                line.update({"asr": key_of["asr"], "heard": key_of["heard"]})
            measured.append(line)
    result = {"voice": vocals["voice"], "checkout": vocals["checkout"], "summary": summarize(measured), "lines": measured}
    with open(os.path.join(run_dir, "metrics.json"), "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=1, ensure_ascii=False)
    return result


COLUMNS = [("onsets", "n"), ("onset_abs_median_ms", "|onset| med ms"), ("onset_abs_p90_ms", "|onset| p90 ms"),
           ("onset_signed_median_ms", "onset med ms"), ("head_abs_median_cents", "head med c"), ("head_abs_p90_cents", "head p90 c"),
           ("body_median_cents", "body c"), ("periodicity_mean", "periodicity"), ("periodicity_rough", "rough"),
           ("asr_mean", "asr"), ("asr_weak", "weak"), ("lag_median_ms", "lag ms"), ("lag_spread_ms", "lag p10-90 ms")]


def table(pairs: list) -> str:
    """One row per label=run_dir; a comma-separated list of run directories is pooled into one row."""
    out = ["| run | " + " | ".join(title for _, title in COLUMNS) + " |", "|---" * (len(COLUMNS) + 1) + "|"]
    for pair in pairs:
        label, run_dirs = pair.split("=", 1)
        lines = []
        for run_dir in run_dirs.split(","):
            with open(os.path.join(run_dir, "metrics.json"), encoding="utf-8") as handle:
                lines += json.load(handle)["lines"]
        summary = summarize(lines)
        out.append(f"| {label} | " + " | ".join("-" if summary.get(key) is None else str(summary[key]) for key, _ in COLUMNS) + " |")
    return "\n".join(out)


if __name__ == "__main__":
    command, *arguments = sys.argv[1:]
    if command == "measure":
        report = measure(arguments[0], "--no-asr" not in arguments, "--reuse-asr" in arguments)
        print(json.dumps(report["summary"]))
    elif command == "table":
        print(table(arguments))
    else:
        raise SystemExit(__doc__)
