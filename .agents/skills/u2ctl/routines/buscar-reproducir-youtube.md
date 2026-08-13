# Buscar en YouTube y reproducir el primer resultado

## Context
- App package / Activity where this starts: `com.google.android.youtube`
- Precondition: YouTube home with search bar (`search_edit_text`)

## Steps
1. `u2ctl app start --package com.google.android.youtube --serial <SERIAL> --json`
2. `u2ctl ui tap --resource-id "com.google.android.youtube:id/search_edit_text" --serial <SERIAL> --json`
3. `u2ctl ui input --text "gato" --serial <SERIAL> --json`
4. `u2ctl ui press --key enter --serial <SERIAL> --json` → submit search
5. `u2ctl ui dump --limit 0 --compact --json` → locate first organic result
6. `u2ctl ui tap --desc-contains "<VIDEO TITLE>" --serial <SERIAL> --json` → screen_changed
7. `u2ctl ui wait --desc-contains "segundos" --timeout 15 --serial <SERIAL> --json` → player SeekBar loaded
8. `u2ctl ui press --key back --serial <SERIAL> --json` (×2) → return to results list

## Postcondition
Back at search results: `search_query` shows the term and `com.google.android.youtube:id/results` container present.

## Known Pitfalls
- `enter` submits the search; results render with `com.google.android.youtube:id/results`.
- Player readiness marker = SeekBar desc "N minutos X segundos de N minutos Y segundos" (`--desc-contains "segundos"`); its time advancing proves playback.
- A Short result's player needs TWO `press back` calls to return to results (first back just dismisses overlay/continues; fingerprint keeps changing during playback).
- Sponsored results ("Patrocinado:") come first; skip to the first organic video by title.