# u2ctl — Functional Shape

How the product behaves from the operator's point of view. This document describes **what** u2ctl does and how it feels to drive it — as a human on the terminal or as an LLM agent over the CLI. It deliberately avoids internal design (that is `PLAN.md` and `BUILDSPEC.md`); everything described here maps 1:1 onto those contracts.

> Typical device used in examples: Xiaomi Mi 9 SE, serial `da0f5e72`, 1080×2340.

Key facts the operator must know up front:

- u2ctl is **stateless per command** — it never remembers you, never runs in the background, never starts a daemon.
- u2ctl does **not** decide anything for you. You (or your agent) choose actions; u2ctl executes them and reports facts.
- Every command returns the **same JSON envelope**; human-readable output is a convenience on top.
- If the device is in a bad state, u2ctl tells you the stable error code and what to do next — it does not hide the problem.

---

## 1. Who uses it, and their journey

### Persona A — Human operator (setup, troubleshooting, ad hoc control)

Quick path:

1. `u2ctl device list` — see what is attached.
2. `u2ctl setup verify` — is this device ready to be controlled?
3. `u2ctl setup install` — if not, provision it (repeatable; safe to run again).
4. `u2ctl setup verify` — confirm.
5. `u2ctl ui dump --filter actionable` — see what is on screen.
6. `u2ctl ui tap --text ...` / `u2ctl app start --package ...` — act.

### Persona B — LLM agent (Claude Code, OpenCode, Codex or a custom agent)

Quick path:

1. `u2ctl tools schema --format openai --json` — get the capability catalog.
2. `u2ctl device list --json` → pick `--serial`.
3. `u2ctl setup verify --json` → provision if needed (`setup install --json`).
4. Loop: `ui.dump --filter actionable` → choose selector → act (`ui.tap`/`ui.input`/`ui.swipe`/`ui.press`) → confirm the returned postcondition.
5. On error codes 2/5: `device reconnect --json`, retry once, else diagnose.

### Persona C — Future recorder (macro author)

Not implemented yet. The functional seams it relies on are already observable:
`ui.dump` returns a `screen_fingerprint`, and every mutation returns the resolved element. A future `macro.record` will be able to capture "fingerprint → tool call → postcondition" without re-instrumenting u2ctl.

---

## 2. Global behavior

### 2.1 Invocation and options

```
u2ctl [--serial SERIAL] [--timeout SECONDS] [--json] [--quiet]
      [--dry-run] [--strict-selector] [--yes] COMMAND [ARGS...]
```

| Option | Effect, functionally |
|---|---|
| `--serial` | Which device to talk to. Required when ADB sees more than one device; with zero devices it is an error either way. |
| `--timeout` | Upper bound for the whole command, in seconds. Default 30. `ui.wait` may clamp up to 120. |
| `--json` | Emit the envelope as JSON to stdout; nothing else on stdout. Diagnostics still go to stderr. |
| `--quiet` | Suppress human diagnostics; keep result on stdout. Never suppresses errors. |
| `--dry-run` | Print the envelope that *would* result, without executing the action. Read tools ignore it. |
| `--strict-selector` | Treat an ambiguous selector match as `SELECTOR_NOT_FOUND` instead of resolving to the first match with a warning. |
| `--yes` | Explicit consent required by destructive commands. Always fails without it. |

### 2.2 Device selection rules

- `--serial` wins over everything.
- Else `U2CTL_SERIAL`, then `ANDROID_SERIAL`.
- Else: exactly one device on ADB → use it; zero devices → `DEVICE_NONE`; two or more → `DEVICE_AMBIGUOUS` (never an implicit pick).

### 2.3 Output channels

- **stdout** carries only the command result (JSON with `--json`, terse human text otherwise).
- **stderr** carries diagnostics, warnings, and one mandatory `[audit]` line per mutation (`[audit] ui.tap device=da0f5e72 text=LinkedIn`).
- A command that fails still exits with a non-zero code; it never prints a Python traceback by default.

### 2.4 Exit codes

| Exit | Means, functionally |
|---:|---|
| 0 | Succeeded; the result satisfies its postcondition where declared. |
| 1 | You asked for something invalid (`USAGE`). |
| 2 | The device layer is wrong: absent, ambiguous, unauthorized, offline, or `adb` missing. |
| 3 | Something to act on was not found: selector or app. |
| 4 | Provisioning or dependency failure (e.g. USB install blocked by the OS). |
| 5 | The operation timed out, or the device state did not reach the expected postcondition. |
| 10 | Unexpected internal failure. |

### 2.5 Success envelope (every command, `--json`)

```json
{
  "schema_version": "1",
  "ok": true,
  "command": "ui.tap",
  "device": "da0f5e72",
  "result": {
    "element": {...},
    "bounds": "[270,1754][450,2058]",
    "postcondition": {"state": "exists", "timeout": 0.4, "satisfied": true}
  },
  "warnings": ["SELECTOR_MATCHED_MULTIPLE matched 3, used first, pass --bounds to disambiguate"]
}
```

### 2.6 Error envelope (every failure, `--json`)

```json
{
  "schema_version": "1",
  "ok": false,
  "command": "device.status",
  "error": {
    "code": "DEVICE_OFFLINE",
    "message": "The selected device is offline.",
    "retryable": true,
    "hint": "Run: u2ctl device reconnect --serial da0f5e72"
  }
}
```

---

## 3. Domain behavior

### 3.1 `device`

| Command | Functionality |
|---|---|
| `device list` | Lists every ADB-visible device: serial, model, transport (USB/Wi-Fi), state (`device`, `offline`, `unauthorized`, `recovery`, `no permissions`). With `--json`, a structured array plus `selected` marking the device that selection rules would pick. |
| `device status` | Health of the selected device: connectivity state, Android version/SDK, screen on/off, current foreground app, transport, and readiness booleans for the uiautomator runtime and the input method. Does **not** mutate anything. |
| `device info` | Hardware/OS facts: model, product, display size and density, manufacturer, serial, SDK, rotation. Static metadata; never errors on screen state. |
| `device reconnect` | Recovery. First tries a soft transit reconnect (`adb reconnect <serial>`). If the device is gone from ADB entirely and `--hard` is given, restarts the local adb server (`kill-server` + `start-server`), which affects *all* attached devices and is therefore destructive — requires `--yes`. Always ends with a fresh `device status` so you can confirm recovery. |

**Functional promise:** after any device-layer failure (exit 2), `device reconnect` either restores a usable device or returns a precise code telling you why it cannot (`DEVICE_UNAUTHORIZED`, `DEVICE_NOT_FOUND`), never a vague error.

### 3.2 `setup`

Setup works in steps, each independently verifiable and idempotent. Running `setup install` twice is a no-op the second time.

| Command | Functionality |
|---|---|
| `setup verify` | Read-only health report: ADB reachable? Device authorized? Android metadata readable? uiautomator runtime responding? Input method installed? Screen usable? Gives an aggregated `status` (`ready` / `not_ready`) plus per-step detail. Never installs or changes state. |
| `setup install` | Makes the device controllable, step by step: (1) ADB connectivity/authorization; (2) device metadata; (3) uiautomator runtime; (4) input method for text entry; (5) only if `--keep-awake` requested, apply stay-awake settings and report them as a reversible step; (6) round-trip check and a harmless UI read. Reports each step as `installed | already_present | skipped | failed`. Partial failure keeps the completed steps and gives the next remediation command. |
| `setup diagnose` | Collects evidence for the problematic step (prop stack, server health, error details, device policy) **without repairing** anything. Its output is meant to be read by the operator or passed to the agent as context. |

**Xiaomi/OS policy promise:** if the OS refuses installs (`INSTALL_FAILED_USER_RESTRICTED`), `setup install` reports `PROVISION_BLOCKED` with the exact enabling setting to flip (Developer options → *Install via USB*) instead of a generic APK failure.

**Safety promise:** `--keep-awake` is the only optional mutation and it is explicit, reported, and reversible. Setup never hides which steps changed the device.

### 3.3 `app`

| Command | Functionality |
|---|---|
| `app current` | The package and activity in the foreground, plus the displayed app label. |
| `app start --package PACKAGE` | Launches the package. Returns the resolved package and foreground package 1 second after launch (the postcondition). Missing package → `APP_NOT_FOUND`. |
| `app stop --package PACKAGE` | Force-stops the package. Returns the previous foreground package and the stop confirmation. |

### 3.4 `ui`

The core control surface. Two kinds of commands: **reflection** (read what is on screen) and **action** (change the screen), with the invariants in §4 enforced throughout.

| Command | Functionality |
|---|---|
| `ui dump` | Returns the actionable elements on screen as an ordered, deduplicated list (see §4.3), plus a `screen_fingerprint` (a stable signature of that screen) and `warnings` about elements collapsed or excluded. `--limit N` caps the list (default 30, `0` = all). `--include-system-bars` adds status/nav chrome. `--raw` returns the full XML instead of the filtered view. |
| `ui tap` | Taps one element matched by `--text`, `--resource-id`, `--description`, or `--bounds X1,Y1-X2,Y2`. Returns the resolved element + the postcondition `exists` after the tap. |
| `ui input --text TEXT` | Types text into the currently focused input field. Returns the field that received it (resolved element) and the text echo. Unicode, spaces, accents and shell-sensitive characters are typed verbatim. |
| `ui swipe --from X1,Y1 --to X2,Y2 [--duration SECONDS]` | Drags from A to B in normalized or pixel coordinates (both accepted, must be unambiguous). Default duration 0.2 s. Returns start/end and a fresh fingerprint after the gesture. |
| `ui press --key KEY` | Fires a key event: `home`, `back`, `recent`, `enter`, `delete`, `dpad_*` etc. `home`/`back` verify the resulting foreground screen via fingerprint. |
| `ui wait --selector SELECTOR [--timeout SECONDS]` | Blocks until the given element is present (or absent with `--absent`) or the timeout expires. Returns the element and the time waited. Timeout → `TIMEOUT`. |

Selector grammar (used anywhere a selector is accepted): `text:...`, `resourceId:...`, `desc:...`, `bounds:...`, class and combined forms are accepted; the dedicated flags are sugar for these.

---

## 4. Functional invariants

### 4.1 Determinism
Same command against the same device state yields the same envelope. Nothing implicit: no random tie-breaks, no hidden retries. Ambiguity is either an error (`--strict-selector`) or an explicit warning (default).

### 4.2 A retry is never silent
u2ctl does not auto-retry invisible to the operator. Transient failures (exit 5, retryable) are reported with `retryable: true`; the operator decides. Only classified transient errors are ever eligible for retry, and never a destructive action unless that action is declaratively idempotent.

### 4.3 "Actionable element" — the shared vocabulary
An element is *actionable* when it is clickable, scrollable, checkable, focused, editable, a known interactive widget (Button, ImageButton, CheckBox, RadioButton, Switch, EditText), or carries visible text up to 200 chars. System status/nav bars are excluded by default. Each actionable element reports: text, resource-id, content-desc, class, bounds, interaction flags, and whether the selector engine considers it visible.

Consistent rule across `ui.dump`, `ui.tap`, `ui.wait`: what you see in `ui.dump` is what you can select.

### 4.4 Resolved element ≠ index
Every mutation returns a *resolved element* (identity + bounds), because raw indexes are a snapshot artifact. Replays and scripts must select by identity (`text`/`resourceId`/`desc`/`bounds`), never by the transient `index`.

### 4.5 The screen fingerprint is the truth
`ui.dump` computes a `screen_fingerprint` over the actionable projection. Any command that changes the screen can return the *new* fingerprint. Comparing fingerprints is the sanctioned way to answer "did the screen reach the expected state?" — the future replay primitive, available today.

### 4.6 Postconditions are checked or admitted
Actions with a declared expected outcome (`text appears`, `element present/absent`, `screen equals fingerprint`) verify it before declaring success. If verification fails, the command still returns its factual result but errors with `POSTCONDITION_FAILED`. A mutation that succeeds without verification is not allowed to exist — it is an audit gap, not a feature.

---

## 5. State and memory model

- u2ctl keeps **no state between commands**. It is a pure function of (command + args + device state).
- The only persisted inputs: optional flat config file (`serial`, `timeout`, `json`, `safety`, etc.) and environment variables. No cache, no telemetry, no history, no daemon.
- The only things it writes to the device are what a command declares: runtime files, the input method, and — for `setup install --keep-awake` — stay-awake settings that are reported and reversible.
- Logs/warnings live on stderr for the lifetime of the command and disappear with it.

---

## 6. Failure behavior, by symptom

| Symptom you hit | What you see | What you should do |
|---|---|---|
| `adb devices` shows nothing | `DEVICE_NONE` (exit 2) | Plug USB or `adb connect 192.168.1.19` (Wi-Fi fallback for this device). |
| Two phones, no `--serial` | `DEVICE_AMBIGUOUS` (exit 2) | Pick one from `device list` and pass `--serial`. |
| RSA prompt pending | `DEVICE_UNAUTHORIZED` (exit 2) | Accept the prompt on the phone screen. |
| Device froze mid-run (MIUI screen-off) | `DEVICE_OFFLINE` / `TRANSIENT` (exit 2/5, retryable) | `device reconnect`; consider `setup install --keep-awake` for long unattended runs. |
| Install refused by Xiaomi | `PROVISION_BLOCKED` (exit 4) | Flip Developer options → *Install via USB*, rerun `setup install`. |
| `ui.tap` matched nothing | `SELECTOR_NOT_FOUND` (exit 3) | `ui.dump --filter actionable` and choose a current selector; the UI may have changed. |
| Tap matched 5 things | Warning `SELECTOR_MATCHED_MULTIPLE` + first match | Pass `--bounds`; or `--strict-selector` if you want a hard error. |
| Package name typo | `APP_NOT_FOUND` (exit 3) | `app current` or check the store listing. |
| Gesture hung | `TIMEOUT` (exit 5, retryable) | Retry with higher `--timeout`, or reconnect first. |
| Tap landed but screen untouched | `POSTCONDITION_FAILED` (exit 5) | Re-dump; target changed or moved. Re-check the selector. |
| Colon in a text when using grammar selector | Parse error `USAGE` (exit 1) | Escape the value, or use `--text` which never parses grammar. |

---

## 7. Scenario walkthroughs (behavioral scenarios)

### S1 — Prepare a fresh device (success)
1. `u2ctl device list` → one row, model `Mi_9_SE`, state `device`, marked selected.
2. `u2ctl setup verify --json` → `{"status": "not_ready", "steps": {"runtime": "missing", "ime": "missing"}}`.
3. `u2ctl setup install --json` → each step `installed`; step 3 succeeded after OS policy was confirmed; final `setup verify` implicit round-trip ok.
4. `u2ctl setup verify --json` → `{"status": "ready"}`.
5. `u2ctl ui dump --filter actionable --limit 10` returns app labels with bounds, `screen_fingerprint: "..."`.

### S2 — Run `setup install` again → idempotent
1. All steps report `already_present`. Exit 0. No device writes performed.

### S3 — Open an app and act
1. `u2ctl app start --package com.android.settings` → `prior`=launcher, `foreground`=settings.
2. `u2ctl ui dump --limit 5` → actionable items, new fingerprint.
3. `u2ctl ui press --key back` → returns to launcher; `screen_fingerprint` again equals the launcher fingerprint from S1.

### S4 — Recover an offline device (the common MIUI case)
1. `u2ctl device status` → `DEVICE_OFFLINE`.
2. `u2ctl device reconnect` → executes soft reconnect; final `status` reports `device` + screen on/off.
3. If screen was off → hint suggests `setup install --keep-awake` for unattended sessions.

### S5 — Agent loop (the product's real calling card)
1. Agent fetches `tools schema --format openai --json`.
2. Agent: `device list --json`; picks `--serial`.
3. Agent: `setup verify --json` → not ready → `setup install` (classified `interactive`, so no `--yes` required).
4. Agent: `ui dump --filter actionable --json`; selects `text:LinkedIn`.
5. Agent: `ui.tap` via `u2ctl ui tap --text LinkedIn --json` → `postcondition.satisfied=true`.
6. Agent hits `TRANSIENT` on a swipe → `device reconnect --json`, retries once, continues.

### S6 — Guarded destructive path
1. `u2ctl device reconnect --hard --json` without `--yes` → `USAGE` explaining the confirmation requirement. Nothing executed.
2. Same command with `--yes` → adb server restarted, all devices re-registered, final status reported.

### S7 — Safety ceiling for an untrusted agent
1. Env `U2CTL_SAFETY=read`.
2. Agent calls `ui.tap` → `USAGE` (locked out before touching the device). `ui.dump`, `device list`, `setup verify` keep working.
3. Human operator raises the ceiling for the session when they want mutation allowed.

---

## 8. Functional acceptance checklist

- [ ] `u2ctl --help` and every `u2ctl <domain> <tool> --help` describe behavior a human can follow without docs.
- [ ] One device → works unnamed; zero → `DEVICE_NONE`; two → `DEVICE_AMBIGUOUS`.
- [ ] `setup install` twice and `setup verify` never mutate more than declared/reversible steps.
- [ ] On the Mi 9 SE: install, dump, tap, input (with accents/unicode), swipe, press, app lifecycle, and reconnect all behave per S1–S6.
- [ ] Every failure returns a stable code (`code`), exit code, and actionable `hint`.
- [ ] No command prints a traceback; stdout carries only the result.
- [ ] `--json` output is byte-stable across runs on the same device state (golden-tested).
- [ ] An external LLM agent can go from `tools schema` to a successful mutation and a successful reconnect using only JSON envelopes.

---

## 9. Relationship to the other docs, and what deliberately does not exist yet

- `PLAN.md` — scope, phases, risks, DoD.
- `BUILDSPEC.md` — the technical contracts that make this behavior deterministic (error catalog, guards, config precedence, selectors).
- **Does not exist yet (by design):** `macro` recording/replay, embedded LLM, multi-device orchestration, a GUI/web inspector, a daemon. The screen fingerprint, resolved-element reporting, and postcondition checks in §4 are the seams those features will use when they arrive.