"""Main CLI entrypoint and execution coordinator for u2ctl."""

import sys
import io
import argparse
from typing import List, Optional, Dict, Any
import jsonschema

from u2ctl import __version__
from u2ctl.config import resolve_config, Config
from u2ctl.errors import (
    U2CtlError,
    UsageError,
    InternalError,
    ADBUnavailableError,
)
from u2ctl.output import print_output, log_audit
from u2ctl.registry import registry, HandlerContext
from u2ctl.domains import init_domains


def _reconfigure_utf8() -> None:
    """Ensure standard output streams use UTF-8 encoding on Windows/MSYS."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass


SAFETY_RANK = {"read": 1, "interactive": 2, "destructive": 3}


def main(argv: Optional[List[str]] = None) -> int:
    _reconfigure_utf8()
    if argv is None:
        argv = sys.argv[1:]

    # Register all domain tools
    init_domains()

    # Global parent parser for inherited flags
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument("--serial", type=str, help="ADB device serial")
    parent_parser.add_argument("--timeout", type=int, help="Command timeout in seconds")
    parent_parser.add_argument("--json", action="store_true", help="Emit output strictly as JSON envelope")
    parent_parser.add_argument("--quiet", action="store_true", help="Suppress non-essential diagnostics")
    parent_parser.add_argument("--dry-run", action="store_true", help="Print envelope without executing action")
    parent_parser.add_argument("--strict-selector", action="store_true", help="Fail on ambiguous selector matches")
    parent_parser.add_argument("--yes", action="store_true", help="Confirm destructive actions explicitly")

    parser = argparse.ArgumentParser(
        prog="u2ctl",
        description="Stateless, LLM-agnostic Android control CLI backed by uiautomator2.",
        parents=[parent_parser],
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    registry.build_cli_parser(parser, parent_parser=parent_parser)

    # Parse args
    try:
        parsed = parser.parse_args(argv)
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 1

    if not getattr(parsed, "_cli_domain", None) or not getattr(parsed, "_cli_tool", None):
        parser.print_help(sys.stderr)
        return 1

    tool_name = f"{parsed._cli_domain}.{parsed._cli_tool}"
    spec = registry.get_tool(tool_name)
    if not spec:
        err = UsageError(f"Unknown command: '{tool_name}'")
        print_output(tool_name, None, error=err, json_mode=parsed.json, quiet=parsed.quiet)
        return err.exit_code

    # Extract CLI flags for config resolution
    cli_dict = {
        "serial": parsed.serial,
        "timeout": parsed.timeout,
        "json": parsed.json,
        "strict_selector": parsed.strict_selector,
    }

    try:
        config = resolve_config(cli_dict)
    except U2CtlError as err:
        print_output(tool_name, None, error=err, json_mode=parsed.json, quiet=parsed.quiet)
        return err.exit_code

    # Guardrail Safety Ceiling Checks (BUILDSPEC G7)
    tool_rank = SAFETY_RANK.get(spec.safety, 2)
    ceiling_rank = SAFETY_RANK.get(config.safety_ceiling, 2)

    if tool_rank > ceiling_rank:
        err = UsageError(
            f"Action '{tool_name}' requires safety level '{spec.safety}', but environment safety ceiling is set to '{config.safety_ceiling}'",
            hint=f"Unset or raise U2CTL_SAFETY environment variable to at least '{spec.safety}'",
        )
        print_output(tool_name, config.serial, error=err, json_mode=config.json_output, quiet=parsed.quiet)
        return err.exit_code

    if spec.safety == "destructive" and not parsed.yes:
        err = UsageError(
            f"Action '{tool_name}' is destructive and requires explicit confirmation '--yes'",
            hint=f"Rerun command with '--yes' flag: u2ctl {parsed._cli_domain} {parsed._cli_tool} --yes",
        )
        print_output(tool_name, config.serial, error=err, json_mode=config.json_output, quiet=parsed.quiet)
        return err.exit_code

    # Extract args passed to the tool subcommand
    subcommand_args = {}
    for prop in spec.input_schema.get("properties", {}).keys():
        val = getattr(parsed, prop, None)
        if val is not None:
            subcommand_args[prop] = val

    # Audit logging for mutations
    if spec.safety in {"interactive", "destructive"} and not parsed.dry_run:
        log_audit(tool_name, config.serial, subcommand_args)

    # Dry-run handling
    if parsed.dry_run and spec.safety in {"interactive", "destructive"}:
        dry_result = {
            "dry_run": True,
            "would_execute": tool_name,
            "args": subcommand_args,
        }
        print_output(tool_name, config.serial, result=dry_result, json_mode=config.json_output, quiet=parsed.quiet)
        return 0

    ctx = HandlerContext(serial=config.serial or "", timeout=config.timeout)

    try:
        # Validate input args against JSON schema
        try:
            jsonschema.validate(instance=subcommand_args, schema=spec.input_schema)
        except jsonschema.exceptions.ValidationError as e:
            raise UsageError(f"Invalid arguments for {tool_name}: {e.message}")

        # Execute handler
        result = spec.handler(ctx, subcommand_args)

        # Validate output result against schema
        try:
            jsonschema.validate(instance=result, schema=spec.output_schema)
        except jsonschema.exceptions.ValidationError as e:
            raise InternalError(f"Handler output for {tool_name} failed schema validation: {e.message}")

        # Verify declarative postcondition (G6)
        registry.verify_postcondition(ctx, spec, result)

        print_output(
            tool_name,
            ctx.serial or config.serial,
            result=result,
            warnings=ctx.warnings,
            json_mode=config.json_output,
            quiet=parsed.quiet,
        )
        return 0

    except U2CtlError as err:
        print_output(
            tool_name,
            ctx.serial or config.serial,
            error=err,
            warnings=ctx.warnings,
            json_mode=config.json_output,
            quiet=parsed.quiet,
        )
        return err.exit_code
    except Exception as exc:
        err = InternalError(f"Unexpected internal error: {exc}")
        print_output(
            tool_name,
            ctx.serial or config.serial,
            error=err,
            warnings=ctx.warnings,
            json_mode=config.json_output,
            quiet=parsed.quiet,
        )
        return err.exit_code


if __name__ == "__main__":
    sys.exit(main())
