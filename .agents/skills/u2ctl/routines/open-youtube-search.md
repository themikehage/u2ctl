# Abrir YouTube y tocar Buscar

## Context
- App package / Activity where this starts: `com.teslacoilsw.launcher` (Nova home)
- Precondition: launcher home screen visible with YouTube icon

## Steps
1. `u2ctl ui tap --text "YouTube" --serial <SERIAL> --json` → screen_changed
2. `u2ctl ui dump --desc-contains "Buscar" --compact --json` → locate search icon (rid `menu_item_view`)
3. `u2ctl ui tap --description "Buscar" --serial <SERIAL> --json` → screen_changed
4. `u2ctl ui dump --text-contains "Buscar" --compact --json` → verify search field visible

## Postcondition
Search screen open: `search_edit_text` with hint "Buscar en YouTube" visible.

## Known Pitfalls
- After step 3 the soft keyboard appears; `--desc-contains "Buscar"` then also matches the IME action key (`com.google.android.inputmethod.latin`). Verify the search bar via the `search_edit_text` resource-id instead.