# Marcar un mail como leído en Gmail

## Context
- App package / Activity where this starts: `com.google.android.gm` (inbox)
- Precondition: inbox with at least one unread row ("No leída" text prefix)

## Steps
1. `u2ctl app start --package com.google.android.gm --serial <SERIAL> --json`
2. `u2ctl ui dump --limit 0 --compact --json` → identify unread rows (text starts "No leída")
3. `u2ctl ui tap --text-contains "<SENDER>" --serial <SERIAL> --json` → open the unread email
4. `u2ctl ui dump --resource-id "com.google.android.gm:id/inside_conversation_unread" --compact --json` → verify header button now says "Marcar como no leída" (i.e. already read)
5. `u2ctl ui press --key back --serial <SERIAL> --json` → return to inbox
6. `u2ctl ui dump --limit 0 --compact --json` → verify "No leída" prefix gone from that sender's row

## Postcondition
The opened email's inbox row no longer starts with "No leída"; header unread button reads "Marcar como no leída".

## Known Pitfalls
- Opening a conversation AUTO-marks it read (Gmail default). There is no separate "Marcar como leída" tap; the header button flips to "Marcar como no leída" immediately on open.
- Unread indicator = "No leída" text prefix on the row FrameLayout (NOT a separate a11y desc).
- Console mangles UTF-8 ("No leída"→"No le\xeDa"); run python reads with PYTHONUTF8=1 to see real strings. Use ASCII-safe sender name for the tap selector.