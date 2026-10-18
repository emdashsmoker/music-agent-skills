# Vocals: voices, lyrics, and making sung words understandable

Read this before adding any vocal. It covers the choice of voice, the melody notation, lyric writing for sung lines, the word-choice procedure, the line-ending repair, the mix, and what to hand the user for listening.

## Contents

- Attitude
- The three kinds of voice
- Offering voices during planning
- Singer voicebanks the user supplies (DiffSinger)
- Writing a vocal part
- Melody notation
- Lyric craft
- Word-choice procedure
- Line-ending repair
- Performance style
- Vocals in the mix
- What to hand the user
- Other languages
- Known limits
- Measurements behind this page

## Attitude

- The recognition score is a detector. It points at lines worth listening to. The user's ears decide whether a line is clear.
- Lyrics the user has approved stay as they are. A warning alone is never a reason to change them. Report the warning, offer alternatives, and let the user choose.
- Every number on this page was measured on particular voices. A new voice, language or engine behaves differently, so measure again with the tools here before relying on a rule. `compare` settles questions that rules cannot.
- When a rule and a measurement disagree, the measurement wins. When the measurement and the user's ear disagree, the ear wins.

## The three kinds of voice

| Voice id | What it is | Strengths | Limits |
|---|---|---|---|
| `diffsinger:<folder>[#colour]` | A singing-voice model the user supplies as a voicebank folder | Real singing: natural vowels, vibrato, breath, many languages depending on the bank | The user must provide the bank and accept its terms. About 10 s of computing per 5 s line on two CPU cores |
| `kokoro:<voice>` | A speech voice (Kokoro, English) made to sing by stretching vowels onto the notes | Always available, clear consonants, eight built-in voices | Speech timbre. Sounds like a vocoder-style or "sung-spoken" lead. Best within about an octave above the voice's speaking pitch |
| `piper:<voice>` | A speech voice (Piper, many languages) sung the same way | Covers languages Kokoro lacks | Quality varies by voice. Some are lo-fi |

A good singer voicebank is the first choice when the user has one, most of all for exposed lead vocals. The speech voices are the fallback that always works, and they suit electronic styles where a processed voice is at home (futurepop, EBM, synthpop, electro, vocoder hooks).

`python scripts/lmms_tool.py voices` lists the built-in speech voices with gender, accent and notes. `voices <voice id>` describes one voice, and for a voicebank it lists languages, voice colours and the documents that state its terms. For a bank with several voice colours, add `#colour` to the id to pick one. Without it the first colour sings.

Speech voices have two methods. `stretched` (default) analyses the spoken line and re-synthesizes it on the melody: any pitch, clearest words in testing. `held` (`method="held"`, Kokoro only) lets the speech model itself hold the vowels: a more natural tone inside the voice's clean range, weaker outside it. Render the same line both ways and let the user pick when the vocal tone matters to them.

## Offering voices during planning

Offer the choice, with a default, when the song has vocals:

1. A singer voicebank, if the user has or wants to supply one.
2. A built-in speech voice. Defaults: `kokoro:af_heart` (female), `kokoro:am_michael` (male). Others: `af_bella`, `af_nicole` (breathy), `bf_emma` (British), `am_fenrir` (deep), `am_onyx` (dark), `bm_george` (British), and the Piper voices in the `voices` list.
3. No vocal, or a vocal melody played by a synth lead.

The voice is a choice of timbre, and it belongs to the user. Use the default voice or the one the user named, and keep it. When a line is unclear, change the wording or the notes first (see the word-choice procedure). Recognition scores do differ between voices on the same line, but a higher score is no reason to swap the singer on your own: offer the comparison (`compare` with `--voice` changed, audio included) and let the user decide.

Some built-in voices carry licence notes (shown by `voices`). Pass them on when the user plans to publish.

## Singer voicebanks the user supplies (DiffSinger)

The toolkit renders DiffSinger voicebanks in the OpenUtau folder layout (a folder containing `dsconfig.yaml`). It contains no voicebank, names none, and downloads none on its own initiative. Handle only what the user hands over:

- A folder path: use it directly. `voices diffsinger:<folder>` confirms that it loads.
- An archive file: unpack it into a new empty folder outside the song project, then use that folder.
- A link to a repository or download page the user gives: fetch exactly that into a new empty folder. Do not search for voicebanks or suggest sources.

Before the first render with a bank:

1. Run `voices diffsinger:<folder>` and open every file it lists under `terms_documents`, plus any terms page those files point to.
2. Tell the user in a few plain sentences what the terms say about the points that matter: commercial use, credit, content restrictions, redistribution of the bank or of audio, and use for machine learning. Quote the source when the wording is unusual.
3. Ask the user to confirm that the planned use fits. If no terms can be found, say so and ask the user how to proceed.
4. Put the required credit into the delivery notes and into the lyrics file or metadata when the terms ask for it.

Never copy a voicebank into the song project, into exports, or into a `pack` archive. Only rendered audio leaves the machine.

Usage:

```python
vocal = song.vocal("lead vocal", "diffsinger:/path/to/bank#Soft", lang="en", steps=20)
```

- `#name` picks a voice colour when the bank has several. Without it the first one is used.
- `lang` must be one of the bank's languages. Words missing from the bank's English dictionary are pronounced through a built-in fallback. Languages written without spaces are looked up character by character.
- Options: `steps` (quality against time, default 20), `gender` (−1 to 1, formant shift), `velocity` (consonant speed), `tension`, `breathiness`, `expressiveness` (how much the bank's own pitch model moves), `own_pitch=False` to draw the pitch curve from the Style settings instead of the bank's pitch model.
- Renders are repeatable: the same line gives the same audio.
- To find the range a bank is comfortable in, sing one line at several transpositions and compare scores, or measure the pitch of the demo recording that often ships with a bank.

## Writing a vocal part

```python
vocal = song.vocal("lead vocal", "kokoro:af_heart")
vocal.line(("verse1", 0), "Empty roads below a paper sky", "E4/0.5 E4/0.5 G4/0.5 G4/0.5 A4/2 A4/0.5 G4/0.5 F4/0.5 E4/2 R/0.5")
vocal.line(("chorus1", 0), "See the signal fires", "A4/1 A4/1 F4/1 A4/1 B4/3", kind="chorus")
vocal.harmony("harmony vocal", steps=2, only_kind="chorus", pan=20)      # a third above, kept off chord clashes
vocal.double("double vocal", only_kind="chorus", pan=-20)                # second take for width
song.duck_for_vocals(4.0, presence_db=6.0)                               # optional: changes the ducking under sung lines (defaults 2.5 and 6.0)
```

- `line(at, text, melody, kind=None, beats=0.0)`: `at` is where the first melody token starts. `beats=-1` starts a pickup one beat before the bar.
- Lines are sung when the song is saved, cached in `.vocal_cache/` beside the project, and placed so that each vowel starts on its beat. Changing one line re-sings only that line.
- Each part becomes one audio file under `samples/<project>/` and one track with a vocal channel strip (EQ, compression, reverb send).
- `song.vocal(..., level_db=, pan=, sends=, effects=, method=, lang=, speed=, style=, fix_ending=)`.

## Melody notation

One token per sung syllable, separated by spaces:

- `E4/1` sings the syllable on E4 for one beat.
- Joining notes with `~` sings one syllable on several notes. For example, `E4/0.5~G4/0.5` bends one syllable from E4 to G4.
- `R/0.5` is a rest of half a beat.

The words are matched to the tokens by syllable, in order. If the counts differ, the tool stops with a table of syllables per word. Fix the melody or the words. Words whose syllable count is unstable in speech (fire, hour, every, different) are best given one long note or replaced.

`python scripts/lmms_tool.py sing --voice <id> --text "..." --melody "..." --bpm 132 -o work/line.wav` sings one line alone and prints its report with a recognition score.

## Lyric craft

Before writing, find out what the chosen voice sings well. The kind of voice (speech voice or singer voicebank) and the language decide which rules in the table below apply. Choose the words and the sentence structure to fit those rules from the start. Changing words after the lyrics are finished means fitting meaning and rhyme again.

- Fit the sentence structure to the voice too. Pick a word order that keeps weak function words (to, the, a) off beats and long notes. Recast a sentence that opens with function words or stacks them in a row so that a content word leads. A speech voice reads to with a weak vowel, so it sinks on a beat or a long note (see the reduced-vowel rule below).
- Avoid, or test early, words a pronunciation dictionary is unlikely to hold (proper nouns, invented words, abbreviations, foreign words). A speech voice guesses their pronunciation from the spelling, so it may read them differently than intended. A singer voicebank sings an English word missing from its dictionary with a guessed pronunciation, and in other languages it stops at such a word.
- Write numbers and symbols out as the words to be sung.
- For a word the song needs, such as the title or a name, sing a line containing it with `sing` or `compare` before writing the other lines. If it is misread, respell it by sound in the text given to the voice, and keep the original spelling in the lyric file for the user.

Review lyrics the user wrote by the same measures once the voice is chosen, before they are sung. For each line the chosen voice is unlikely to sing well, give the reason and a revised line. Where it helps, sing the original and the revision with `compare` and show the scores and the audio. Apply only the revisions the user approves. If the user insists on the original, say once and concretely what to expect on that line, then go on with the original and record it in the delivery notes (the principles in `SKILL.md`).

Sung words are harder to follow than spoken ones, and a model voice has less to spare than a human singer. These habits raise the odds. They are starting points from measurements on English speech voices, so check them with `compare` instead of trusting them blindly.

Not every rule is about speech voices:

| Rules | For | What they cover |
|---|---|---|
| Singing craft | Any voice, a human singer included | Stress on the strong beats, 110 ms or more per syllable, open vowels or nasals on held notes, reduced vowels and weak function words off the beats |
| Model-voice habits | Speech voices and singer voicebanks alike | Consonants blur under about 200 ms, consonant clusters need room, bright consonants spit and peak |
| Speech-voice repairs | Speech voices only | The thin held ee and `vowel_body`, `sibilance`, the line-ending repair, the timing guards, the strong-form spelling |

When the user has chosen a voicebank, write the lyrics by the singing craft and the model-voice habits, and read the speech-voice repairs as background. `lyric-lint` checks the first two groups for a voicebank voice as well.

- One sentence, one line. A sentence split into separate one-bar fragments ("Day after day" / "the same old sky") scored 0.15 to 0.23 per fragment. The same words sung as one two-bar line scored 1.0. The voice needs the whole phrase to speak it naturally.
- Start lines on a content word (`weak_opening`). Content words on the long and strong notes, small words (the, of, to, and) on short weak ones.
- End lines on an open vowel or a diphthong: day, go, you, sky, low, away. A line that ends on a held stop consonant (night, stop, made) has nothing to sustain.
- Carry a line on voiced consonants (m, n, l, d, b, g, w, r) and open vowels. Use the bright consonants t, k, p, s, z and sh as seasoning: about one per word, and none right before a held note. On the speech voices they spit and hiss. Their bursts are the loudest peaks of a line, up to 13 dB above the vowel body, and carry a metallic edge. A line built on them pokes out of the mix and reaches the limiter first. `bright_consonants` warns at three bright sounds in five syllables (a cluster such as st or sk counts twice) or at three bright syllables in a row.
- Keep ee words (he, she, we, see, me, be, free) on short notes when a speech voice sings. The voice has little body in that vowel, and the stretch keeps it thin. The word drops well under its neighbours (9 dB in the measurements below), while its energy above 1.3 kHz stays as strong as the body, so it sounds quiet and sharp at once. Put open vowels (ah, oh, oo, ay) on the held notes, or let the engine fill the vowel with `Style(vowel_body=1)` (see Performance style). `held_ee` points at an ee held for 2 beats or more. A singer voicebank shapes the vowel itself, so this rule and `held_ee` do not apply to it.
- Keep reduced vowels off the beats and off long notes. Function words such as the, to and a, the first syllable of upon and about, and the short ɪ of it, its and sit have almost no vowel for the engine to hold. In a probe line, a schwa held for half a second came out 18-22 dB under the line, "the" sang as breath (periodicity 0.4), and "it" on a beat became the burst of its t. Put these words on short off-beat notes and give the beats to content words (`reduced_vowel_on_beat`, `short_vowel_on_beat`, `weak_word_on_long_note`).
- When such a word must sit on a held note, hand the voice its strong form: too for to, thee for the, ay for a. A singer holds the strong form anyway, and the voice then sings a full vowel in place of the schwa. Check that the respelling does not change the meaning (too is also a word), and keep the ordinary spelling in the lyrics file for the user.
- Give every syllable at least about 110 ms. At 132 BPM a 16th note is 114 ms, which is the practical floor. Consonant clusters (str, ndz, lds) need a half beat or more.
- At 150 BPM and above, avoid runs of eighth-note syllables and start from one syllable per beat. Once a syllable gets shorter than about 200 ms (an eighth at 150 BPM is 200 ms), consonants start to blur even in a singer voicebank.
- Put the stressed syllable of a multi-syllable word on the stronger beat. Beat strength runs: the downbeat, beat three, beats two and four, the off-beats, then 16th places. `stress_on_weak_beat` warns when the stressed syllable sits on a weaker beat than an unstressed syllable of the same word and its note is no longer. The stress comes from the voice's pronunciation dictionary.
- Avoid three weak words in a row, and two short weak words running into a long note (`weak_words_in_a_row`, `weak_pickup`).
- Chorus lines: 5 to 7 syllables, a held last note, and the title in the first or last line.
- Keep the melody within about an octave above the speech voice's natural pitch (the line report shows `natural_pitch`). A singer voicebank has its own comfortable range.
- Leave air between lines: one or two beats of rest so the reverb tail and the listener can catch up.
- Rhyme by vowel sound. Spelling is no guide (move and love do not rhyme).

`python scripts/lmms_tool.py lyric-lint --voice <id> --text "..." --melody "..." --bpm 132` checks a line against these habits before anything is sung. Run it on each line as you write it. Once the project exists, `lint song.mmp` repeats the same checks on every lead line (`lyrics_*` findings). For a line that does not start on the downbeat, pass its starting beat within the bar (`--start-beat 0.5`) so the stress check sees the right beat strengths.

## Word-choice procedure

Use this when a line is flagged, and for every chorus before building the arrangement around it.

1. Render the vocal alone first. Judge words on the dry vocal, before the mix can mask them.
2. For each doubtful line write 3 to 5 candidates with the same syllable count and meaning (`let it glow` / `let me go` / `feel the glow`).
3. Compare them on the same notes:

   ```bash
   python scripts/lmms_tool.py compare --voice kokoro:af_heart --bpm 132 --melody "A4/1 A4/1 F4/1 A4/1 B4/3" \
       "We are signal fires" "See the signal fires" "Signal fires are high" --out work/candidates
   ```

   The result lists, per candidate, what the recogniser heard, the score (0 to 1, the second-best of several passes) and how steadily the last note is voiced. `--out` keeps a WAV of each.
4. Prefer the candidate that keeps the meaning and scores clearly higher. A difference under about 0.1 is noise.
5. Show the user the table and the audio of the top candidates when the wording matters to them. Their approved lyric wins even if another candidate scores higher.
6. If no wording helps, change the notes: longer notes on the words that are lost, a lower key, or a slower rhythm for that line. If that fails too, tell the user and offer another voice as an option.

After the song is built, `produce` scores each different lead line once and lists the weak ones (`weak_line`, score under 0.85) with possible causes. Lines that come through clearly produce no lyric warnings, whatever the craft rules say. Backing parts (harmonies, doubles) get no recognition score or pitch error. They do get the `ROUGH` and `ending_dies` checks, because a nearly silent harmony syllable leaves a hole under the lead that no lead check can see. When either warning names a backing part, rest the backing on that word or lower the part.

The same check measures two more things per line. They appear in the `vocal_scores` table next to each line's score, and every line in `out/vocals.json` carries them as `pitch_error_cents` and `rough`.

- Pitch error (`pitch_error_cents`): the median distance in cents between the sung pitch and the written notes, measured in the vowels away from the note edges. 10 to 15 cents is normal. Above 25 the line is heard as out of tune. When at least two lines, and half or more of the different lines, are above 25 cents, `off_pitch_lines` appears. The melody then lies outside the range this voice holds cleanly: transpose the part toward its natural pitch or choose another voice.
- Rough syllables (`rough_syllables`, `ROUGH` in the report): vowels that came out as noise (`noise`, periodicity under 0.6) or were swallowed (`quiet`, 8 dB under the line's typical vowel). The score finds lines whose words come out wrong. `ROUGH` finds syllables that grate even when the words are understood, so a line scoring 1.00 can still be rough. Check both. A syllable that is mostly consonant by design on a short note is not judged.
- Weak and `ROUGH` lines get a figure in `out/vocals/<part>_lineNN.png`. A smudge where the vowel should show stripes is a real fault: lengthen the note, choose a word with fewer consonants around the syllable, or try another voice and check again. `references/visual-qa.md` explains the figure.

## Line-ending repair

A speech voice lets the last word of a sentence die away: quieter, breathy, often whispered. In a song the last word usually holds the longest note, and a whisper held for a bar is hiss. The toolkit repairs this automatically for speech voices:

- It speaks the line a second time with a short carrier word after it (English: "but"), which keeps the real last word in full voice, and splices only that last syllable into the plain take. The carrier word itself is never heard.
- It acts only when the ending is judged to be dying: less than 85% of the last vowel is voiced, or the vowel is 9 dB or more below the line's typical level. Other lines are left untouched.
- It checks that the carrier take has the same syllables before splicing, and falls back to the plain take when anything is off. Results are cached.
- Switch it off for a part with `song.vocal(..., fix_ending=False)` or for one test line with `sing --no-ending-fix`, for example when the fading ending is the effect the user wants.
- The carrier word is defined per language in `CARRIER_WORDS` (`scripts/lmmskit/vocal/ending.py`). A language without an entry is not repaired. To add one, pick a short unstressed word that naturally continues a sentence and starts with a consonant, then confirm with the before-and-after test below.
- Singer voicebanks do not need the repair and are not touched by it.
- When the ending still dies after the repair (or the repair could not be applied), `produce` raises an `ending_dies` warning and draws that line's figure. It uses the same criteria as the repair. Change the last word to one ending on an open vowel or diphthong, give it a shorter note, or try another voice. `ROUGH` averages over the whole vowel and can miss this fault, so read both warnings together.

What not to do about dying endings: do not boost the ending with a compressor or volume automation (it raises the hiss), do not add a comma or an exclamation mark to the lyric to force emphasis (it changes the rhythm and timing of the whole line), and do not cut the last note short to hide the problem.

To check the repair on a new voice or language, sing the same line with and without it and compare: the line report gives `voiced_share` before and after, and `visual.compare_spectrograms` shows the last note as clean horizontal stripes (voiced) or as a grey cloud (whisper).

## Performance style

`from lmmskit.vocal.singing import Style`, then `song.vocal(..., style=Style(vibrato=1.0, scoop=0.6, drift=1.0, evenness=0.7, seed=0))`.

- `vibrato`: 0 is a straight tone, 1 the default, 2 wide. It starts late on long notes, as singers do.
- `scoop`: how far phrase starts slide up into the note.
- `drift`: slow random pitch wander that keeps held notes alive.
- `evenness`: 0 keeps speech dynamics, 1 makes every syllable equally loud.
- `sibilance`: default 0 (off). It finds every s, z and sh, and every t, k and p burst, that rises more than 3 dB above the line's vowel body (300-1300 Hz). On that phone's own span it cuts above 5 kHz by the excess, at most by the set value in dB (4 or so). Unlike a mixer de-esser, it knows where the consonants are and touches nothing else. In five songs, 13% of bright consonants rose more than 3 dB (up to +13 dB), and most of the loudest were t and k bursts. On the worst lines a setting of 4 took 2-3 dB off the peaks and changed one line's recognition score. Use it for a voice that sounds spitty, and leave it off otherwise.
- `vowel_body`: default 0 (off). At 1 it fills each held ee vowel (he, she, we, see; 0.2 s or longer) with the 300-1300 Hz body of the line's other vowels, aiming 3 dB under them and lifting at most 10 dB. On the same frames it thins the breath noise above 2 kHz. A singer does the same by opening ee toward ih on a long note. On 24 lines from seven songs it raised the median ee body from 8.8 dB to 6.4 dB under the line, took 3 dB off the metallic 1.3-5 kHz excess and 4 dB off the hiss above 5 kHz, and left 22 recognition scores unchanged. It shifts the vowel's colour a little, so listen to the ee words before keeping it.
- `seed`: a different seed gives a different take. `double()` uses this.

Deadpan styles (doomer, coldwave, EBM) want `vibrato=0.3, scoop=0.3`. Anthemic choruses can take the defaults or more vibrato. For a singer voicebank these settings shape the pitch only with `own_pitch=False`. Otherwise the bank's own pitch model performs the line.

## Vocals in the mix

- Targets, measured on the stems only while a lead line is sung (the line times of the vocals file): the lead should sit at or above the backing between 300 and 3400 Hz (`vocal_body`), and at least 2 dB above it between 1.3 and 5 kHz (`vocal_consonants`), where consonants live. More than 9 dB above reads as a vocal pasted on top.
- Both findings report a whole-song value and a value per section. The floor and the ceiling are judged on the section whose backing is densest (usually a chorus), because a sparse verse lifts the whole-song value and hides a chorus that falls short.
- Voices differ by many dB in the 1.3-5 kHz band (in the test songs a singer voicebank started 4.7 dB under the backing and a speech voice 7.6 dB over it with the same channel settings). The balance step therefore measures the margin and adds a presence lift of up to 6 dB to the lead vocal when it falls short. The report shows the lift under `vocal_presence`.
- What the lift cannot close comes from the backing. Every song with a vocal part gets ducking automation on the music bus while a lead line is sung. By default the whole bus drops 2.5 dB, and the consonant band dips 6 dB at its centre. The dip is 1.5 octaves wide: it lowers the 1.3-5 kHz band by about 2.7 dB and leaves the music above 5 kHz nearly untouched.
- A genre profile's `vocal_duck` pair replaces these defaults, and `song.duck_for_vocals(depth_db, presence_db)` in the song script overrides both. `song.duck_for_vocals(0)` turns the ducking off. `presence_octaves` changes the dip width when the production the user wants calls for it (default 1.5). Wide values are not recommended and stay off by default.
- The dip acts on the music bus only. When hats, claps and snares are what covers the consonants, the `vocal_consonants` warning says so and names the remedy: fewer bright drum hits under the lines, or a little more vocal level. Also rest the lead synth while the voice sings.
- When the vocal sounds small, deepen the ducking first, then thin out the parts under the vocal, and leave raising the vocal `level_db` for last. In the test songs, +1.5 LU of vocal sounded the same as the default ducking (2.5/6.0) but spent 1.2 dB of limiter headroom and kept the chorus ceiling warning on for good. At +3 LU the vocal sat on top of the track.
- Do not sidechain the vocal or its reverb to the kick. Pumping chops consonant tails and makes words harder to follow. The vocal bus is outside the sidechain by default.
- When listening to the mix, check the t, s and z of each line first for peaks and a metallic edge. Then check whether ee words drop under their neighbours or ring. Tame stinging consonants with `sibilance` in the Style, which acts only on those phones. Do not reach for a mixer de-esser, which cuts all treble. Fix a buried ee word in the lyric or with a shorter note, because a level boost raises its hiss too.
- Harmonies and doubles go to the sides (`pan=±20`) and about 8 to 10 dB under the lead. They follow the chords automatically.
- The mixer de-esser is off by default, and the agent never switches it on by itself. The one bundled with LMMS 1.2 cuts everything above its split frequency whatever its threshold (measured: −7 dB from 9 to 16 kHz). Add it only when the user asks, with `song.vocal(..., deesser={})`. The split defaults to 9 kHz. Pass `fx.deesser` arguments in the dict, for example `{"split_hz": 7000, "threshold_db": -20}`.
- Character effects (distortion for industrial, bitcrush for lo-fi, a chorus for an 80s sheen) are added after the standard vocal strip with `song.vocal(..., effects=[("distortion", {"drive": 4.0})])`, using the builder names from `sounds-effects.md`. Heavy processing costs clarity, so listen to the result with the user.

## What to hand the user

For a vocal song, deliver for listening and approval:

- The lyrics file (`<name>.lyrics.txt`, written on save, with section headings and time stamps).
- The dry lead vocal alone (`samples/<project>/lead_vocal.flac`, convert with `render.convert` if needed), so words can be judged without the music.
- The table of lines with what the recogniser heard and the scores (`out/vocals.json`, or the `weak_line` findings).
- When wordings were compared: the candidates table and the audio of the top two.
- When the user must choose between methods or voices: the same chorus rendered each way.

Ask for the user's verdict on the words before polishing the mix around them.

## Other languages

- Singer voicebanks sing the languages they list.
- Piper has voices for many languages: `piper:<voice id>` with the id from the Piper voice list (for example `piper:de_DE-thorsten-medium`, `piper:es_ES-davefx-medium`), plus `lang="de"`. The voice is downloaded on first use. Recognition switches to a multilingual model automatically.
- Outside English, expect lower recognition scores, no line-ending repair until a carrier word is registered, and lyric-craft hints that only partly apply (the weak-word list is English). Check syllable counts with `lyric-lint` and judge by listening.
- Kokoro's built-in voices here are English.

## Known limits

- A speech voice made to sing keeps its speech timbre. It will not pass for a trained singer. Say so before the user expects otherwise, and offer the voicebank route.
- Very fast syllables (under about 110 ms), wide leaps inside a word, and melodies far above the speaking pitch degrade first.
- The recogniser is unsteady on sung audio. The same take can score a few tenths apart depending on the silence around it. A failed pass returns an empty or invented transcript, so one good pass is luck and two are evidence. The score is therefore the second-best pass: three passes when they agree within 0.1, six more when they do not. Small differences mean nothing. It also "repairs" words from context, so a high score is not proof of clarity. A low score on a line the user finds clear should be ignored.
- Speech models report when each sound starts, and those times run late against the audio by an amount that differs per engine, voice and line (roughly 40 ms for the Kokoro voices and near 0 for the Piper voices tested). The toolkit measures this lag on every line from the audio itself and reports it as `lag_ms`. A value far from those, or a line whose syllables land audibly off the beat, points to a line the alignment misread: reword it or split it.
- The lag is the shift that puts the reported vowels on the most periodic frames of the audio, with a mild preference for the usual value. Two corrections follow before the line is planned. A full vowel whose reported span is still mostly unvoiced moves onto the voiced frames beside it, inside its own syllable. This happens most often to the first word of a line, which the engines time early. A reduced vowel stays where it is, because a quiet schwa is the sound itself. A word gap that is still voiced goes to the vowel before it, so each note is built from the vowel's steady middle.
- The repair fixes the last syllable only. A whole line spoken too softly needs different words or another voice.
- Rendering is slow compared to the instruments: plan about 3 to 10 s per line for speech voices and 10 to 20 s for a voicebank on two CPU cores. Lines are cached.

## Measurements behind this page

Measured with the tools in this skill. Scores are recognition scores from 0 to 1.

Line endings before and after the repair (132 BPM, same notes, last note held 3 beats):

| Voice | Lines whose ending was dying | Voiced share of last vowel | Tone steadiness of last note |
|---|---|---|---|
| `kokoro:af_heart` | 7 of 8 | 0.25 to 0.60 before, 1.00 after | 0.10 to 0.93 before, 0.99 to 1.00 after |
| `kokoro:am_michael` | 8 of 8 | 0.34 to 0.80 before, 1.00 after | 0.20 to 0.98 before, 0.93 to 1.00 after |
| `piper:en_US-ljspeech-high` | 2 of 8 | 0.56 to 0.74 before, 1.00 after | 0.53 to 0.80 before, 0.99 to 1.00 after |

Endings in "ee" and "oo" (me, sea, you, undo) died most completely on the Kokoro voices (voiced share 0.25 to 0.54). Endings in "oh" and "ay" (low, know, grey, glow) often kept more voice but were still repaired when they fell under the threshold. The Piper voice rarely needed the repair. This is why the repair decides per line. Recognition scores did not move in a consistent direction with the repair, because the recogniser guesses a last word from context either way. What the repair changes is the held note itself: hiss before, a pitched tone after, which the voiced share, the steadiness figure and the spectrogram show.

Same notes, different words (132 BPM, pairs that differ in one habit from the craft list):

| Notes | Weaker wording | Score | Stronger wording | Score | Voice |
|---|---|---|---|---|---|
| 3 notes, last held | come what may | 0.54 | anyway | 1.0 | af_heart |
| 3 notes | feel the glow | 0.62 | let it glow | 1.0 | af_heart |
| 5 notes, last held | burning till the day | 0.80 | burning all the way | 1.0 | af_heart |
| 5 notes, last held | sinking down so low | 0.84 | all the things we know | 1.0 | af_heart |
| 5 notes | someone is singing | 0.56 | voices are singing | 1.0 | am_michael |
| 5 notes, last held | burning till the day | 0.50 | burning all the way | 1.0 | am_michael |

The same pairs did not always fall the same way on another voice ("someone is singing" scored 1.0 on af_heart and 0.56 on am_michael), which is the reason to measure per voice.

Spectral balance of lead syllables by vowel, measured on the dry stems of seven finished songs (Kokoro voices, 1,655 syllables, medians; body is 300-1300 Hz, the level is against the median body level of the syllable's line):

| Vowel | Syllables | 1.3-5 kHz against body | 5-9 kHz against body | Body level against the line |
|---|---|---|---|---|
| ee (iː) | 149 | -2.8 dB | -5.3 dB | -9.1 dB |
| i (ɪ) | 502 | -8.4 dB | -18.1 dB | 0.0 dB |
| ay, e (eɪ ɛ) | 115 | -7.8 dB | -20.4 dB | +1.6 dB |
| schwa (ə ɐ) | 263 | -13.6 dB | -19.3 dB | -2.4 dB |
| open and back (ɑ æ ɔ oʊ uː ʌ) | 626 | -14.5 dB | -24.9 dB | +1.1 dB |

The ee syllables carry as much energy above 1.3 kHz as in the body and sit 9 dB under their line, which is the thin, hissing sound of held he, she, we, see. The word "we" alone (41 syllables) sat 10 dB under its line. The syllables of "the" (104) kept the line's level but had the most 5-9 kHz of the function words, from the voiced th.

`Style(vowel_body=1)` on the 24 lead lines of those songs that hold an ee vowel (medians over the ee syllables unless noted):

| Measure | Fill off | Fill on |
|---|---|---|
| Body against the line | -8.8 dB | -6.4 dB |
| Body against the line, worst lines | -18 to -19 dB | -10 to -13 dB |
| 1.3-5 kHz against body | -4.4 dB | -7.2 dB |
| 5-9 kHz against body | -11.0 dB | -14.8 dB |

The line level did not change. The recognition score stayed the same on 22 lines, rose on one and fell on one.

Timing by vowel periodicity, on the affected lines of seven songs: the mean periodicity of the vowel middles rose from 0.68 to 0.73, the upper bound. Vowels whose reported span was mostly noise fell from 32 of 1,798 to 11, and nine of those 11 are reduced vowels left alone on purpose. On the 50 lines that held such a vowel, the mean recognition score rose from 0.95 to 0.98. An earlier rule matched the voiced and unvoiced pattern of the audio. The pitch tracker voices loud fricatives, so that rule was fooled: a line opening with "share" got the full 150 ms of lag and was sung as a long "sh".

The vocal margins (`vocal_body`, `vocal_consonants`) count every frame while a lead line is sung. An earlier edition counted only frames within 12 dB of the band's loudest frame. In the consonant band these were a few sibilant bursts, 2-30% of the sung frames, so the margins read 4-12 dB too high.
