# Reaccionar a un post de Facebook

## Context
- App package / Activity where this starts: `com.facebook.katana` (home feed)
- Precondition: feed visible with a post whose action row is on screen

## Steps
1. `u2ctl app start --package com.facebook.katana --serial <SERIAL> --json`
2. `u2ctl ui dump --limit 0 --compact --json` → find post action row
3. `u2ctl ui swipe --from-pos "540,1800" --to-pos "540,600" --serial <SERIAL> --json` → if like button below fold
4. `u2ctl ui long-press --desc-contains "Me gusta" --serial <SERIAL> --json` → screen_changed (reaction picker opens)
5. `u2ctl ui tap --description "Me encanta" --serial <SERIAL> --json` → pick a reaction
6. `u2ctl ui dump --limit 0 --compact --json` → verify reaction desc changed

## Postcondition
Like button content-desc changes to `Botón "<Reacción>" pulsado...` (e.g. `Botón "Me encanta" pulsado`).

## Known Pitfalls
- Post action row is below the fold (photo/video area has no a11y nodes); swipe up first.
- `desc-contains "Me gusta"` may also match a COMMENT's like button (`...reaccionar al comentario`) — verify bounds are in the post action row, not a comment.
- Reaction picker exposes reaction names as content-desc (Me gusta, Me encanta, Me importa, Me divierte, Me asombra, Me entristece, Me enfada) + Cancelar. Tap by exact `--description`.
- A first-run data-consent dialog ("Elige si podemos tratar tus datos...") may block the feed; tap "Empezar" to dismiss.