---
name: u2ctl
description: Concise operational guide and feedback contract for AI agents driving Android devices via the u2ctl CLI.
---

# u2ctl — Agent Skill & Operational Contract

---

## 0. Routines Protocol (Run FIRST on every task)

Routines are concise, deterministic step-by-step scripts derived from real executions. They eliminate trial-and-error on repeated objectives.

### 0.1 Lookup Flow

```
TASK RECEIVED
    │
    ▼
Does .agents/skills/u2ctl/routines/ exist?
    ├── NO  → mkdir .agents/skills/u2ctl/routines/
    │
    ▼
Does routines/<slug>.md exist for this objective?  (see §0.3 for slug rules)
    ├── YES → READ IT. Execute its steps literally. Skip exploration.
    └── NO  → Proceed with normal §1–§4 interaction loop.
              On task completion → CREATE routines/<slug>.md (§0.2).
```

### 0.2 Routine File Format

After completing (or on meaningful partial completion of) an objective, write the routine file:

```markdown
# <Human-readable objective title>

## Context
- App package / Activity where this starts: `<package>`
- Precondition: <what must be true on screen before step 1>

## Steps
1. `u2ctl ui find --text-contains "<X>" --scroll-direction down --json`  → locate element
2. `u2ctl ui tap --text "<X>" --serial <SERIAL> --json`
3. `u2ctl ui dump --filter actionable --limit 30 --json`  → verify screen changed
...

## Postcondition
<What the final screen looks like — fingerprint hint or visible text>

## Known Pitfalls
- <Any selector ambiguity, timing issue, or OS dialog that appeared>
```

**Rules for routine content:**
- Only include commands that were actually executed successfully.
- No placeholders — use real text, real resource_ids, real scroll directions.
- If a step failed and was replaced, keep the replacement only.
- Keep it under 30 lines. One action per step.

### 0.3 Slug Rules

Derive the filename from the objective using these rules (in order):

| Rule | Example objective | Slug |
|---|---|---|
| Lowercase words joined by `-` | "Like a post on Facebook" | `like-post-facebook.md` |
| Strip articles/prepositions | "Tap the back button" | `tap-back-button.md` |
| Max 5 words | "Open notification shade and clear all" | `open-notification-clear-all.md` |

### 0.4 Routine Maintenance

- If a routine **fails at any step**, update the file: correct the failing step or mark it with `⚠️ UNRELIABLE` and document the actual fix.
- If the app **updated** and selectors changed, overwrite the affected steps.
- Never delete a routine — update it.

---

`u2ctl` is a stateless, LLM-agnostic Android control CLI. Output to `stdout` is **JSON by default** (use `--human` for text formatting). Diagnostics and audit logs go to `stderr`.

---

## 1. Quickstart & Capability Discovery

```bash
# 1. Discover capability catalog and OpenAI function schemas
u2ctl tools schema --format openai

# 2. List connected ADB devices (serial auto-selected if only 1 device is connected)
u2ctl device list

# 3. Check target device readiness (read-only)
u2ctl setup verify

# 4. Batch Execution (Atomic, Ultra-Fast Multi-Step Execution)
u2ctl run --steps '[{"tool":"ui.type","args":{"resource_id":"search_bar","text":"YouTube"}},{"tool":"ui.wait","args":{"text_contains":"YouTube"}}]'
```

---

## 2. Standard Interaction Loop

```mermaid
graph TD
    A[u2ctl run --steps '[...]'] --> B[Execute batch in 1 process & single connection]
    B --> C[Verify step postconditions & screen_fingerprint]
```

### Key Rules & Token Optimizations
1. **Use Batch Mode (`u2ctl run`) for Multi-Step Tasks (10x Faster)**: Pass a JSON array of step objects `[{"tool":"...", "args":{...}}, ...]`. It reuses a single connection and process spawn, running tasks in ~3s instead of 30s.
2. **Auto-Serial Selection**: `--serial <SERIAL>` is optional when only 1 device is connected; it auto-selects automatically.
3. **Use Macros**:
   - `ui.type`: Taps target input field and types text in 1 call (`u2ctl ui type --resource-id "input_id" --text "Hello"`).
   - `ui.scroll`: Swipe in high-level direction (`u2ctl ui scroll --direction down`).
4. **Combine Action + Verification**: Pass `--expect-desc-contains "..."`, `--expect-text-contains "..."`, or `--expect-element-absent` to `ui.tap` / `ui.long-press`. Returns `postcondition.expect_satisfied: true/false`.
5. **IME & System UI Filtered Automatically**: System bars and keyboards (Gboard, Samsung Keyboard) are filtered by default. Use `--include-system-bars` only when needed.
6. **Use Server-Side Dumping Filters**: `u2ctl ui dump --desc-contains "Search"` filters elements on device before returning.
7. **Use Compact Dump Mode**: Pass `--compact` to `ui dump` to omit false boolean fields.
8. **Use `ui.find` for Scrolling Navigation**: Use `u2ctl ui find --text-contains "..." --scroll-direction down` to scroll automatically until target element appears.

---

## 3. Error Codes & Recovery Strategy

All failures return exit code `> 0` and an error envelope:

```json
{
  "schema_version": "1",
  "ok": false,
  "command": "ui.tap",
  "device": "da0f5e72",
  "error": {
    "code": "DEVICE_OFFLINE",
    "message": "The selected device is offline.",
    "retryable": true,
    "hint": "Run u2ctl device reconnect --serial da0f5e72."
  }
}
```

| Exit | Error Code | Retryable? | Action Strategy |
|---:|---|:---:|---|
| 1 | `USAGE` | No | Check argument schema with `u2ctl tools show --domain <DOMAIN> --json`. |
| 2 | `DEVICE_OFFLINE` / `DEVICE_NOT_FOUND` | Yes | Run `u2ctl device reconnect --serial <SERIAL> --json`. Retry action once. |
| 2 | `DEVICE_UNAUTHORIZED` | Yes | Prompt human operator to accept RSA key prompt on phone. |
| 3 | `SELECTOR_NOT_FOUND` | No | Re-dump hierarchy with `u2ctl ui dump --filter actionable --json`. Screen moved. |
| 4 | `PROVISION_BLOCKED` | No | Prompt human operator to enable "Install via USB" in Developer options. |
| 5 | `TIMEOUT` / `TRANSIENT` | Yes | Reconnect device or increase `--timeout <SECS>`. Retry once. |
| 5 | `POSTCONDITION_FAILED` | No | UI did not transition. Re-dump hierarchy to inspect state change. |

---

## 4. Contract for Reporting Errors & Improvements

When an agent encounters an unresolvable issue, unexpected device behavior, or needs a missing capability, it MUST produce a structured feedback report adhering to this contract.

### 4.1 Error Report Schema (`u2ctl-error-report`)

When a command fails with `code: INTERNAL` (exit 10), unexpected driver error, or OS-level policy lock:

```json
{
  "report_type": "u2ctl_error_report",
  "timestamp": "<ISO-8601>",
  "command": "<command name, e.g. ui.tap>",
  "serial": "<device serial>",
  "exit_code": 10,
  "error_code": "<ERROR_CODE>",
  "raw_stderr": "<stderr output>",
  "reproduction_steps": [
    "u2ctl device status --serial da0f5e72 --json",
    "u2ctl ui tap --text 'Settings' --json"
  ],
  "device_context": {
    "model": "<device model>",
    "android_sdk": 31,
    "screen_fingerprint": "<fingerprint string>"
  },
  "impact": "blocking | degraded | cosmetic"
}
```

### 4.2 Improvement / Feature Proposal Schema (`u2ctl-feature-proposal`)

When an agent experiences friction, missing selectors, or missing capability domain:

```json
{
  "report_type": "u2ctl_feature_proposal",
  "timestamp": "<ISO-8601>",
  "category": "new_capability | selector_enhancement | performance | error_handling",
  "proposed_capability_name": "domain.action (e.g., ui.drag_and_drop)",
  "problem_statement": "Short description of what the agent tried to accomplish and why existing tools were insufficient.",
  "suggested_input_schema": {
    "type": "object",
    "properties": { ... }
  },
  "workaround_used": "How the agent bypassed the limitation (e.g. raw shell, coordinate math, multi-step swipe)."
}
```
