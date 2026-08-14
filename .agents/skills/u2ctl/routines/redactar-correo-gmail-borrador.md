# Redactar correo completo en Gmail (asunto + cuerpo) y dejarlo en borrador

## Context
- App package / Activity where this starts: `com.google.android.gm`
- Precondition: Gmail inbox visible (start via `app start --package com.google.android.gm`)

## Steps
1. `u2ctl app start --package com.google.android.gm --json`
2. `u2ctl ui tap --text-contains "Redactar" --json` → opens compose screen
3. `u2ctl ui type --resource-id "com.google.android.gm:id/subject" --text "<ASUNTO>" --json` → focus + type subject
4. `u2ctl ui type --resource-id "editor" --text "<CUERPO>" --json` → focus + type body
5. `u2ctl ui dump --resource-id "com.google.android.gm:id/subject" --compact --json` → verify subject
6. `u2ctl ui dump --resource-id "editor" --compact --json` → verify body

## Postcondition
Compose screen open with subject (`com.google.android.gm:id/subject`) and body (`editor`) showing typed text. Do NOT tap `com.google.android.gm:id/send` ("Enviar"); leave screen open so Gmail autosaves the draft.

## Known Pitfalls
- Compose FAB selector: `--text-contains "Redactar"` (matches text + contentDesc of `compose_button`).
- Body editor resource_id is `editor` (a WebView, clickable:false); `ui.type` taps bounds and types anyway.
- Device can go offline mid-task (`DEVICE_NONE`); `u2ctl device reconnect` is blocked by safety ceiling, so use raw `adb reconnect offline` instead.
