# Search for videos on YouTube

## Context
- App package / Activity where this starts: `com.google.android.youtube` (home feed)
- Precondition: device unlocked and on the launcher home screen.

## Steps
inside u2bun (workdir: `u2bun/`)

1. Launch YouTube by tapping the launcher "YouTube" icon, then confirm with `ui snapshot`.
   NOTE: `app start --package com.google.android.youtube` returns `APP_NOT_FOUND` even though the
   package appears in `app list`; launch via the launcher icon instead.
2. `bun run src/index.ts --serial <SERIAL> ui snapshot --json`  → confirm home feed (bottom nav: Inicio/Shorts/Crear/Suscripciones/Tú).
3. `bun run src/index.ts --serial <SERIAL> ui tap --text "Buscar" --json`  → opens search screen (search EditText auto-focused)
4. `bun run src/index.ts --serial <SERIAL> ui input --text "<query>" --json`
5. `bun run src/index.ts --serial <SERIAL> ui press --key enter --json`
6. `bun run src/index.ts --serial <SERIAL> ui snapshot --json`  → results list

## Postcondition
- Results show the channel card and video cards with content-desc containing "<title> - <channel> - <N> visualizaciones - <time> - ver vídeo".

## Known Pitfalls
- `app start --package com.google.android.youtube` returns `APP_NOT_FOUND` despite the package being listed in `app list`; tap the launcher icon to open it.
- The search button (top-right) matched by text "Buscar" on the current device; re-snapshot before tapping by ref if the handle shifts.
- After tapping search, the `EditText` ("Buscar en YouTube") is auto-focused, so `ui input` types directly into it without a separate tap.
- `ui input` uses clipboard+paste internally, so accented/special chars type correctly.
- Device serial: `192.168.1.19:5555` (WiFi) — the old `da0f5e72` (USB) no longer applies.
