# u2ctl Implementation Plan

## Outcome

Build `u2ctl`, an installable, LLM-agnostic Android control CLI backed by
uiautomator2. The CLI will expose a stable, machine-readable capability
catalog that can be used by Claude Code, OpenCode, Codex, or a custom agent.

The first release will validate and provision Android devices, expose core UI
and app operations, and provide enough introspection for an external agent to
plan and execute actions. It will not embed an LLM and will not replace
mobilerun's trajectory system in the first milestone.

## Principles

| Principle | Implementation consequence |
|---|---|
| LLM-agnostic | No model client, prompt loop, API key, or provider dependency in the core package. |
| One capability contract | The registry is the source of truth for CLI commands, schemas, help, and documentation. |
| Machine-first output | JSON output is stable, compact, versioned, and emitted separately from diagnostics. |
| Deterministic execution | Explicit selectors, timeouts, waits, retries, and postconditions; no hidden model decisions. |
| Safe provisioning | Setup is idempotent, reports partial failure, and never silently changes device state beyond declared actions. |
| Transport isolation | ADB, uiautomator2, and future transports are behind internal ports. |
| Observable failure | Errors have stable codes, actionable details, and remediation hints. |

## Scope

### MVP in scope

- Discover connected ADB devices and select one explicitly.
- Validate device state, Android metadata, screen state, and transport health.
- Provision and verify the uiautomator2 runtime and input method.
- Recover common `offline` and `unauthorized` states with explicit commands.
- Start, stop, inspect, and identify Android applications.
- Dump the UI hierarchy, including a compact actionable-element projection.
- Execute UI actions: tap, text input, swipe, press, wait, and back/home.
- Expose capability metadata and JSON schemas through `tools` commands.
- Provide unit tests with fake transports and a small device smoke-test suite.

### Explicitly out of scope for MVP

- Embedded LLM or prompt orchestration.
- Automatic action selection based on an LLM.
- Full macro recording and deterministic replay.
- Replacing mobilerun or migrating existing trajectories.
- Multi-device orchestration and parallel execution.
- A web dashboard, GUI inspector, or long-running daemon.
- Arbitrary shell execution exposed as an agent capability.

## Proposed Package Layout

```text
u2ctl/
  pyproject.toml
  src/u2ctl/
    cli.py                 # command parsing and process exit handling
    config.py              # serial, timeouts, output, and local config
    errors.py              # typed errors and stable error codes
    models.py              # device, action, result, and capability models
    registry.py            # capability registration and schema export
    output.py              # JSON envelope and human-readable rendering
    runtime/
      adb.py               # ADB discovery and recovery operations
      device.py            # device session lifecycle
      uiautomator.py       # uiautomator2 adapter
      provisioning.py      # idempotent setup and verification
    domains/
      device.py            # status, info, reconnect
      setup.py              # install, verify, diagnose
      app.py                # start, stop, current, list
      ui.py                 # dump, tap, input, swipe, press, wait
    selectors/
      parser.py             # validated selector forms
      resolver.py           # selector priority and fallback behavior
  tests/
    unit/
    contract/
    smoke/
  docs/
    capability-catalog.md
```

The current `poc_u2.py` remains a reference during implementation and is
replaced by tested package code once equivalent behavior exists.

## Capability Registry

Each domain registers explicit `ToolSpec` objects. A spec owns the public
contract and points to its implementation; schemas are not duplicated in
separate YAML files.

```python
ToolSpec(
    name="ui.tap",
    domain="ui",
    description="Tap one visible UI element using a validated selector.",
    input_schema={...},
    output_schema={...},
    handler=ui_tap,
    safety="interactive",
    requires=["device.connected", "runtime.uiautomator.ready"],
)
```

Every capability must define:

- Stable fully qualified name, such as `device.status` or `ui.dump`.
- Short agent-facing description focused on intent and constraints.
- Input schema with required fields, allowed values, and bounds.
- Output schema with successful result fields and postcondition data.
- Required runtime capabilities and provisioning dependencies.
- Timeout and retry policy, if applicable.
- Safety class: `read`, `interactive`, or `destructive`.
- Stable error codes and recovery hints.

The registry will expose:

```text
u2ctl tools list --json
u2ctl tools show ui --json
u2ctl tools schema --format openai --json
```

The `openai` format is an interoperability format for external agents; the
core registry remains provider-neutral.

## CLI Contract

### Global options

```text
u2ctl [--serial SERIAL] [--timeout SECONDS] [--json] [--quiet] COMMAND
```

Rules:

- A serial is optional only when exactly one device is connected.
- Ambiguous device selection is an error, never an implicit choice.
- Human output is for interactive use; `--json` is the agent contract.
- Diagnostics go to stderr; structured results go to stdout.
- Every command returns a documented exit code.
- Commands must not print tracebacks by default.

### Initial command surface

```text
u2ctl device list
u2ctl device status
u2ctl device info
u2ctl device reconnect

u2ctl setup install
u2ctl setup verify
u2ctl setup diagnose

u2ctl app current
u2ctl app start --package PACKAGE
u2ctl app stop --package PACKAGE

u2ctl ui dump [--filter actionable] [--limit N]
u2ctl ui tap (--text TEXT | --resource-id ID | --description DESC | --bounds BOUNDS)
u2ctl ui input --text TEXT
u2ctl ui swipe --from X,Y --to X,Y [--duration SECONDS]
u2ctl ui press --key KEY
u2ctl ui wait --selector SELECTOR [--timeout SECONDS]
```

### JSON envelope

All machine-readable responses use one envelope:

```json
{
  "schema_version": "1",
  "ok": true,
  "command": "ui.tap",
  "device": "da0f5e72",
  "result": {},
  "warnings": []
}
```

Errors use the same envelope:

```json
{
  "schema_version": "1",
  "ok": false,
  "command": "device.status",
  "error": {
    "code": "DEVICE_OFFLINE",
    "message": "The selected device is offline.",
    "retryable": true,
    "hint": "Run u2ctl device reconnect --serial da0f5e72."
  }
}
```

Initial exit codes:

| Code | Meaning |
|---:|---|
| 0 | Success |
| 1 | Usage or validation error |
| 2 | Device unavailable, unauthorized, or offline |
| 3 | Selector or application not found |
| 4 | Provisioning or dependency failure |
| 5 | Action timeout or transient runtime failure |
| 10 | Unexpected internal error |

## Selector Strategy

Selectors are validated before execution and use an explicit priority order:

1. Resource ID.
2. Accessibility description.
3. Exact visible text.
4. Class plus text/resource constraints.
5. Bounds only when explicitly requested or when no semantic selector exists.

The CLI must return the resolved element identity and bounds after an action.
Raw hierarchy indexes are never treated as stable identifiers. `ui.dump
--filter actionable` must report enough metadata for an external agent to
choose a selector without receiving the full XML by default.

Because `dump_hierarchy()` and selector visibility can disagree on this
device, the adapter must distinguish `present_in_dump` from
`visible_to_selector_engine` and include that distinction in diagnostics.

## Provisioning Model

`setup install` is a sequence of independently verifiable steps:

1. Confirm ADB connectivity and authorization.
2. Confirm Android API/device metadata.
3. Push or start the uiautomator2 runtime.
4. Install or verify the input method required for text entry.
5. Apply optional stability settings explicitly requested by the user.
6. Verify a round-trip connection and a harmless UI read.

Each step reports `installed`, `already_present`, `skipped`, or `failed`.
Partial failure must preserve the completed-step report and a remediation
command. Provisioning must not hide Xiaomi's `INSTALL_FAILED_USER_RESTRICTED`;
it must classify it as an actionable device-policy error.

`setup verify` is read-only. `setup diagnose` collects evidence without
performing repair. This separation is important when an external agent is
allowed to inspect but not mutate a device.

## Execution Flow

Every action follows the same pipeline:

1. Parse and validate CLI input against the capability schema.
2. Resolve the target device deterministically.
3. Check declared runtime prerequisites.
4. Create or reuse a short-lived device session.
5. Execute the adapter operation with a deadline.
6. Verify the declared postcondition where possible.
7. Return the JSON envelope and stable exit code.

Retries are limited, observable, and only enabled for classified transient
errors. A retry must never repeat a destructive action without an explicit
idempotency policy.

## Implementation Phases

### Phase 0: Repository foundation

- Add `pyproject.toml` and an installable `u2ctl` console script.
- Replace ad hoc dependency usage with pinned, supported dependency ranges.
- Add logging, configuration, typed models, error hierarchy, and test layout.
- Keep `.env` out of package code and version control.

**Exit criteria:** `u2ctl --help`, `u2ctl --version`, and unit tests run from a
clean environment.

### Phase 1: Device and runtime lifecycle

- Implement device discovery and explicit serial selection.
- Implement `device status/info/reconnect`.
- Implement idempotent `setup install/verify/diagnose`.
- Add Xiaomi-specific diagnostics without hard-coding the device as the only
  supported target.

**Exit criteria:** clean setup, repeated setup, unauthorized device, offline
device, and blocked USB-install scenarios produce correct envelopes and exit
codes.

### Phase 2: Registry and introspection

- Implement `ToolSpec`, registry loading, dependency metadata, and validation.
- Add `tools list/show/schema`.
- Validate duplicate names, invalid schemas, missing handlers, and unsupported
  safety classes at startup.

**Exit criteria:** every exposed command has exactly one registry entry and the
exported schema is sufficient for an external agent to call it.

### Phase 3: App and UI domains

- Implement app lifecycle commands.
- Implement compact filtered dumps.
- Implement semantic selectors, coordinate fallback, input, gestures, key
  presses, waits, and postcondition reporting.
- Add timeouts and bounded retries.

**Exit criteria:** the existing POC behavior is reproduced through the CLI,
including app launch, filtered dump, scroll, home, and text entry.

### Phase 4: Contract and device smoke tests

- Add golden JSON tests for successful and failed commands.
- Add fake adapter tests for every domain handler.
- Add a gated Mi 9 SE smoke suite requiring `U2CTL_DEVICE_SERIAL`.
- Verify setup, dump, tap, swipe, text input, app lifecycle, and recovery.

**Exit criteria:** CI passes without a physical device, and the optional device
suite produces a clear skipped result when no device is configured.

### Phase 5: Agent integration and hardening

- Publish schemas in OpenAI-compatible function format.
- Add examples for Claude Code, OpenCode, and Codex command invocation.
- Document permission boundaries and safe capability selection.
- Add performance measurements for hierarchy filtering and command latency.
- Define versioning and deprecation policy for capabilities and JSON envelopes.

**Exit criteria:** an external agent can discover capabilities, inspect a
device, execute a UI action, and recover from a classified transient failure
without parsing human text.

## Testing Strategy

| Layer | What it proves | Device required |
|---|---|---:|
| Unit | Schemas, models, selectors, errors, output envelopes | No |
| Contract | Every registered tool maps to a valid CLI command and schema | No |
| Adapter fake | Runtime behavior under success, timeout, offline, and not-found states | No |
| CLI subprocess | Exit codes, stdout/stderr separation, JSON stability | No |
| Device smoke | Real uiautomator2 and Xiaomi-specific behavior | Yes |
| Manual agent trial | Discover, plan, execute, and recover using an external CLI agent | Yes |

Critical regression cases:

- Zero devices and multiple devices without `--serial`.
- `offline`, `unauthorized`, and disconnected devices.
- `INSTALL_FAILED_USER_RESTRICTED` during setup.
- Missing or stale UI selectors.
- Selector visible in dump but not visible to the query engine.
- Text containing spaces, accents, Unicode, and shell-sensitive characters.
- Repeated setup and repeated read-only actions.
- Timeout during a gesture or app launch.
- Device reconnect after screen-off.

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| MIUI kills `adbd` when screen is off | Diagnose, expose bounded reconnect, and document optional stay-awake settings. |
| USB installs are blocked | Classify the exact error and provide the required developer-setting hint. |
| UI changes break selectors | Prefer semantic selectors, return resolved metadata, and avoid raw indexes. |
| Schema and implementation drift | Registry-owned specs, startup validation, and contract tests. |
| Agent repeats an unsafe action | Safety classes, explicit confirmation policy, idempotency metadata, and no hidden retries. |
| Output changes break agents | Versioned JSON envelope and golden contract tests. |
| uiautomator2 behavior changes across versions | Pin a tested range and isolate it behind an adapter. |
| Tool becomes coupled to one LLM host | Keep CLI protocol and schema export provider-neutral. |

## Definition Of Done For MVP

- [ ] Fresh installation exposes `u2ctl` and `u2ctl --help`.
- [ ] A user can select and validate a connected device.
- [ ] Setup is repeatable and reports every provisioning step.
- [ ] `tools` exports complete, valid schemas for all MVP capabilities.
- [ ] UI output is compact, stable, and useful to an external agent.
- [ ] App and UI actions return postconditions, not just acknowledgements.
- [ ] All expected failures have stable JSON error codes and exit codes.
- [ ] Unit, contract, subprocess, and optional device smoke tests exist.
- [ ] No LLM provider, API key, or prompt logic is required by the package.
- [ ] Existing mobilerun trajectories remain untouched and runnable.

## First Work Unit

Implement the repository foundation and the device lifecycle before adding UI
actions:

1. Create the package and console entry point.
2. Define models, errors, JSON envelope, and configuration.
3. Implement `device list`, `device status`, and serial selection.
4. Implement `setup verify` as read-only.
5. Add tests for zero, one, multiple, offline, and unauthorized devices.

This gives us a reliable boundary around the physical device before selector
semantics and agent-facing action execution increase the surface area.
