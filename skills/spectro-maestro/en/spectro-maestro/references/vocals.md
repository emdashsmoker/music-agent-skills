# Making vocals

## Principles of judgement
- The rules in this file are starting points
    + Some may rest on thin evidence, so when a result looks wrong, observation comes before the rule
- The speech recognition match score is a detector
    + Its job is to pick out lines to listen to
    + Whether a line finally passes is decided by a person listening
- Lyrics and melodies the user wrote or approved are not changed because of a warning alone
    + When a weak line is found, present solo vocal clips of the original and of the candidates together
    + Leave the choice to the user
- The figures in this file are reference values measured in one particular environment
    + When the engine version, the voice or the tempo changes, measure again with `vocal-check`

## Choosing an engine
| Engine | Method | Strengths | Weaknesses |
|---|---|---|---|
| `kokoro` | A speech voice converted to singing | Light to install, clear diction, the same result every time | Timbre stays close to reading aloud, 24 kHz sample rate |
| `piper` | A speech voice converted to singing | Wide choice of voices and languages | Quality varies a lot between voices, 22 kHz sample rate for most voices |
| `diffsinger` | A dedicated singing voicebank | The most natural singing, 44.1 kHz sample rate | The user has to supply the voicebank, rendering is slow |
- See the list of voices with the `voices` command
    + Default female voice : `kokoro` / `af_heart`
    + Default male voice : `kokoro` / `am_michael`
    + Piper voices have different usage terms per dataset, so check the model card of a voice before choosing it and tell the user
- For other languages, name a Kokoro or Piper voice of that language; it sings through the same conversion path
    + Use a multilingual recognition model with `vocal-check --asr-model base` or `small`
- Ask the user about engine and voice in the planning step
    + If the user owns a singing voicebank, suggest `diffsinger` first

## Track settings
```yaml
vox:
  role: vocal
  vocal:
    engine: kokoro
    voice: af_heart
    style: {vibrato_depth: 20, scoop: 0.4}   # optional
    ending_fix: true                         # line-end repair, on by default
  layers:
    - {type: double, sections: [chorus1, chorus2]}
    - {type: harmony, steps: 2, sections: [chorus2]}
  mix: {gain_db: 0, reverb: 0.2}
```
| `style` key | Default | Meaning |
|---|---|---|
| `vibrato_depth` | 28 | Vibrato depth on long notes (cents), 0 switches it off |
| `vibrato_rate`, `vibrato_delay` | 5.6, 0.28 | Vibrato speed (Hz), delay before it starts (seconds) |
| `glide` | 0.07 | Time to move between notes (seconds) |
| `scoop` | 0.6 | How far below the first note of a phrase the pitch starts (semitones) |
| `preparation` | 0.12 | Share of an interval the pitch first moves the other way just before a note change |
| `drift` | 6 | Slow pitch wander (cents) |
| `fall` | 0.35 | How far the pitch sags at the end of a phrase (semitones) |
| `level` | 0.6 | How strongly syllable loudness is evened out (0 to 1) |
| `ring` | 3 | Lift around 3 kHz on vowels (dB); not applied to consonants |
| `consonant_ceiling` | -3 | Largest level of an unvoiced consonant (dB, against the vowel level of its line); only t, s, k above it are turned down, by at most 6 dB |
| `formant` | 0 | Formant shift (semitones); positive gives a thinner, brighter timbre |
| `breath` | 0 | Share of breath noise (0 to 1) |
| `vowel_body` | 0 | Fills held ee vowels (he, she, we, see) with the 300-1300 Hz body of the line's other vowels (at most 10 dB) and thins their hiss; 1 is the full fill. The vowel colour moves a little toward ih, so listen |
- Layers
    + `double` : the same melody sung once more on each side (separate takes with slight pitch and timing differences)
    + `harmony` : a harmony `steps` scale steps above or below; notes that clash with the chord are moved to chord tones
    + Limit where they apply with `sections`; the default practice is harmonies in the chorus only
    + Options : `gain_db`, `pan`, `detune` (cents), `delay_ms`

## Lyric writing rules
- Before writing, check the strengths and weaknesses of the chosen engine and voice
    + The kind of engine (speech voice or singing voicebank) and the language decide which rules in the table below apply
    + Choose the words and the sentence structure to fit those rules from the start (changing words after the lyrics are finished means fitting meaning and rhyme again)
- Where the rules are silent, review the lines from several seats as well, such as a lyricist (e.g. meaning, imagery, rhyme), a singer (e.g. where to breathe, notes that follow the natural rhythm of the words), a listener (e.g. whether the words come through and stick on first hearing), a sound engineer (e.g. bands shared with the backing, places where the lead collides) and an agent operator (e.g. whether the limits of the tools the skill relies on, such as TTS, DiffSinger and the mixer, were taken into account); note the reason in `notes` for any choice that departs from the rules
- Sentence structure
    + Pick a word order that keeps weak function words (to, the, a) off beats and long notes
    + Recast a sentence that opens with function words or stacks them in a row so that a content word leads
    + A speech voice reads to with a weak vowel, so it sinks on a beat or a long note (see 'Reduced vowels and weak function words' below)
- Words a pronunciation dictionary is unlikely to hold (proper nouns, invented words, abbreviations, foreign words)
    + A speech voice guesses their pronunciation from the spelling, so it may read them differently than intended
    + A singing voicebank sings an English word missing from its dictionary with a guessed pronunciation, and in other languages it stops at such a word
    + Write numbers and symbols out as the words to be sung
    + For a word the song needs, write the line containing it first and listen with `vocal-try`; if it is misread, give that line a `phonemes` entry
- Lyrics from the user
    + Review them by the measures above before they are sung, and present the problem lines with suggested changes
    + Apply only approved changes; if the user keeps the original, follow 'Handling unworkable plans' in `planning.md`: state the expected loss of quality once, then go on with the original

| Rules | For | What they cover |
|---|---|---|
| Singing craft | Any voice, a human singer included | Stress on the strong beats, 110 ms or more per syllable, open vowels or nasals on held notes, reduced vowels and weak function words off the beats |
| Model-voice habits | Speech voices and singing voicebanks alike | Consonants blur under about 200 ms, consonant clusters need room, bright consonants spit and peak |
| Speech-voice repairs | Speech voices only | The thin held ee and `vowel_body`, `consonant_ceiling` for stinging consonants, the line-ending repair, the strong-form spelling |
- Rules for a voicebank
    + Write by the singing craft and the model-voice habits, and read the speech-voice repairs as background
    + `lint` runs the first two groups on DiffSinger tracks as well
- Order of writing
    + Fix the rhythm of the melody first
    + Write the lyrics so that stressed syllables fall on the strong beats of that rhythm
    + Check syllable counts and stress with `lint`, then revise
- Line length
    + A line is about two bars; leave a rest of at least half a beat between lines
    + Without a rest the last note of one line and the first consonant of the next overlap (`lyrics.no_breath`)
- Syllables match notes
    + One syllable per note
    + The engine's syllable count is the reference, so follow the per-word counts shown by `lint`
    + To sing one syllable on several notes, join the notes with `~` (example : `E4:1~D4:1` sings one syllable bending from E4 to D4)
- Last syllable on a long note
    + On notes held for two beats or more, place words that end in an open vowel or a nasal (day, go, flame, burn)
    + Words ending in a plosive or fricative have their tail cut off on a long note (`lyrics.long_note_ending`)
- Stress
    + Put the stressed syllable of a multi-syllable word on the stronger beat (`lyrics.stress`)
    + Order of beat strength : first beat, third beat, second and fourth beat, the off-beat eighth, sixteenth positions
- Note length
    + One syllable needs 110 ms or more (`lyrics.short_notes`)
    + In fast songs avoid syllables shorter than an eighth note
- Words with an unstable syllable count
    + Words in which a weak vowel follows a diphthong, such as fire, hour, higher, dial, are one or two syllables depending on the engine (`lyrics.unstable_word`)
    + Put them on one long note or split them over two notes, and check with `lint`
- Position of rests
    + Do not put a rest in the middle of a word (`lyrics.rest_in_word`)
- Rhyme
    + `lint` lists the line-end sounds (`lyrics.rhymes`), so check that the intended pairs match
- Bright consonants
    + Carry a line on voiced consonants (m, n, l, d, b, g, w, r) and open vowels
    + Use t, k, p, s, z and sh as seasoning, about one per word and none right before a held note
    + On the speech voices those sounds spit and hiss, and their bursts peak up to 13 dB above the vowel body with a metallic edge
    + A line built on them pokes out of the mix and reaches the limiter first
    + `lyrics.bright_consonants` warns at three bright sounds in five syllables (a cluster such as st or sk counts twice) or at three bright syllables in a row
- Held ee vowels (speech voices only)
    + A speech voice stretched onto a note sings a held ee (he, she, we, see, me, be, free) thin, because the spoken vowel has little body and the stretch keeps it so
    + The word sits under its neighbours, and what is left rings metallic: quiet and sharp at once (in seven songs with Kokoro voices, the body band of an ee syllable sat 9 dB under its line)
    + Keep ee words on short notes and put open vowels (ah, oh, oo, ay) on held notes (`lyrics.held_ee`), or fill the vowel with `style: {vowel_body: 1}`
    + `vowel_body: 1` on 24 lines raised the median ee body from 8.8 to 6.4 dB under the line and left the match scores unchanged
    + A singing voicebank shapes the vowel itself, so this rule and `lyrics.held_ee` do not apply to it
- Reduced vowels and weak function words (any voice)
    + Weak function words (to, the, a) go quiet on long notes: the vowel is reduced in speech, and a singer has to open it on purpose
    + Reduced vowels (the schwa of the, to, a and the first syllable of upon, about) and the short ɪ of it, its, sit have almost no vowel to hold
    + A schwa held for half a second came out 18-22 dB under its line, and "the" sang as breath
    + Give these words short off-beat notes and let a content word take the beat (`lyrics.reduced_vowel_on_beat`, `lyrics.short_vowel_on_beat`, `lyrics.weak_word_on_long_note`)
- Strong-form spelling (speech voices only)
    + When a weak function word must sit on a held note, spell its strong form for the voice: too for to, thee for the, ay for a
    + A singer holds the strong form anyway, and the voice then speaks a full vowel
    + Check that the respelling keeps the meaning, and keep the ordinary spelling in the lyrics file
- Function words on short off-beats (any voice)
    + A function word on a short off-beat note can still blur (on a Kokoro `am_michael` song at 134 bpm, listening found the to of "to every" and the could of "could ever" blurred)
    + The match score and `ROUGH` rarely catch this fault, so reduce it while writing the lyrics (see 'Known limits' below)
    + Rewrite a line flagged `lyrics.weak_words_in_a_row` only when a content-word phrasing keeps the meaning and the rhyme; for the user's lyrics, propose the rewrite
    + If no such phrasing exists, keep the warning and judge the line by ear (see 'Checking procedure' below)

## Patterns that weaken intelligibility
| Pattern | Observed example | Remedy |
|---|---|---|
| Consonants crowded onto short notes | "fields of snow" on one-beat notes at 128 bpm, "only snow" on eighth notes at 156 bpm | Lengthen the notes or use a word with fewer consonants (hills of snow) |
| A run of fast syllables | A whole verse in eighth notes at 156 bpm | Rewrite the rhythm as one syllable per beat |
| Weak function words in a row, or opening the line (`lyrics.weak_words_in_a_row`, `lyrics.weak_opening`) | come what may | Replace with a phrase that includes a content word (anyway) |
| A weak syllable at the head of a line | someone is singing | Put a word that starts with a strong consonant first (voices are singing) |
| A plosive after a long note | hold the light | Replace with a word ending in an open vowel or a nasal |
| Several t, s, z sounds in one line (spit, peaks, a metallic edge) | tests at last | Spread them out or use words with voiced consonants (m, n, l, d) |
| A held ee word on a speech voice (thin, rings metallic) | we will see | Move it to a short note or use a word with an open vowel |
| A word with an unstable syllable count | fire, hour | Change the note layout or use another word |
| A melody outside the voice's range | A line where only breath is left on the low notes | Move the key or the octave |
- This table is a list of risk factors
    + Lines of these patterns are often fine, depending on voice and melody
    + Whether a line is weak is established with `vocal-check`
- The same lyric gives different results in different voices
    + A line that is weak in one voice may be fine in another, so check again after changing the voice
- Remedies are conditional
    + Apply them only to lines confirmed as weak
    + Applied in advance to sound lines, they only make the lyrics awkward
- A yardstick for fast tempos
    + Once a syllable is shorter than about 200 ms, consonants start to blur even with a dedicated singing voicebank (`lyrics.fast_syllables`)
    + At 150 bpm and above avoid runs of eighth-note syllables and start from one syllable per beat

## Checking procedure
- Step 1 : render the vocal alone before mixing
    + `python scripts/studio.py vocal-check song.yaml`
    + Prints the recognised text, the match score and the pitch error (cents) for every line
    + Syllables whose vowel was sung as noise or is barely audible are printed with a `ROUGH` mark (speech voice engines)
    + For lines with a match below 0.85 or a `ROUGH` mark, a picture and a solo clip are saved in the `vocals/` folder
- The match score and `ROUGH` catch different faults
    + Match score : lines whose words are heard differently
    + `ROUGH` : syllables that are understood but grate (a vowel dragged out as breath, a swallowed syllable)
    + `ROUGH` can appear on a line with a match of 1.00, so check both
- Step 2 : look at the pictures of weak lines
    + Upper picture : check that horizontal stripes (harmonics) run to the end of each vowel; a smear instead of stripes means a whisper
    + Lower picture : check that the pitch curve lies on the note bars
    + Check that the syllable marker lines agree with where the sound really starts
- Step 3 : compare candidates
    + Prepare three to five alternatives with the same number of syllables
    + `python scripts/studio.py vocal-try song.yaml --line 13 --text "over hills of snow" --text "over miles of snow"`
    + Each candidate takes a few seconds and is printed with its match score and a solo clip
- Step 4 : choose
    + For lyrics the user wrote, present the original and the candidate clips and let the user choose
    + For lyrics you wrote, take the candidate that harms neither the meaning nor the rhyme
- Handling `ROUGH` syllables
    + If the picture shows a smear instead of stripes at that syllable, it is a real fault
    + Lengthen the note, use a word with fewer consonants around the syllable, or change the voice, then check again
    + A mark caused by consonants taking up most of a short note may be left as it is
- When consonants sting or are buried
    + If the listening comment is that the t or s of a certain word stings, lower it with `style: {consonant_ceiling: -6}` and confirm with `vocal-check` that the match holds
    + If consonants are buried and the words cannot be heard, raise it to `consonant_ceiling: 0`
- Faults that neither recognition nor the marks catch
    + A trembling or crackling line end and an over-strong syllable do not show in the match score or in `ROUGH`
    + A blurred short function word is also hard to catch with the match score or `ROUGH` (see 'Known limits' below)
    + Suspect them when the harmonic stripes at a line end blur into a smear in the picture, or when the level goes up and down
    + The final verdict is by ear, so ask the user to listen to the line ends and to lines that keep a `lyrics.weak_words_in_a_row` warning (the listening list in the report)
    + After any change to the way vocals are processed, check line ends and long notes again as well as the places that were fixed
- Cautions in reading recognition results
    + If the last note of the previous line leaks into the clip, the first word may come out different
    + When the recogniser repeats one letter on a long held note, the repeat counts as one letter in the score
    + Proper nouns and rare words are recognised poorly regardless of the singing

## How a speech voice is turned into singing
- Order of conversion
    + The engine reads one line of lyrics aloud
    + The reading is split into pitch, timbre and breath components
    + The timeline is laid out again so that vowel onsets fall on the beat; consonants are sent ahead of the beat
    + Only the most stable and brightest instant of a vowel is stretched to fill a long note; breath and closures are never stretched
    + If there is no voice where the engine says the vowel is, the truly voiced stretch is found inside the same syllable and the boundary is moved
    + A vowel that was read in a whisper is synthesised again as a voiced sound, and the amount of breath in vowels is capped
    + The end of a syllable after the stretched part is kept from exceeding the usual vowel level of its line (prevents a syllable end from popping out)
    + For the last syllable of a phrase that ends in a consonant, the reading's fade-out is used as it is, but its level curve is smoothed so that it only ever goes down (prevents the creak at the end of speech from being heard as a tremble)
    + The pitch is replaced with a sung curve and the sound is synthesised again
    + Unvoiced consonants are taken unchanged from the original recording to keep them crisp
    + A t, s or k that was read louder than the vowels is turned down to `consonant_ceiling` (a level that is natural in speech stings in singing)
- Correcting the engine's timing information
    + The phone times the engine reports are later than the actual sound
    + The delay is measured by observing sibilant and voicing boundaries in all lines of the song; no fixed value is used
    + The delay is inversely proportional to reading speed, so it is converted by each line's speed before it is applied
    + The gap reported between words is in reality occupied by the neighbouring sounds, so it is divided by a ratio measured per engine
- Reading speed
    + The engine is made to read slower for long notes and faster for short ones, which reduces how much has to be stretched
    + It can be fixed with `vocal: {speed: 0.9}`

## Line-end repair
- Background
    + A speech voice lets the last word of a sentence trail off
    + In lines that end in a close vowel, such as me, sea, you, the last note easily becomes a whisper
- The first measure is always applied
    + The blurred tail of the reading is cut away and the long note is filled from the stable part of the vowel only
- The second measure is decided automatically per line
    + It triggers when the held instant of the last vowel is unvoiced, or its periodicity is below 0.5, or it is 9 dB or more quieter than the other vowels
    + A short word (in English, but) is appended to the line and the line is read once more, which makes the original last word mid-sentence and therefore clear
    + The new reading is joined at the start of the last syllable with a short crossfade
    + Its level is matched to that of the syllable before
- Safeguards
    + If appending the word changes the pronunciation of the original line, the repair is abandoned
    + It does not trigger in languages with no registered carrier word (registered : en, de, es, fr, it, pt, nl)
    + The result is cached per line
- The mark `ending resung` in the `vocal-check` output shows whether it triggered
- It can be switched off with `ending_fix: false`

## Connection to the mix
- Vocal against backing is checked separately in two bands
    + 300-3400 Hz (body) : the vocal must be 0-12 dB above the backing (`vocal_body_db`)
    + 1.3-5 kHz (consonants) : the vocal must be at least 2 dB above the backing (`vocal_consonant_db`)
    + The consonant-band figure is also reported per section, so a vocal that is buried only in the chorus can be found
- Act on the backing first
    + Reduce lead and pad during vocal passages, or clear their register
    + Take more of the consonant band out of the backing with `master.vocal_carve`
- Vocal reverb and delay do not receive the kick sidechain
    + A tail that is cut on every beat makes the vocal sound chopped up
- After changing the voice, check the mix numbers again
    + Each voice has a different spectral centre, so the same settings bury it to a different degree

## DiffSinger voicebanks
- Only voicebanks the user provides are used
    + Give `voice` a folder path, an archive path, or a repository address the user handed over
    + Do not search for a voicebank or download one on the user's behalf
- Check before use
    + `python scripts/studio.py diffsinger-inspect <path>`
    + Prints speakers, languages, the models included, and the list of files that state usage terms
    + Read those files and the terms on the distribution page and give the user a summary (commercial use, required credit, prohibited content, limits on use of the output)
    + If the lyrics or the purpose conflict with the terms, discuss it with the user before proceeding
- Settings
```yaml
vocal:
  engine: diffsinger
  voice: /path/to/voicebank
  lang: en              # a language code the voicebank supports
  speaker: normal       # optional; can be mixed as {normal: 0.7, soft: 0.3}
  steps: 20             # sampling steps of the timbre model; higher is slower and finer
  pitch: model          # model is the voicebank's pitch model, curve is the built-in pitch curve
  gender: 0             # timbre shift (-1 to 1)
  breathiness: 0        # more or less breath (dB)
  tension: 0            # more or less tension
```
- Speakers and timbre
    + With several speakers, a clear one and a soft one differ in intelligibility
    + A dark voice easily lacks consonant-band energy in the mix, so look at `vocal_consonant_db` and set EQ around 3 kHz and level separately for each voice
- Range
    + Every voicebank has its own comfortable range
    + Too low or too high, breath increases and the pitch error grows
    + If lines with a `vocal-check` pitch error above 25 cents cluster, move the melody (the part's `octave` or `transpose`)
- Pronunciation
    + Words missing from the voicebank's dictionary are filled in from a general pronouncing dictionary and a grapheme-to-phoneme converter
    + A syllable group starts at its vowel, and the first consonant of the next syllable sits at the end of the previous note
- Reproducibility
    + Every line starts from the same seed, so the same input gives the same sound
    + A double is a separate take with a different seed and timbre
- Render time
    + About 10 seconds per line (on a 2-core CPU); results are cached and reused on re-render

## Known limits
- The speech voice path inherits the timbre of reading aloud
    + Belting, falsetto and rough phonation cannot be expressed
    + More than an octave away from the speaking pitch the timbre turns thin or muddy
- The recognition match is most trustworthy in English
    + For other languages trust it only as far as the multilingual recognition model is accurate
- Fast rap and runs of sixteenth-note singing blur the syllables
- The stress check runs only for speech voice engines
    + Voicebank dictionaries carry no stress marks, so DiffSinger tracks get the syllable count, pronunciation and the other checks of the singing craft and the model-voice habits
- A blurred short function word (to, could and the like) is hard to catch with the match score
    + The score compares the characters of the whole line, so it stays high even when one short word drops out entirely (a 31-character line heard without its to scores 0.95)
    + The recogniser often fills in a function word from the words around it
    + Reduce it while writing the lyrics, and judge the lines that keep it by ear
