# Genre library

## How to use it
- List : `python scripts/studio.py genres`
- Read a genre's conventions : `python scripts/studio.py genres uplifting_trance`
    + The conventions are described in the order rhythm, bass, harmony, melody, arrangement, mix
    + Always read them before composing
- Create a starter song : `python scripts/studio.py new futurepop -o song.yaml --title "..." --bpm 128 --key "A minor"`
    + A complete song file with the genre's standard instruments, patterns and structure
    + Chords and melodies are written in Roman numerals and scale degrees, so it works in any key
- A starter is a starting point
    + Delivered as it is, every song would be the same, so rewrite melody, progression, structure and fills to fit the plan
    + Extend the length to the plan by adding sections
- The `genre` value of the song file decides the mix profile and the QA thresholds
    + Set `genre` even when writing from scratch without a starter

## Genres included
| Family | Genre id (default bpm) |
|---|---|
| House | house (124), deep_house (120), tech_house (126), progressive_house (126), acid_house (122), electro_house (128), big_room (128), disco (118), uk_garage (132) |
| Techno | techno (132), acid_techno (140), dub_techno (122), industrial_techno (142) |
| Trance | trance (138), uplifting_trance (138), psytrance (145), dark_psy (150), eurodance (138) |
| Breakbeat | breakbeat (132), big_beat (126), dnb (174), liquid_dnb (174), neurofunk (174), jungle (165) |
| Bass music | dubstep (140), future_bass (150) |
| Hardcore | gabber (180), hardstyle (150), happy_hardcore (170) |
| Industrial | ebm (120), industrial (110) |
| Pop | synthpop (118), futurepop (128) |
| Retro | synthwave (100), darksynth (115), italo_disco (120), electro (128), doomer (156), chiptune (150), vaporwave (80) |
| Hip hop | hiphop (90), lofi_hiphop (78), trap (140), trip_hop (84) |
| Experimental | idm (140), ambient (70) |
| Orchestral support | cinematic (110) |

## Genres not in the list
- Start from the closest genre
    + Pick the genre whose tempo, drum pattern and bass approach are most alike
    + Create that genre's starter, then change the elements that differ
- For a request that mixes two genres, choose one as the skeleton and lay the other's characteristic elements on top
    + Skeleton : drums, bass and tempo
    + Laid on top : lead timbre, harmony, structure
- Do not guess conventions you do not know
    + Ask the user for a reference song or for the traits
    + Where web search is allowed, look up tempo, rhythm, signature timbres and structure before proceeding

## Structure of a genre file
```yaml
name: Futurepop
family: pop
summary: one-line summary
bpm: [122, 136, 128]          # minimum, maximum, default
keys: [A minor, D minor]      # commonly used keys
about: |                      # description of the genre's conventions
  Rhythm: ...
profile:                      # mix profile
  master: {lufs: -9.5}
  roles: {pad: {duck: -6}, vocal: {reverb: 0.2}}
  returns: {reverb: {decay: 2.4}}
  buses: {music: [{fx: lofi, wow: 0.25}]}
  qa: {slope_db_per_octave: [-5.5, -0.7]}
song:                         # starter song (same syntax as a song file)
  chords: {...}
  tracks: {...}
  sections: [...]
```
- With a parent genre given as `extends: house`, only the differences need to be written
- To add a genre, add a file of the same structure to `assets/genres/`
    + Afterwards create a starter with `new` and verify it with `lint` and `render`
