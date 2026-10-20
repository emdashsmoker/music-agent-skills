# Planning

## Purpose of planning
- Agree on the big decisions with the user before rendering
    + Rendering a whole song and synthesising vocals take time, so a wrong direction is costly
- Summarise what was agreed in the song file's `notes`
    + It becomes the yardstick for later change requests

## Questions
| Item | Default | Remarks |
|---|---|---|
| Genre | Inferred from the request | Offer the closest id from the `genres` list |
| Mood and references | Genre standard | Take only tempo, rhythm, timbre and structure traits from a reference |
| Tempo | The genre's default bpm | Suggest within the range shown by `genres <id>` |
| Key | The genre's first key | With vocals, adjust to the voice's range |
| Length | Genre standard (pop 3-4 min, club 5-8 min) | Present it converted to bars |
| Structure | The genre's standard structure | Present the section list and bar counts as a table |
| Vocals | None | If wanted, ask the vocal questions below |
| Delivery formats | ogg, mp3, MIDI, the song file and the project JSON | wav, flac, stems, LMMS and DAWproject on request |
| Mix style | Balanced, flexible | Where the foreground (the backbeat, the lead, the lead vocal) sits in the track. Forward is a pop or radio mix, vocal puts only the voice and the lead forward, backbeat only the backbeat, balanced is the default, blended a club mix. Offer instrumentals the list without vocal. Adherence is flexible (the style is a starting point, adjusted 1 to 2 dB at a time as the review asks, and changed when another style fits better, with the change reported afterwards), flexible-Human in the Loop (as flexible, but the user is asked before the style changes) or fixed (the foreground parts and the carve stay at the style's values). Record the choice as `mix.style` and in `notes` (Mix styles in `mixing-qa.md`) |
| Loudness target | Genre profile | Reflect a stated purpose such as streaming or club play. For a hot master raise the target by 1 to 2 LU and watch `limiter_p95_db` for overwork |
- Extra questions when there are vocals
    + Engine and voice (show the `voices` list, ask whether the user has a singing voicebank)
    + Language
    + Lyrics : provided by the user, or written from a theme the user gives
    + Preference for gender and range
    + Recognition model for the vocal check (default base) : offer small when the machine has room (4 or more CPU cores, 2 GB or more of free memory), above all for lyrics in another language, where base flags clearly sung lines more often. Medium or larger only when the user asks. Record the choice as the setting `asr_model`; the costs per model are in `vocals.md`
    + Reading speed of a speech voice (default: the agent decides) : three choices. The agent decides: pick one of the other two for each vocal track and record which, and why, in `notes`. Matched to the melody: the voice reads slower under long notes and faster under short ones (0.7 to 1.15), so less has to be stretched and two nasals across words stay apart. Fixed: every line at one pace, 1.0 being the voice's own, recorded as `vocal: {speed: 1.0}`. Deciding, start from matched, which left fewer weak lines in measurements, and fix the speed for a track meant to sound spoken or a track whose lines the vocal check finds weaker matched than fixed (Reading speed in `vocals.md`)
- Ask everything in one batch
    + Offer a default with every item so the user only answers what should change
- If the user leaves it to you, go ahead with the defaults
    + State in the first report which assumptions were made
- If asking is impossible in this environment, go ahead with the defaults and record the assumptions at the top of the report

## Planning summary form
```
Title / genre / tempo / key / length
Structure : intro 8 - verse 16 - chorus 16 - ... (N bars in total, M min S s)
Chords : verse i VI III VII / chorus VI VII i i
Core idea : (one or two lines on the hook, the timbre, the development)
Vocals : engine, voice, range, lyric theme, recognition model, reading speed
Mix : style (balanced), adherence (flexible), loudness target
Deliverables : ogg, mp3, MIDI, song file, project JSON, ...
```
- Show this summary to the user and start composing after it is confirmed
- For a song whose lyrics are newly written, have the lyric draft confirmed as well
    + Read the lyric writing rules in `vocals.md` before drafting, because a draft written first tends to keep its faults

## Handling user input
- Melodies, chords and rhythm ideas from the user go in as given
    + Transcribe them into the syntax and share the `lint` result
    + If there is a harmonic clash, show where and offer alternatives, and ask for a choice
- Lyrics from the user are kept as written in principle
    + Check syllable counts, stress, line-final vowels and rhyme
    + Once the engine and voice are chosen, also check what that voice can sing (sentence structure and words a pronunciation dictionary is unlikely to hold, at the top of the lyric writing rules in `vocals.md`)
    + Present a list of problem lines with suggested changes; where it helps, play solo clips of the original and the change made with `vocal-try`
    + Apply only the changes that are approved
    + If the user keeps the original, follow 'Handling unworkable plans' below
- From a reference song take traits only
    + Do not copy the melody or the lyrics of a specific song
- Given a MIDI file, make a song file draft with `import-midi`, then assign instruments and roles

## Handling unworkable plans
- Examples of requests that would badly hurt quality
    + A tempo far from the genre's conventions (example : gabber at 90 bpm)
    + A melody far outside the voice's range
    + Lyrics that put several syllables on one note, or run syllables shorter than 110 ms
    + Lyrics whose rhyme and syllable count differ from line to line
    + A long structure that repeats the same section with no development
- Order of response
    + Step 1 : explain concretely what the problem is and how the result gets worse
    + Step 2 : offer one or two alternatives that keep the intent (example : lyrics revised only for rhyme)
    + Step 3 : take the user's choice
- Do not fix it on your own and carry on
    + The fixed result may differ from what the user meant
- If the user keeps the original, follow the original
    + State once, clearly, what loss of quality to expect
    + Record the numbers and the limits of that part in the result report
- When a voice or voicebank with usage terms is used
    + If the lyrics or the purpose conflict with the terms, tell the user before proceeding and adjust

## Reporting during the work
- Share briefly at the end of each step
    + When structure and chords are settled
    + The vocal check result (weak lines and candidates)
    + The numbers of the first full render and what was seen in the pictures
- Points that need the user's judgement
    + Changes to lyrics
    + Choosing between candidates for a weak line
    + When an intended effect conflicts with a QA threshold
