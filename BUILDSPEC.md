# u2ctl Build Specification

Companion to `PLAN.md`. PLAN.md decides *why* and *how much*; this document pins the concrete contracts so implementation proceeds without reopening design decisions. Where this document and PLAN.md disagree, **this document wins** and PLAN.md must be updated.

The numbering G1–G12 matches the identified gaps.

## Map to PLAN phases

| Gap | Decides | Feeds phase |
|---|---|---|
| G1 | Registry → CLI binding | 2 (registry) |
| G2 | ToolSpec shape + handler contract | 2 |
| G3 | "Actionable" projection definition | 3 (ui) |
| G4 | Selector ambiguity policy | 3 |
| G5 | Canonical error catalog | 0/1 |
| G6 | Postcondition mechanism | 3 |
| G7 | Guardrail enforcement | 0 (CLI) |
| G8 | Config precedence + env names | 0 |
| G9 | Dependency and tooling inventory | 0 |
| G10 | Test harness and CI | 0/4 |
| G11 | Windows/MSYS operations | 0/1 |
| G12 | Forward-compat with the `macro` domain | 3 (design only) |

---

## G1. Registry → CLI binding

**Decision: the CLI is generated from the registry.** A developer never edits argparse for a tool. Adding a capability = adding a `ToolSpec` in a domain module and registering the domain. Nothing else.

**Extension contract (the only way to add a capability):**

1. Create `src/u2ctl/domains/<name>.py`.
2. Define `DOMAIN = DomainSpec(name="<name>", description="...", tools=[ToolSpec(...), ...])`.
3. Append `DOMAIN` to `DOMAINS` in `src/u2ctl/domains/__init__.py`.

At startup the CLI reads `DOMAINS`, builds `u2ctl <domain> <tool>` subcommands, and validates the whole registry (G2 checks). A contract test asserts every registered tool is reachable through the parser and vice versa.

**Argument generation from `input_schema`:**

| JSON Schema property | CLI mapping |
|---|---|
| Required | Positional argument (`u2ctl ui tap --text` sugar below; e.g. `ui.swipe requires from/to`) |
| Optional | `--kebab-case` flag |
| `type: boolean` | `--flag` / `--no-flag` |
| `enum` | `choices=[...]` |
| `type: array` | `nargs="+"` |
| Integer/string/number | Coerced to the declared type |

Datetime/currency-free. No nested objects as flat CLI args; nested data goes through the `--json-input` argument (a file path or inline JSON string) on the rare tool that needs it.

`tools list`, `tools show`, and `tools schema` print the *same* schemas the parser was built from — they cannot drift.

---

## G2. ToolSpec shape + handler contract

**Decision: JSON Schema (draft 2020-12) is the only schema language. Validation uses `jsonschema` at registration time and at runtime. Internal models use std-lib `dataclasses`. No pydantic.**

```python
ToolSpec(
    name="ui.tap",
    domain="ui",
    description="Tap one visible UI element using a validated selector.",
    input_schema={
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Exact visible text."},
        },
        "oneOf": [
            {"required": ["text"]},
            {"required": ["resource_id"]},
            {"required": ["description"]},
            {"required": ["bounds"]},
        ],
        "additionalProperties": False,
    },
    output_schema={"type": "object", "required": ["element", "bounds"]},
    handler=ui_tap,
    safety="interactive",
    idempotent=False,
    requires=["device.connected", "runtime.uiautomator.ready"],
    expect={"element": None},
)
```

**Handler contract — fixed signature:**

```python
def ui_tap(ctx: HandlerContext, args: dict) -> dict:
    ...
```

- `ctx` exposes: `ctx.device` (device handle), `ctx.serial`, `ctx.timeout`, `ctx.warn(msg)`, `ctx.output` (append structured warnings), `ctx.call_tool(name, **kw)` (intra-command delegation, enables future `macro` without new plumbing), `ctx.client` (low-level adapter, kept private to the runtime package).
- `args` is a validated, coerced dict (strings coerced per schema type). Handlers never parse CLI strings.
- Handlers return a plain `dict` that must validate against `output_schema`.
- Handlers raise typed errors from `src/u2ctl/errors.py` (G5). They never return error payloads; the CLI layer converts exceptions into the error envelope.

**Registration-time validation (fails at startup, not at runtime):**

- name is `domain.tool`, domain matches the module's `DOMAIN.name`.
- No duplicate names across domains.
- `input_schema`/`output_schema` are syntactically valid JSON Schema.
- Handler is callable; safety is one of `read|interactive|destructive`; `requires` entries are known capability keys.
- Mutation tools (`safety in {interactive, destructive}`) declare an `expect` (G6).

---

## G3. "Actionable" projection

**Decision: the canonical definition, used by both `ui.dump --filter actionable` and future replay state assertions.**

A node from the dump is **actionable** iff **any** of:

- `clickable=true` or `scrollable=true` or `checkable=true` or `focused=true`; or
- `editable=true`; or
- `className` in `{Button, ImageButton, CheckBox, RadioButton, Switch, EditText}`; or
- non‑empty `text` of length ≤ 200 and not a system-inset node.

**Exclusion rule (system chrome):** by default drop nodes whose `resource-id` starts with `com.android.systemui` or whose bounds intersect the top status-bar inset (y < status height) or bottom nav inset (y > display height − nav height). Re-enabled with `--include-system-bars`.

**Dedup:** group by `(text, resource-id, content-desc, className, bounds)` where bounds must overlap ≥ 90% of the smaller rect. First occurrence in document order wins; count of collapsed duplicates returned as `duplicates`.

**Ordering:** document order from the dump, after filters.

**Element record emitted per node:**

```json
{
  "index": 12,
  "text": "LinkedIn",
  "resourceId": "",
  "contentDesc": "",
  "className": "android.widget.TextView",
  "bounds": "[270,1754][450,2058]",
  "clickable": false,
  "scrollable": false,
  "focused": false,
  "visible_to_selector_engine": true
}
```

- `index` is scoped to the *filtered view* and is **transitional** — never stored for replay. Present so the agent has a handle; the 2-second watcher (G4) and `screen_fingerprint` are the durable hooks.
- `visible_to_selector_engine` reflects the known divergence between `dump_hierarchy()` and the selector engine (G4); `false` means "use bounds".
- Default `--limit 30`; `--limit 0` means unlimited. Also `--raw` to emit the full XML dump (escape hatch, not the default agent path).

**`screen_fingerprint`** (included in every `ui.dump`): a stable string = sorted, hashed list of `(resourceId, text, contentDesc, className, bounds)` for the actionable projection. Used by G12 replay to assert "same screen".

---

## G4. Selector ambiguity policy

**Decision: resolve deterministically, do not fail by default, make ambiguity visible.**

Priority: `resourceId` → `content-desc` → exact `text` → `className+text/other constraint` → `bounds`.

If a selector matches multiple elements:

1. If exactly one matched node is `focused=true`, choose it.
2. Else if all matches are the same screen rect (≥90% overlap), choose the first (same element).
3. Else choose first in document order **and** emit a `warning` with `matched_count` and the bounds list, so the agent can disambiguate with `--bounds`.
4. `--strict-selector` turns any multi-match into `SELECTOR_NOT_FOUND` (exit 3).

`--bounds X1,Y1-X2,Y2` taps the rect center; after the tap a fresh read returns the node occupying that point as the resolved element.

**After every mutation**, resolve and return a snapshot: `{resourceId, text, contentDesc, className, bounds, visible_to_selector_engine}` — this is the "resolved element identity" (it is *not* an index).

---

## G5. Canonical error catalog

**Decision: stable string codes map 1:1 to exit codes, retryability, and hint templates.**

| Code | Meaning | Exit | Retryable | Hint |
|---|---|---:|---|---|
| `USAGE` | Invalid args/selector grammar | 1 | no | "Run u2ctl <domain> <tool> --help" |
| `DEVICE_NONE` | No devices on ADB | 2 | yes | "Connect USB or `adb connect <ip>`" |
| `DEVICE_AMBIGUOUS` | Multiple devices, no `--serial` | 2 | no | "Pass --serial <serial> from `device list`" |
| `DEVICE_NOT_FOUND` | Serial present but not on ADB | 2 | yes | Wi-Fi fallback `u2ctl device reconnect` |
| `DEVICE_UNAUTHORIZED` | USB authorization pending | 2 | yes | "Accept the RSA prompt on the device" |
| `DEVICE_OFFLINE` | `offline` transport state | 2 | yes | "Run `u2ctl device reconnect --serial X`" |
| `ADB_UNAVAILABLE` | `adb` not on PATH | 2 | no | "Install platform-tools or set ADB_PATH" |
| `SELECTOR_NOT_FOUND` | No element matched | 3 | no | "Re-dump with `ui.dump --filter actionable`" |
| `APP_NOT_FOUND` | Package missing | 3 | no | "`app list` to verify the package name" |
| `PROVISION_BLOCKED` | USB install policy (`INSTALL_FAILED_USER_RESTRICTED`) | 4 | no | "Enable Install via USB in Developer options" |
| `PROVISION_FAILED` | Other provisioning dependency failure | 4 | yes | "Run `setup diagnose`" |
| `TIMEOUT` | Operation exceeded deadline | 5 | yes | "Raise `--timeout`, or reconnect first" |
| `POSTCONDITION_FAILED` | `expect` not satisfied after action | 5 | no | "Re-dump; the UI state may have changed" |
| `TRANSIENT` | Offline/timeout hit mid-action, may retry | 5 | yes | "Retry once, then `device reconnect`" |
| `INTERNAL` | Unexpected exception | 10 | no | "Report the command + JSON envelope" |

Envelope uses `error.code`, `error.retryable`, `error.hint` (see PLAN.md). The CLI maps errors to exit codes centrally — handlers never set exit codes.

---

## G6. Postcondition mechanism

**Decision: declarative, machine-checked, enforced for mutations.**

`ToolSpec.expect` is one of:

- `{"schema": <sub-schema>}` — the result `dict` must validate the sub-schema.
- `{"element": {"text": "X", "resource_id": "…"}, "state": "exists"}` — after the action, the given selector must resolve within `expect_timeout` seconds (default 3).
- `{"element": ..., "state": "gone"}` — must *not* resolve (for dismiss/delete flows).
- `{"screen": "fingerprint"}` — the recomputed fingerprint must equal the given one (G12 replay / idempotency proof).

Read tools (`safety=read`) may omit `expect`. Mutation tools **must** declare one — enforced at registration.

Implementation: `registry.verify_postcondition(ctx, expected)` runs after the handler returns, inside the same device session, before the envelope is emitted. Failure raises `POSTCONDITION_FAILED`.

---

## G7. Guardrail enforcement

**Decision: enforcement lives in the CLI layer, single choke-point, never inside handlers.**

- `safety=read`: no guard.
- `safety=interactive`: no confirmation; each mutation emits one stderr audit line (`[audit] <command> <device> <args>`). `--dry-run` prints the exact envelope that would result without executing (read tools ignore it).
- `safety=destructive`: requires explicit `--yes`. Absent → `USAGE` with the confirmation contract text. Requires `--yes` to appear at least once; `--dry-run` alone never executes.
- A capability ceiling env `U2CTL_SAFETY` (G8) caps the highest allowed safety, so an untrusted agent can be locked to `read` (destructive/interactive tools then fail with `USAGE` before touching the device).
- Idempotency: `ToolSpec.idempotent` is reported in every mutation envelope so agents know whether a retry is safe.

---

## G8. Config precedence and env names

**Decision: flags > environment > config file > code default.**

| Key | Flag | Env | Config key | Default |
|---|---|---|---|---|
| Serial | `--serial` | `U2CTL_SERIAL` (then `ANDROID_SERIAL`) | `serial` | "exactly one device" rule |
| Timeout (s) | `--timeout` | `U2CTL_TIMEOUT` | `timeout` | `30` (ui.wait clamp 120) |
| JSON output | `--json` | `U2CTL_JSON=1` | `json` | `false` |
| Safety ceiling | — | `U2CTL_SAFETY=read\|interactive\|destructive` | `safety` | `interactive` |
| Config path | — | `U2CTL_CONFIG` | — | `.u2ctl.json` in cwd, else `~/.config/u2ctl/config.json` |
| adb binary | — | `ADB_PATH` | `adbPath` | `shutil.which("adb")` |
| Strict selectors | `--strict-selector` | `U2CTL_STRICT_SELECTOR=1` | `strictSelector` | `false` |

- Config file is flat JSON; keys match env names without the `U2CTL_` prefix. Enum values validated (unknown → `USAGE`).
- `.env`/API keys are out of scope for this package; it never loads them.

---

## G9. Dependency and tooling inventory

**Decision:**

```
requires-python = ">=3.9"            # validated on 3.10/3.11
dependencies:
  uiautomator2>=3.7.0,<4            # pin the adapter range; change behind the adapter
  adbutils>=2.9,<3                  # explicit (transitively present)
  jsonschema>=4.21,<5               # validation only; no pydantic

[project.scripts] u2ctl = "u2ctl.cli:main"
```

- Project manager: **uv** (repository already uses it for mobilerun). Dev: `uv sync`, `uv run u2ctl ...`, `uv run pytest`, `uv run python -m u2ctl`.
- Editable install for development; `uv build`/`publish` for release.
- No `rich`, no `click`, no `typer`: argparse + `--json` contract keeps output plain, fast, and diff-stable across platforms.
- Windows UTF-8 guarantee: `cli.py` beginning reconfigures `sys.stdout`/`sys.stderr` to `utf-8` (guarded), and docs mandate `PYTHONUTF8=1` on Windows Git Bash consistently with AGENTS.md.

## G10. Test harness and CI

**Decision:**

- `pyproject.toml`:

  ```text
  [tool.pytest.ini_options]
  testpaths = ["tests"]
  markers = ["device: requires a physical device (U2CTL_DEVICE_SERIAL)"]
  ```

- `tests/conftest.py`: option/env `U2CTL_DEVICE_SERIAL`; if set → `device_session` fixture uses the real adapter; if not → device-marked tests `pytest.skip("set U2CTL_DEVICE_SERIAL")`.
- Fixtures: `fake_adapter` (success/offline/not-found/timeout), `invoke_cli` (in-process, captures stdout/stderr + exit code), `proc_cli` (subprocess `python -m u2ctl` for golden JSON byte-stability).
- Golden files: `tests/contract/golden/*.json`; refresh with `U2CTL_UPDATE_GOLDEN=1`.
- Coverage gate: ≥80% on `src/u2ctl` (domains excluded from the floor; they're thin).
- CI (`.github/workflows/ci.yml`): matrix `{ubuntu-latest, windows-latest} × {3.10, 3.11}`; steps: uv setup → `uv sync` → `uv run pytest -m "not device"` → coverage gate. Device smoke never runs on hosted CI (no reachable device); it runs locally via `uv run pytest -m device`.

---

## G11. Windows/MSYS operations

**Decision:**

- adb discovery: `ADB_PATH` > `shutil.which("adb")`; missing → `ADB_UNAVAILABLE` with a platform-tools hint.
- adb server lifecycle: `device reconnect` → `adb reconnect <serial>`; if `DEVICE_NONE` and `--hard` passed → `adb kill-server` + `adb start-server` (destructive to the local adb server, never implicit).
- MSYS path conversion is a Git-Bash concern only for raw `adb shell` invocations; the CLI spawns adb via the Python library (adbutils), so it is unaffected. AGENTS.md guidance for manual commands stays.
- Stay-awake settings (`svc power stayon true`, `screen_off_timeout`) are applied **only** on explicit `setup install --keep-awake`, reported as a reversible step, never silently.
- Every blocking adapter call runs under an external deadline wrapper (device-independent watchdog), not unbounded waits.

---

## G12. Forward-compat with the `macro` domain

**Decision: reserve the space now, ship composability today.**

- `macro` is a reserved domain name; MVP rejects registering `macro.*` tools, so the name can't be squatted by a future conflicting domain.
- `ctx.call_tool("ui.tap", ...)` gives any future `macro.record`/`macro.replay` the same execution path as the CLI — replay is a loop over recorded tool calls, no new mechanism.
- `screen_fingerprint` (G3) is the replay assertion primitive ("am I on the expected screen?").
- The `expect`/postcondition mechanism (G6) is the replay continuation guard ("did the action land?").
- Account for these hooks in Phase 3 exit criteria: `ui.dump` must return `screen_fingerprint`, and every mutation must return the resolved element, so a future recorder has everything without re-instrumenting.

---

## Build order for the first work unit (PLAN Phase 0 + G1–G12 prerequisites)

1. `pyproject.toml` + console script + UTF-8 bootstrap (G9, G11).
2. `errors.py` exit-code mapping + `config.py` precedence (G5, G8).
3. `output.py` envelope + `--json`/human rendering (PLAN JSON contract).
4. `registry.py` `ToolSpec`/`DomainSpec` + startup validation (G2) + loading (G1).
5. `Runtime` transport isolation stub + fake adapter fixture (G10).
6. `device` domain: `list`, `status`, `info`, `reconnect` (G5, G11).
7. `setup verify` (read-only); `setup install` (steps + `--keep-awake`) (G5, G7).
8. `tools` intro commands (generated from the same registry).
9. Tests: CLI callable, golden envelopes for device/setup/tools, zero/one/multi/offline/unauth matrices (G10).
10. Update PLAN.md where this spec wins (G1–G12 notes) and AGENTS.md runbook lines for `u2ctl`.

## Acceptance checklist for this spec

- [ ] Adding a capability requires zero argument-parser code (G1).
- [ ] Handlers use one fixed signature and never emit exit codes or parse strings (G2).
- [ ] `actionable`, dedup, system-chrome exclusion, and `screen_fingerprint` are implemented as written (G3).
- [ ] Ambiguous selectors resolve deterministically and warn (G4).
- [ ] Every error in G5 renders the envelope with `code/retryable/hint` and correct exit code.
- [ ] Mutation tools fail to register without an `expect` (G6).
- [ ] `U2CTL_SAFETY=read` locks out interactive/destructive tools (G7).
- [ ] Config precedence and env names match G8 exactly.
- [ ] Dependency pins match G9; `uv sync` + tests pass on Ubuntu & Windows.
- [ ] Smoke suite gates on `U2CTL_DEVICE_SERIAL` (G10).
- [ ] `u2ctl device reconnect` and `--hard` behave as specified (G11).
- [ ] `macro` reserved; `ui.dump` returns `screen_fingerprint` (G12).