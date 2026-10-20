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

A good singer voicebank is the first choice when the user has one, most of all for exposed lead vocals. The speech voices are the fallback that always works, and they suit electronic styles where a processed voice is at home (futurepop, EBM, synthpop, electro, vocoder hooks, etc.).

`python scripts/lmms_tool.py voices` lists the built-in speech voices with gender, accent and notes. `voices <voice id>` describes one voice, and for a voicebank it lists languages, voice colours and the documents that state its terms. For a bank with several voice colours, add `#colour` to the id to pick one. Without it the first colour sings.

Speech voices have two methods. `stretched` (default) analyses the spoken line and re-synthesizes it on the melody: any pitch, clearest words in testing. `held` (`method="held"`, Kokoro only) lets the speech model itself hold the vowels: a more natural tone inside the voice's clean range, weaker outside it. Render the same line both ways and let the user pick when the vocal tone matters to them.

## Offering voices during planning

Offer the choice, with a default, when the song has vocals:

1. A singer voicebank, if the user has or wants to supply one.
2. A built-in speech voice. Defaults: `kokoro:af_heart` (female), `kokoro:am_michael` (male). The other Kokoro voices and the Piper voices are in the `voices` list.
3. No vocal, or a vocal melody played by a synth lead.

The voice is a choice of timbre, and it belongs to the user. Use the default voice or the one the user named, and keep it. When a line is unclear, change the wording or the notes first (see the word-choice procedure). Recognition scores do differ between voices on the same line, but a higher score is no reason to swap the singer on your own: offer the comparison (`compare` with `--voice` changed, audio included) and let the user decide.

Some built-in voices carry licence notes (shown by `voices`). Pass them on when the user plans to publish.

## Singer voicebanks the user supplies (DiffSinger)

The toolkit renders DiffSinger voicebanks in the OpenUtau folder layout (a folder containing `dsconfig.yaml`). It contains no voicebank, names none, and downloads none on its own initiative. Handle only what the user hands over:

- A folder path: use it directly. `voices diffsinger:<folder>` confirms that it loads.
- An archive file: unpack it into a new empty folder outside the song project, then use that folder. Unpack with `python -m zipfile -e <archive> <folder>`, which keeps file names written in other scripts (a terms document named in Japanese or Russian). `unzip` garbles them where the system language is not UTF-8. When names still come out garbled (an archive made on Japanese Windows), add `--metadata-encoding cp932`.
- A link to a repository or download page the user gives: fetch exactly that into a new empty folder. Do not search for voicebanks or suggest sources. For a GitHub repository link, before fetching: if the execution environment has a tool that attaches a GitHub repository to the session, call it. Pass the owner and the repository name from the link as separate values. Follow any access route the tool's reply names. Skip this step when no such tool exists or the call is refused.

A repository that uses Git LFS leaves pointer files after the clone (small files that start with `version https://git-lfs.github.com/spec/v1`). Clone with `GIT_LFS_SKIP_SMUDGE=1` so an unreachable LFS server cannot stop the clone. Fetch the remaining files from `https://media.githubusercontent.com/media/<owner>/<repo>/<commit>/<path>` on GitHub or from `<repository address>/resolve/<commit>/<path>` on Hugging Face, and check each against the sha256 in its pointer. Use `git lfs pull` for other hosts and for private repositories. Do not use the folder while any pointer remains.

Before the first render with a bank:

1. Run `voices diffsinger:<folder>`. Find the documents that state the terms of use yourself by checking every file in the voicebank folder, subfolders included, and open them. File names differ in language and form from bank to bank (for example readme.txt, character.txt, 利用規約.txt). Also open any terms page those documents point to.
2. Tell the user in a few plain sentences what the terms say about the points that matter: commercial use, credit, content restrictions, redistribution of the bank or of audio, and use for machine learning. Quote the source when the wording is unusual.
3. Ask the user to confirm that the planned use fits. If no terms can be found, say so and ask the user how to proceed.
4. Put the required credit into the delivery notes and into the lyrics file or metadata when the terms ask for it.

Never copy a voicebank into the song project, into exports, or into a `pack` archive. Only rendered audio leaves the machine.

Usage:

```python
vocal = song.vocal("lead vocal", "diffsinger:/path/to/bank#Soft", lang="en", steps=20)
```

- `#name` picks a voice colour when the bank has several. Without it the first one is used.
- `lang` must be one of the bank's languages, or a language the bank has a dictionary file for. Words missing from the bank's English dictionary are pronounced through a built-in fallback. German, French, Spanish, Italian, Portuguese and Russian words missing from its dictionary go through OpenUtau's G2P, downloaded once (see `setup.md`). Languages written without spaces are looked up by the longest dictionary entries from the left, so a kana pair such as きゃ counts as one entry.
- The bank's dictionary decides the spelling of the lyrics. Open its dictionary file (`dsdict*.yaml`), check the `grapheme` entries and write the lyrics the same way. A bank whose dictionary holds no words of a language (its OpenUtau phonemizer converts them in code) sings only German, French, Spanish, Italian, Portuguese and Russian here, through that G2P. A word with a sound the bank lacks stops the line with an error naming the sound.
- A bank's dictionary or a G2P pack can also write a word wrong. When a word sounds like another language or the recogniser hears another word, check the symbols in the `phonemes` of the `sing` report. If they differ from how the language says the word, give the line `phonemes` modelled on the symbols of related words.
- Options: `steps` (quality against time, default 20), `gender` (−1 to 1, formant shift), `velocity` (consonant speed), `tension`, `breathiness`, `expressiveness` (how far the bank's own pitch model moves from the notes, default 1.0), `own_pitch=False` to draw the pitch curve from the Style settings instead of the bank's pitch model.
- A bank's pitch model sings each note with slides and swings of its own, so the start of a note can sit well off the written pitch. When notes sound slightly off, lower `expressiveness` from its default 1.0 (try 0.5) or set `own_pitch=False`. The measured effect is under Measurements behind this page.
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

- `line(at, text, melody, kind=None, beats=0.0, phonemes=None)`: `at` is where the first melody token starts. `beats=-1` starts a pickup one beat before the bar.
- `phonemes=` gives the line's pronunciation in the voice's own symbols, sung instead of reading the text. For a speech voice, edit the `phonemes` of the `sing` report (what the voice read). For a voicebank, write its own symbols with `|` between words (`en/hh en/ah | en/l en/ow`). An entry not written in the bank's symbols is noted and the line is sung from its words. A line with given phonemes gets no line-ending repair. To try one line, give `--phonemes` to `sing` and `lyric-lint`.
- Lines are sung when the song is saved, cached in `.vocal_cache/` beside the project, and placed so that each vowel starts on its beat. Changing one line re-sings only that line.
- Each part becomes one audio file under `samples/<project>/` and one track with a vocal channel strip (EQ, compression, reverb send).
- `song.vocal(..., level_db=, pan=, sends=, effects=, method=, lang=, speed=, style=, fix_ending=)`.
- `speed=` is the reading speed of a speech voice. Left out, each line is read at the pace of its melody: 0.21 s (a syllable at speed 1) divided by the line's typical note, kept between 0.7 and 1.15. A number reads every line of the part at that speed (1.0 is the voice's own pace). The `held` method reads at 1.0 unless a number is given: Kokoro's own decoder sings the joins between words there, and the matched speed made no clear difference (36 English lines, mean score 0.872 at 1.0 and 0.878 matched). Voicebanks have no reading speed.

## Melody notation

One token per sung syllable, separated by spaces:

- `E4/1` sings the syllable on E4 for one beat.
- Joining notes with `~` sings one syllable on several notes. For example, `E4/0.5~G4/0.5` bends one syllable from E4 to G4.
- `R/0.5` is a rest of half a beat.

The words are matched to the tokens by syllable, in order. If the counts differ, the tool stops with a table of syllables per word. Fix the melody or the words. Words whose syllable count is unstable in speech (fire, hour, every, different) are best given one long note or replaced.

`python scripts/lmms_tool.py sing --voice <id> --text "..." --melody "..." --bpm 132 -o work/line.wav` sings one line alone and prints its report with a recognition score.

## Lyric craft

Before writing, find out what the chosen voice sings well. The kind of voice (speech voice or singer voicebank) and the language decide which rules in the table below apply. Choose the words and the sentence structure to fit those rules from the start. Changing words after the lyrics are finished means fitting meaning and rhyme again.

- Where the rules are silent, also review the lines from several seats, such as a lyricist (e.g. meaning, imagery, rhyme), a singer (e.g. where to breathe, notes that follow the natural rhythm of the words), a listener (e.g. whether the words come through and stick on first hearing), a sound engineer (e.g. bands shared with the backing, places where the lead collides) and an agent operator (e.g. whether the limits of the tools the skill relies on, such as speech voices, singer voicebanks, speech recognition and the mixer, were taken into account). Note the reason in the delivery note for any choice that departs from the rules.
- Fit the sentence structure to the voice too. Pick a word order that keeps weak function words (to, the, a) off beats and long notes. Recast a sentence that opens with function words or stacks them in a row so that a content word leads. A speech voice reads to with a weak vowel, so it sinks on a beat or a long note (see the reduced-vowel rule below).
- Avoid, or test early, words a pronunciation dictionary is unlikely to hold (proper nouns, invented words, abbreviations, foreign words). A speech voice guesses their pronunciation from the spelling, so it may read them differently than intended. A singer voicebank sings a word missing from its dictionary with a guessed pronunciation in English, German, French, Spanish, Italian, Portuguese and Russian, and stops at such a word in other languages.
- Write numbers and symbols out as the words to be sung.
- For a word the song needs, such as the title or a name, sing a line containing it with `sing` or `compare` before writing the other lines. If it is misread, respell it by sound in the text given to the voice or give the line its `phonemes`, and keep the original spelling in the lyric file for the user.

Review lyrics the user wrote by the same measures once the voice is chosen, before they are sung. For each line the chosen voice is unlikely to sing well, give the reason and a revised line. Where it helps, sing the original and the revision with `compare` and show the scores and the audio. Apply only the revisions the user approves. If the user insists on the original, state once, clearly, what loss of quality to expect on that line, then go on with the original and record the measurements and limits of that line in the delivery notes (`SKILL.md` stage 1).

Sung words are harder to follow than spoken ones, and a model voice has less to spare than a human singer. These habits raise the odds. They are starting points from measurements on English speech voices, so check them with `compare` instead of trusting them blindly.

Not every rule is about speech voices:

| Rules | For | What they cover |
|---|---|---|
| Singing craft | Any voice, a human singer included | Stress on the strong beats, note lengths that follow the spoken stress, 110 ms or more per syllable, open vowels or nasals on held notes, reduced vowels and weak function words off the beats |
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
- At 150 BPM and above, avoid runs of eighth-note syllables and start from one syllable per beat. Once a syllable gets shorter than about 200 ms (an eighth at 150 BPM is 200 ms), consonants start to blur even in a singer voicebank. `fast_syllables` points at a line with three or more syllables shorter than 200 ms.
- Put the stressed syllable of a multi-syllable word on the stronger beat. Beat strength runs: the downbeat, beat three, beats two and four, the off-beats, then 16th places. `stress_on_weak_beat` warns when the stressed syllable sits on a weaker beat than an unstressed syllable of the same word and its note is no longer. The stress comes from the voice's pronunciation dictionary.
- Let note lengths follow the spoken stress. After writing a line, mark each syllable strong or weak as it is spoken ("Rise and fall" runs strong, weak, strong) and set the marks beside the note lengths. The longest note of a line goes to a content word. When a function word or a weak syllable takes the longest note and the stressed syllable after it is clipped short, the stress is reversed. "Rise and fall" with "and" held for two beats and "fall" cut to half a beat is one example. A human singer struggles with such a line too, so give the stressed syllable the long note.
- Take the vocal rhythm from the spoken stress of the words. To sing a melody written for an instrument (a lead hook, a theme, a riff), rewrite its rhythm to the spoken stress first. In arrangements where the lead plays the vocal's melody (synthpop, futurepop, etc.), fix the vocal line first and let the lead follow its rhythm.
- Leave the dramatic devices to the arrangement. Risers, snare rolls and impacts carry the build-up and the drop (trance, big room, etc.). Instruments carry sudden stops and hits (darksynth, etc.) and fast runs and trills (chiptune, etc.). To build tension in a sung line, hold the last word itself. For a clipped effect, give the last word a beat or more and cut it with a rest.
- Keep the rhythmic density of a line from changing all at once. Three shapes do this: a burst of fast syllables running into a long note, a burst of syllables after a long rest or slow notes, and a long build-up that ends on a clipped last word. The singer has no place to breathe, and the last word, the point of the line, is over before it is heard. Even out the burst to the pace of the line's start or cut syllables from it. `fast_syllables` points at fast runs. `clipped_line_end` warns at a line that ends, after a note held 2 beats or more, on a last syllable a quarter of that note or shorter.
- Keep a clipped delivery that is part of the genre (the shouted lines of EBM, industrial, etc.) only when the last word comes through in the vocal-only render. Put such a line in the delivery note, with the reason, among the lines to check by ear. For sounds whose job is not to carry words (vocal chops, vocal shots), write their purpose in the delivery note to keep them apart from the lead lyric lines.
- Avoid three weak words in a row, and two short weak words running into a long note (`weak_words_in_a_row`, `weak_pickup`).
- A function word on a short off-beat note can still blur. On a 134 BPM song sung by Kokoro `am_michael` through a different singing converter, listening found the to of "to every" and the could of "could ever" blurred on eighth-note off-beats. The recognition score and `ROUGH` rarely catch this fault (Known limits), so reduce it while writing. Rewrite a line flagged `weak_words_in_a_row` or `weak_pickup` only when a content-word phrasing keeps the meaning and the rhyme, and offer the rewrite for lyrics the user wrote. If no such phrasing exists, keep the warning and judge the line by ear.
- Chorus lines: 5 to 7 syllables, a held last note, and the title in the first or last line.
- Keep the melody within about an octave above the speech voice's natural pitch (the line report shows `natural_pitch`). A singer voicebank has its own comfortable range.
- Leave air between lines: one or two beats of rest so the reverb tail and the listener can catch up.
- Rhyme by vowel sound. Spelling is no guide (move and love do not rhyme).

`python scripts/lmms_tool.py lyric-lint --voice <id> --text "..." --melody "..." --bpm 132` checks a line against these habits before anything is sung. Run it on each line as you write it, with `--lang` for lyrics outside English (`--lang ko`). Once the project exists, `lint song.mmp` repeats the same checks on every lead line (`lyrics_*` findings). For a line that does not start on the downbeat, pass its starting beat within the bar (`--start-beat 0.5`) so the stress check sees the right beat strengths.

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

After the song is built, `produce` scores each different lead line once and lists the weak ones (`weak_line`, score under 0.85) with possible causes. Lines that come through clearly produce no lyric warnings, whatever the craft rules say. A line that keeps `weak_words_in_a_row`, `weak_pickup` or `clipped_line_end` in `lint` goes into the delivery note as a line to check by ear, whatever its score. Backing parts (harmonies, doubles) get no recognition score or pitch error. They do get the `ROUGH` and `ending_dies` checks, because a nearly silent harmony syllable leaves a hole under the lead that no lead check can see. When either warning names a backing part, rest the backing on that word or lower the part. By default the recogniser is the small `base` model (`base.en` for English). For lyrics in another language it can mishear lines that are sung clearly, so a larger model (`--asr-model small` on `produce`, `check`, `sing` and `compare`, or the setting `asr_model`) gives fewer false weak lines. Measured on a 4-core CPU checking one 5-second line: base 402 MB of memory and 5.7 s, small 869 MB and 8.7 s, medium 2.1 GB and 23 s; the first use downloads 142 MB, 464 MB and 1.5 GB.

The same check measures two more things per line. They appear in the `vocal_scores` table next to each line's score, and every line in `out/vocals.json` carries them as `pitch_error_cents` and `rough`.

- Pitch error (`pitch_error_cents`): the median distance in cents between the sung pitch and the written notes, measured in the vowels away from the note edges. 10 to 15 cents is normal. Above 25 the line is heard as out of tune. When at least two lines, and half or more of the different lines, are above 25 cents, `off_pitch_lines` appears. The melody then lies outside the range this voice holds cleanly: transpose the part toward its natural pitch or choose another voice.
- Rough syllables (`rough_syllables`, `ROUGH` in the report): vowels that came out as noise (`noise`, periodicity under 0.6) or were swallowed (`quiet`, 8 dB under the line's typical vowel). The score finds lines whose words come out wrong. `ROUGH` finds syllables that grate even when the words are understood, so a line scoring 1.00 can still be rough. Check both. A syllable that is mostly consonant by design on a short note is not judged.
- Cut opening (`cut_at_song_start`): a line whose opening consonants would sound before the song starts loses them, and the warning gives the lost length. Start the line later or give the song a bar before it.
- Weak and `ROUGH` lines get a figure in `out/vocals/<part>_lineNN.png`. A smudge where the vowel should show stripes is a real fault: lengthen the note, choose a word with fewer consonants around the syllable, or try another voice and check again. `references/visual-qa.md` explains the figure.

## Line-ending repair

A speech voice lets the last word of a sentence die away: quieter, breathy, often whispered. In a song the last word usually holds the longest note, and a whisper held for a bar is hiss. The toolkit repairs this automatically for speech voices:

- It speaks the line a second time with a short carrier word after it (English: "but"), which keeps the real last word in full voice, and splices only that last syllable into the plain take. The carrier word itself is never heard.
- It acts only when the ending is judged to be dying: less than 85% of the last vowel is voiced, or the vowel is 9 dB or more below the line's typical level. Other lines are left untouched.
- It checks that the carrier take has the same syllables before splicing, and falls back to the plain take when anything is off. Results are cached.
- Switch it off for a part with `song.vocal(..., fix_ending=False)` or for one test line with `sing --no-ending-fix`, for example when the fading ending is the effect the user wants.
- The carrier word exists for English ("but") only. Lines in other languages are not repaired, and a line whose ending fades gets the `ending_dies` warning.
- Singer voicebanks do not need the repair and are not touched by it.
- When the ending still dies after the repair (or the repair could not be applied), `produce` raises an `ending_dies` warning and draws that line's figure. It uses the same criteria as the repair. Change the last word to one ending on an open vowel or diphthong, give it a shorter note, or try another voice. `ROUGH` averages over the whole vowel and can miss this fault, so read both warnings together.

What not to do about dying endings: do not boost the ending with a compressor or volume automation (it raises the hiss), do not add a comma or an exclamation mark to the lyric to force emphasis (it changes the rhythm and timing of the whole line), and do not cut the last note short to hide the problem.

To check the repair on a new voice, sing the same line with and without it and compare: the line report gives `voiced_share` before and after, and `visual.compare_spectrograms` shows the last note as clean horizontal stripes (voiced) or as a grey cloud (whisper).

## Performance style

`from lmmskit.vocal.singing import Style`, then `song.vocal(..., style=Style(vibrato=1.0, scoop=0.6, drift=1.0, evenness=0.7, seed=0))`.

- `vibrato`: 0 is a straight tone, 1 the default, 2 wide. It starts late on long notes, as singers do.
- `scoop`: how far phrase starts slide up into the note.
- `drift`: slow random pitch wander that keeps held notes alive.
- `evenness`: 0 keeps speech dynamics, 1 makes every syllable equally loud.
- `sibilance`: default 0 (off). It finds every s, z and sh, and every t, k and p burst, that rises more than 3 dB above the line's vowel body (300-1300 Hz). On that phone's own span it cuts above 5 kHz by the excess, at most by the set value in dB (4 or so). Unlike a mixer de-esser, it knows where the consonants are and touches nothing else. In five songs, 13% of bright consonants rose more than 3 dB (up to +13 dB), and most of the loudest were t and k bursts. On the worst lines a setting of 4 took 2-3 dB off the peaks and changed one line's recognition score. Use it for a voice that sounds spitty, and leave it off otherwise.
- `vowel_body`: default 0 (off). At 1 it fills each held ee vowel (he, she, we, see; 0.2 s or longer) with the 300-1300 Hz body of the line's other vowels, aiming 3 dB under them and lifting at most 10 dB. On the same frames it thins the breath noise above 2 kHz. A singer does the same by opening ee toward ih on a long note. On 24 lines from seven songs it raised the median ee body from 8.8 dB to 6.4 dB under the line, took 3 dB off the metallic 1.3-5 kHz excess and 4 dB off the hiss above 5 kHz, and left 22 recognition scores unchanged. It shifts the vowel's colour a little, so listen to the ee words before keeping it.
- `seed`: a different seed gives a different take. `double()` uses this.

Deadpan styles (doomer, coldwave, EBM, etc.) want `vibrato=0.3, scoop=0.3`. Anthemic choruses can take the defaults or more vibrato. For a singer voicebank these settings shape the pitch only with `own_pitch=False`. Otherwise the bank's own pitch model performs the line.

## Vocals in the mix

- Targets, measured on the stems only while a lead line is sung (the line times of the vocals file): the lead should sit at or above the backing between 300 and 3400 Hz (`vocal_body`), and at least 2 dB above it between 1.3 and 5 kHz (`vocal_consonants`), where consonants live. More than 9 dB above reads as a vocal pasted on top. This window follows the mix style chosen in the plan: forward and vocal move it 1.5 dB up, blended 2 dB down (Mix styles in `mixing.md`).
- Both findings report a whole-song value and a value per section. The floor and the ceiling are judged on the section whose backing is densest (usually a chorus), because a sparse verse lifts the whole-song value and hides a chorus that falls short.
- Voices differ by many dB in the 1.3-5 kHz band (in the test songs a singer voicebank started 4.7 dB under the backing and a speech voice 7.6 dB over it with the same channel settings). The balance step therefore measures the margin and adds a presence lift of up to 6 dB to the lead vocal when it falls short. The report shows the lift under `vocal_presence`.
- What the lift cannot close comes from the backing. Every song with a vocal part gets ducking automation on the music bus while a lead line is sung. By default the whole bus drops 2.5 dB, and the consonant band dips 6 dB at its centre. The dip is 1.5 octaves wide: it lowers the 1.3-5 kHz band by about 2.7 dB and leaves the music above 5 kHz nearly untouched.
- A genre profile's `vocal_duck` pair replaces these defaults, the mix style shifts them (forward and vocal +1 and +1, blended -1 and -2), and `song.duck_for_vocals(depth_db, presence_db)` in the song script overrides all of them. `song.duck_for_vocals(0)` turns the ducking off. `presence_octaves` changes the dip width when the production the user wants calls for it (default 1.5). Wide values are not recommended and stay off by default.
- The dip acts on the music bus only. When hats, claps and snares are what covers the consonants, the `vocal_consonants` warning says so and names the remedy: fewer bright drum hits under the lines, or a little more vocal level. Also rest the lead synth while the voice sings.
- When the vocal sounds small, deepen the ducking first, then thin out the parts under the vocal, and leave raising the vocal `level_db` for last. In the test songs, +1.5 LU of vocal sounded the same as the default ducking (2.5/6.0) but spent 1.2 dB of limiter headroom and kept the chorus ceiling warning on for good. At +3 LU the vocal sat on top of the track.
- Do not sidechain the vocal or its reverb to the kick. Pumping chops consonant tails and makes words harder to follow. The vocal bus is outside the sidechain by default.
- When listening to the mix, check the t, s and z of each line first for peaks and a metallic edge. Then check whether ee words drop under their neighbours or ring. Tame stinging consonants with `sibilance` in the Style, which acts only on those phones. Do not reach for a mixer de-esser, which cuts all treble. Fix a buried ee word in the lyric or with a shorter note, because a level boost raises its hiss too.
- Harmonies and doubles go to the sides (`pan=±20`) and about 8 to 10 dB under the lead. They follow the chords automatically.
- The mixer de-esser is off by default, and the agent never switches it on by itself. The one bundled with LMMS 1.2 cuts everything above its split frequency whatever its threshold (measured: −7 dB from 9 to 16 kHz). Add it only when the user asks, with `song.vocal(..., deesser={})`. The split defaults to 9 kHz. Pass `fx.deesser` arguments in the dict, for example `{"split_hz": 7000, "threshold_db": -20}`.
- Character effects (distortion for industrial, bitcrush for lo-fi, a chorus for an 80s sheen, etc.) are added after the standard vocal strip with `song.vocal(..., effects=[("distortion", {"drive": 4.0})])`, using the builder names from `sounds-effects.md`. Heavy processing costs clarity, so listen to the result with the user.

## What to hand the user

For a vocal song, deliver for listening and approval:

- The lyrics file (`<name>.lyrics.txt`, written on save, with section headings and time stamps).
- The dry lead vocal alone (`samples/<project>/lead_vocal.flac`, convert with `render.convert` if needed), so words can be judged without the music.
- The table of lines with what the recogniser heard and the scores (`out/vocals.json`, or the `weak_line` findings).
- When wordings were compared: the candidates table and the audio of the top two.
- When the user must choose between methods or voices: the same chorus rendered each way.

Ask for the user's verdict on the words before polishing the mix around them.

## Other languages

- `lang` (en, ko, ja, zh, ru ...) is the language of the lyrics for every engine. A speech voice reads the text with that language's pronunciation, a voicebank looks the words up in that dictionary, and the recogniser listens for that language. Give the same code to `song.vocal(..., lang=)`, `sing`, `compare` and `lyric-lint`.
- Outside English, the melody's notes give the syllable count. When the pronunciation has more vowels than notes, the toolkit joins vowels that meet inside a word, and `folded_syllable` names the joins. If a join is wrong, or syllables are missing (`syllable_count`), give the line its `phonemes`. A syllable with no vowel (Serbo-Croatian srce) takes a short vowel (ə) before its consonant there.
- Singer voicebanks sing the languages they list.
- Piper has voices for many languages: `piper:<voice id>` with the id from the Piper voice list (for example `piper:de_DE-thorsten-medium`, `piper:ko_KR-kss-medium`, `piper:ru_RU-irina-medium`), plus `lang="de"`. The voice is downloaded on first use. Recognition switches to a multilingual model automatically. The Piper Japanese voice needs the `pyopenjtalk` package.
- Kokoro's built-in list here holds English voices. Its Japanese (`kokoro:jf_alpha`) and Mandarin (`kokoro:zf_xiaobei`) voices also sing, with `lang="ja"` or `lang="zh"`. A line with characters the voice cannot read gets an `unreadable_text` error that names the words: write them in a script the voice reads, or choose a voice that reads them. An English Kokoro voice reading another language keeps a strong English accent, so choose a voice of that language. A Kokoro voice of the lyrics' language keeps its own variant: `lang="pt"` with a Brazilian voice (`kokoro:pf_dora`) reads Brazilian Portuguese.
- Outside English, expect lower recognition scores and no line-ending repair.
- The weak-word rules of `lyric-lint` (`weak_opening`, `weak_words_in_a_row`, `weak_pickup`, `weak_word_on_long_note`) and `unstable_word` match the spelling against English word lists. In another language such a warning comes from a word spelled like an English one, so judge it by the role the word has in that language. The rules read from the sounds (short notes, clusters, reduced vowels, bright consonants, held ee, stop endings) apply to every language; their numbers were measured on English voices.
- Languages that write the same words in several scripts (Japanese kana and kanji, Chinese simplified and traditional characters) can come back from the recogniser in another script than the lyrics. The score compares characters, so a line sung right can still score low.
- For a `weak_line` in such a language, read what was heard in the warning. The same words in another script (ありがとう and アリガトウ, 谢谢你 and 謝謝你) mean the line came through. Other words, or a kanji heard with another reading (君 as きみ or くん), mean it was misheard.

## Known limits

- A speech voice made to sing keeps its speech timbre. It will not pass for a trained singer. Say so before the user expects otherwise, and offer the voicebank route.
- Very fast syllables (under about 110 ms), wide leaps inside a word, and melodies far above the speaking pitch degrade first.
- The recogniser is unsteady on sung audio. The same take can score a few tenths apart depending on the silence around it. A failed pass returns an empty or invented transcript, so one good pass is luck and two are evidence. The score is therefore the second-best pass: three passes when they agree within 0.1, six more when they do not. Small differences mean nothing. It also "repairs" words from context, so a high score is not proof of clarity. A low score on a line the user finds clear should be ignored.
- A blurred short function word is hard to catch with the recognition score. The score compares the characters of the whole line, so a transcript of a 31-character line missing one to still scores 0.90, above 0.85. The recogniser also often fills in function words from context. Reduce them while writing, and judge the lines that keep them by ear.
- Speech models report when each sound starts, and those times run late against the audio by an amount that differs per engine, voice and line. The toolkit measures this lag on every line from the audio itself and reports it as `lag_ms`: about 40 ms on the Kokoro voices tested, and 25 to 40 ms on the Piper voices, whose own lag is nearer 0, because the measure leans toward the usual value. The boundary snap described next takes out what is left, so a syllable lands on its beat even when `lag_ms` is a few tens of milliseconds off. A line whose syllables still land audibly off the beat points to a line the alignment misread: reword it or split it.
- The lag is the shift that puts the reported vowels on the most periodic frames of the audio, with a mild preference for the usual value. Before it is applied, the time an engine reports for the space between two words goes to the sounds around it (half to each on Kokoro, all to the following sound on Piper). After it, every boundary where the voice or a hiss should switch on or off moves onto that switch in the audio when it lies within 50 ms, and the boundaries between move in proportion (`snapped` in the line report counts them). A full vowel whose reported span is still mostly unvoiced then moves onto the voiced frames beside it, inside its own syllable. This happens most often to the first word of a line, which the engines time early. A reduced vowel stays where it is, because a quiet schwa is the sound itself. The beat falls where each vowel's voice really starts: an unvoiced start of the vowel (aspiration after p, t, k or h) is sung before the beat with the consonants.
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

Beat alignment, on the lead lines of the two example songs with vocals sung by `kokoro:af_heart`, `kokoro:am_michael`, `piper:en_US-ljspeech-high` and `piper:en_US-bryce-medium` (56 different lines). The measure is the time from a note's start to the moment the voice really starts (pitch found, periodic, within 24 dB of the loud frames), on syllables that open on a voiceless consonant or after a rest. With the boundary snap, the shared word gaps and the beat on the voice's real start, it fell from a median of 10 ms to 1.6 ms, and at the 90th percentile from 35 ms to 6.8 ms. The voicing rule (vowels and sonorants always voiced, b, d, g, v and z only where the speech was voiced, voiceless sounds never) took the vowels sung as noise from 1 to 0. The mean recognition score went from 0.947 to 0.948 and the lines under 0.85 from 9 to 4. The pitch in the first 90 ms of a note sat 5.9 cents from the written note before and 6.5 after, because the voice now starts inside the glide into the note. One lag for the whole part, measured over all its lines, did worse than each line's own lag with the snap in three variants (90th percentile 6.8 to 13.6 ms, mean score 0.926 to 0.941), so it is not used.

Singer voicebanks, on two DiffSinger banks and the same two songs (28 different lines): the voice started a median 7 ms from the beat, as with the speech voices. The pitch in the first 90 ms of a note sat a median 22 cents from the written note and 137 cents at the 90th percentile, against 5.9 and 12.5 cents for the speech voices, and the held part of the note sat 17 cents off. Both come from the bank's pitch model: with `expressiveness=0.5` the three figures were 4.5, 9.4 and 4.1 cents, with `own_pitch=False` 5.5, 13.0 and 7.2 cents. The mean recognition score stayed between 0.940 and 0.950.

The vocal margins (`vocal_body`, `vocal_consonants`) count every frame while a lead line is sung. An earlier edition counted only frames within 12 dB of the band's loudest frame. In the consonant band these were a few sibilant bursts, 2-30% of the sung frames, so the margins read 4-12 dB too high.
