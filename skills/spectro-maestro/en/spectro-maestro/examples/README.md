# Example songs

## Songs
| Folder | Song | Genre | Vocal | Length |
|---|---|---|---|---|
| `first_light/` | First Light | Uplifting trance, 138 bpm, F# minor | none | 7:16 |
| `signal_fires/` | Signal Fires | Futurepop, 128 bpm, A minor | Kokoro `af_heart` | 3:50 |
| `last_tram/` | Last Tram | Doomer, 156 bpm, E minor | Kokoro `am_michael` | 3:04 |
| `silver_box/` | Silver Box | Acid house, 124 bpm, G minor | none | 4:12 |
- Each folder has the song file (`.yaml`) and MIDI
    + Vocal songs include the lyrics (`lyrics.txt`)
- No audio is included; rendering a song file produces the same sound
- Every instrument sound is synthesised by this skill; no samples are used

## Rendering them again
- Put the output folder outside the skill
    + `python scripts/studio.py render examples/silver_box/silver_box.yaml -o <working folder>/silver_box_out`
- Vocal songs need the vocal packages and the Kokoro model
- The same song file gives the same sound

## Copyright and licence
- Music, lyrics and song files : Copyright (C) 2026 Em Dash Smoker
- Provided under AGPL-3.0-or-later as part of this skill (`../LICENSE`)
- The vocals of Signal Fires and Last Tram are synthesised with the Kokoro-82M voice model (Apache-2.0) when rendered
- Full notices are in `../THIRD-PARTY-NOTICES.md`
