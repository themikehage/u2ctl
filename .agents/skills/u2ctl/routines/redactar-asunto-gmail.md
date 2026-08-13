# Redactar correo en Gmail y escribir asunto

## Context
- App package / Activity where this starts: `com.google.android.gm`
- Precondition: Gmail inbox visible (start via `app start --package com.google.android.gm`)

## Steps
1. `u2ctl app start --package com.google.android.gm --serial <SERIAL> --json`
2. `u2ctl ui dump --text-contains "Redactar" --compact --json` → locate compose FAB
3. `u2ctl ui tap --text-contains "Redactar" --serial <SERIAL> --json` → screen_changed
4. `u2ctl ui tap --resource-id "com.google.android.gm:id/subject" --serial <SERIAL> --json` → focus subject field
5. `u2ctl ui input --text "Prueba asunto u2ctl" --serial <SERIAL> --json` → text_typed
6. `u2ctl ui dump --resource-id "com.google.android.gm:id/subject" --compact --json` → verify text in field

## Postcondition
Compose subject field (`subject`) shows typed text and `focused: true`.

## Known Pitfalls
- `ui dump` without filter returns system windows (notification shade, Gboard IME keys) ahead of app elements; always filter by `--resource-id` or `--text-contains`/`--desc-contains`.
- Compose FAB selector: use `--text-contains "Redactar"` (matches both text and contentDesc of `compose_button`).