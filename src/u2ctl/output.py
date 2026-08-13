"""Output envelope and formatting for stdout/stderr."""

import sys
import json
from typing import Optional, Dict, Any, List

from u2ctl.errors import U2CtlError

SCHEMA_VERSION = "1"


def build_success_envelope(
    command: str,
    device: Optional[str],
    result: Dict[str, Any],
    warnings: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": True,
        "command": command,
        "device": device or "",
        "result": result,
        "warnings": warnings or [],
    }


def build_error_envelope(
    command: str,
    error: U2CtlError,
    device: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": False,
        "command": command,
        "device": device or "",
        "error": error.to_dict(),
    }


def print_output(
    command: str,
    device: Optional[str],
    result: Optional[Dict[str, Any]] = None,
    error: Optional[U2CtlError] = None,
    warnings: Optional[List[str]] = None,
    json_mode: bool = False,
    quiet: bool = False,
) -> None:
    """Print standard stdout envelope (or human readable text) and stderr warnings/diagnostics."""
    if warnings and not quiet:
        for w in warnings:
            print(f"[warning] {w}", file=sys.stderr)

    if error:
        if json_mode:
            env = build_error_envelope(command, error, device=device)
            print(json.dumps(env, ensure_ascii=False, indent=2), file=sys.stdout)
        else:
            print(f"Error [{error.code}]: {error.message}", file=sys.stderr)
            if error.hint:
                print(f"Hint: {error.hint}", file=sys.stderr)
    else:
        res = result or {}
        if json_mode:
            env = build_success_envelope(command, device, res, warnings=warnings)
            print(json.dumps(env, ensure_ascii=False, indent=2), file=sys.stdout)
        else:
            # Human readable output
            if not quiet:
                print(f"OK ({command}):")
                print(json.dumps(res, ensure_ascii=False, indent=2))


def log_audit(command: str, device: Optional[str], args: Dict[str, Any]) -> None:
    """Emit one mandatory audit line to stderr for mutation commands."""
    formatted_args = " ".join(f"{k}={v}" for k, v in args.items() if v is not None)
    device_str = device or "unknown"
    print(f"[audit] {command} device={device_str} {formatted_args}", file=sys.stderr)
