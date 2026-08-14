# Search for videos on YouTube

## Context
- App package / Activity where this starts: `com.google.android.youtube` (home feed)
- Precondition: YouTube is open on the home screen (bottom nav visible: Inicio/Shorts/Crear/Suscripciones/Tú).

## Steps
inside u2bun (workdir: `u2bun/`)

1. `bun run src/index.ts --serial da0f5e72 app start --package com.google.android.youtube --json`
2. `bun run src/index.ts --serial da0f5e72 ui tap --ref @6 --json`  (top-right search ImageView, content-desc "Buscar")
3. `bun run src/index.ts --serial da0f5e72 ui input --text "<query>" --json`  (EditText is auto-focused)
4. `bun run src/index.ts --serial da0f5e72 ui press --key enter --json`
5. `bun run src/index.ts --serial da0f5e72 ui snapshot --json`  → results under `com.google.android.youtube:id/results`

## Postcondition
- Results RecyclerView shows video cards with content-desc containing "<title>, <channel> - <N> visualizaciones - <time> - reproducir (Short|vídeo)".

## Known Pitfalls
- The search button has empty `text` and `resourceId="menu_item_view"`; its content-desc is "Buscar". Tap it by ref (top-right `@6`) — semantic `--text "Buscar"` won't match.
- After tapping search, the `EditText` ("Buscar en YouTube", `search_edit_text`) is auto-focused, so `ui input` types directly into it without a separate tap.
- `ui input` uses clipboard+paste internally, so accented/special chars type correctly.
