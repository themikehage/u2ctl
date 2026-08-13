# AGENTS.md — Non-Negotiable Principles & Runbook

This document defines the core invariants and rules for `u2ctl`. Every contribution and feature MUST adhere to these principles.

## 1. Core Principles

1. **LLM-Agnostic Core**: No LLM client, prompt logic, API keys, or provider SDKs inside `u2ctl`. It is a pure, stateless tool protocol for external agents or humans.
2. **Stateless Execution**: Each command execution is stateless and self-contained. No background daemons, state persistence, or inter-command memory.
3. **Single Source of Truth**: The `registry` owns capability metadata, JSON Schemas, CLI parsing, and documentation generation. Never manually edit argument parsers.
4. **Machine-First Output Envelope**: `stdout` outputs ONLY the standard JSON envelope when `--json` is set. All diagnostics, logs, and audit lines MUST go to `stderr`.
5. **Deterministic Behavior & Ambiguity Policy**: No hidden retries or implicit selector choices. Ambiguous matches resolve deterministically with warnings or fail with `--strict-selector`.
6. **Enforced Postconditions**: Every mutation operation MUST declare and verify a postcondition (`expect`).
7. **Safe & Idempotent Provisioning**: Setup operations are step-by-step, idempotent, and report explicit statuses without hiding OS/device policy errors (e.g., Xiaomi USB install locks).
8. **Typed Errors & Exit Codes**: All failures map to standard error codes and non-zero exit codes. Python tracebacks must never be printed to stdout/stderr in standard execution.

## 2. Environment & Tooling

- Package manager: `uv`
- Python version: `>=3.9`
- Code formatting / linting: standard Python conventions, UTF-8 stdout/stderr explicitly handled.
- Windows execution: run commands under `PYTHONUTF8=1` in Git Bash / MSYS if applicable.

## 3. Development Workflow

- Run unit tests: `uv run pytest -m "not device"`
- Run device smoke tests (physical device required): `U2CTL_DEVICE_SERIAL=da0f5e72 uv run pytest -m device`
- Code changes must be accompanied by relevant unit or contract tests.
