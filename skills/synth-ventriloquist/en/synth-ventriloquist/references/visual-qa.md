# Visual review: checking sound with pictures

An agent that can read images but cannot listen reviews a song the way an engineer reads meters and a spectrum analyser. The figures make audible properties visible, and each one answers specific questions. Look at every figure `produce` or `check` writes before telling the user a song is finished. Opening the images is part of the job. The numbers in `report.txt` say that something is off, and the figures show where and why.

## Contents

- The review pass
- Figure 1: overview
- Figure 2: band balance
- Figure 3: arrangement
- Figure 4: stem spectra
- Close-ups on demand
- Reading spectrograms
- When pictures and numbers disagree
- Showing figures to the user

## The review pass

After `produce`, in this order:

1. Read `report.txt` top to bottom. Note every `ERROR` and `WARN`, and read the tables under `master_summary`, `section_energy` and `part_levels`.
2. Open `fig_overview.png`. Does the energy curve match the plan? Is anything missing or constant where it should change?
3. Open `fig_balance.png`. Which bands sit outside their bars?
4. Open `fig_arrangement.png`. Does every part enter and leave where the script intended?
5. Open `fig_stems.png` when a band is off or two parts fight: who owns each region?
6. For each remaining suspicion, make a close-up (below) of the exact bars or the exact vocal line.
7. Decide: fix and run again, or accept and explain. Write down what was seen and what was changed.

State in the report to the user which figures were examined and what they showed. "The overview shows the kick stripe disappearing in both breakdowns as planned and the full spectrum returning at bar 177" is a review. "Looks good" is not.

## Figure 1: overview

`fig_overview.png`: on top the loudness curve over time (short-term LUFS) with section names, below it a spectrogram of the whole song (time left to right, pitch from low to high, darker means more energy).

What a healthy electronic track shows:

- The loudness curve steps with the sections: lower in intros and breakdowns, highest in drops, chorus and climax. A flat line from start to end means the limiter is flattening everything, or the arrangement has no contrast.
- A dark stripe at the bottom (about 40 to 100 Hz) wherever kick and bass play, and a gap in that stripe where the plan takes out both kick and bass.
- Fine vertical lines through the whole height: drum hits. They are absent where the plan takes out the drums.
- Rising diagonal smears before drops: risers and filter sweeps opening.
- Horizontal lines in the middle: held notes of pads, leads and vocals. They should change with the chords.
- Energy up to 10 kHz and beyond in full sections. A song that goes pale above 5 kHz everywhere is dull. A solid dark block from 2 to 8 kHz is harsh.

What to catch:

- A section that looks the same as its neighbours although the plan says it differs: a part is probably missing (wrong position, silent patch).
- The stripe of a part the plan takes out continuing through that stretch: the part was not removed. Stripes of drums and bass the plan keeps are normal.
- White columns (silence) in the middle of the song that the plan does not intend.
- The end cut off while lines are still dark: raise `tail_bars`.
- A loudness dip of several dB in a section meant to be the peak.

## Figure 2: band balance

`fig_balance.png`: six bands from sub to air. A bar marks the usual range for the genre, a dot marks the measured level, and the dot turns orange outside the bar.

- Dot right of the bar: too much energy in that band. Dot left: too little.
- Read the pattern across all six dots. Sub and bass high with mid low means the track is all kick and bass and the music is too quiet. Low-mid high means mud. High-mid and air both high means harsh and hissy.
- The fixes are in `mixing.md`. Prefer changing part levels and arrangement over EQ.

## Figure 3: arrangement

`fig_arrangement.png`: one row per part, a block for every bar in which it plays, section lines on top.

- Check it against the plan: entries, exits and breakdowns should be where the script put them. An empty row is a part that never plays.
- Look for the staircase in intros and outros (parts entering and leaving one by one), the hole where the plan takes parts out, and the full wall in the climax.
- Long unbroken rows for every part from start to end mean the arrangement never changes.

## Figure 4: stem spectra

`fig_stems.png`: the average spectrum of every part on one plot, kick and vocal highlighted, each curve labelled at its peak.

- Each part should have a region where it is the highest curve. Two curves at the same height over the same region mask each other. Choose the owner and lower, filter or move the other.
- The kick should be the top curve around 50 to 80 Hz. A sub or bass curve lying on top of it there explains a weak kick.
- The lead vocal should clear the other curves between about 1 and 5 kHz.
- A curve with strong content far outside its role (a pad with energy at 60 Hz, a bass reaching 8 kHz) needs a high-pass or low-pass.

## Close-ups on demand

Call these from Python when the standard figures raise a question. All are in `lmmskit.visual`.

| Question | Call |
|---|---|
| What happens in these bars? | `spectrogram(wav, out, start=seconds, end=seconds, marks=[(seconds, "label")])` |
| Did my change do what I wanted? | `compare_spectrograms([("before", a.wav), ("after", b.wav)], out, start, end)` |
| Is this vocal line voiced to the end? | `compare_spectrograms` on the dry vocal lines, `fmax=5000` |
| Is this vocal line really sung (harmonics in every vowel, pitch on the notes, syllables in place)? | `vocal_line(piece, rate, out, origin=seconds of the first sample, notes=lines.melody_in_seconds(melody, bpm, first_note_s), labels=[(seconds, "syllable")])`. `produce` draws it for weak and `ROUGH` lines as `out/vocals/<part>_lineNN.png` |
| Which notes are outside the key? | `piano_roll(project, out, start_bar, bars, tracks=[...], scale_pitch_classes=set(theory.scale_pitch_classes(key)))` |
| How do these sounds differ? | `lmms_tool.py sounds a b c --out folder` writes `sounds.png`, one small spectrogram per sound |
| What does this automation or ducking curve look like? | `curves({"name": (times, values)}, out, ylabel)` |

Seconds from bars: `song.seconds(bar)`, or bars × 4 × 60 ÷ BPM in 4/4.

Render only the part in question when the mix hides it: the stems from the last `produce` are in `out/stems/`, one WAV per part.

`vocal_line` has two panels. The top is a spectrogram to 6 kHz with an orange mark at every syllable. The bottom lays the sung pitch (dark line) over the written notes (pale bars).

- The marks should line up with where the sound starts, and horizontal stripes should run through every vowel to its end. A smudge in place of stripes is a whispered or noisy vowel.
- The pitch line should sit on the bars. A line running parallel to a bar nearly a semitone away is a pitch error.
- Short spikes at the note edges are consonants and the move between notes. Ignore them.
- A line that breaks in the middle of a vowel shows a voice that went unvoiced there.

## Reading spectrograms

- Horizontal stripes stacked at even spacing are a pitched, voiced sound: a sung vowel, a synth note. The lowest stripe is the pitch. Wavy stripes are vibrato.
- A grey cloud without stripes is noise: a whisper, a hi-hat, a riser, hiss. A sung line whose last note turns from stripes into cloud has lost its voice there.
- Sharp vertical lines are transients: drum hits, consonants like t and k.
- Stripes that bend upward or downward are pitch slides: a 303 slide, a vocal scoop, a pitch-dropping kick (a short downward hook at the bottom).
- A regular dimming of everything except the kick, once per beat, is sidechain pumping.
- Repeating fading copies to the right of a sound are delay echoes. A slowly fading haze is reverb.

## When pictures and numbers disagree

Trust neither blindly. A band can measure in range while the overview shows it comes entirely from one harsh section. A recognition score can be high while the spectrogram shows a whispered ending. Look closer with a close-up, and when it stays unclear, describe both observations to the user and let them listen.

## Showing figures to the user

Send the overview figure with the finished song. It lets a non-engineer see the shape of the track at a glance. Add a close-up only when it explains a decision or a question for the user (a before and after, a line that needs their ear).
