"""Run domain capability definitions for batch execution."""

import json
from pathlib import Path
from typing import Dict, Any, List

from u2ctl.errors import UsageError
from u2ctl.registry import ToolSpec, DomainSpec, HandlerContext
from u2ctl.batch import execute_batch_steps


def run_steps_handler(ctx: HandlerContext, args: Dict[str, Any]) -> Dict[str, Any]:
    steps_raw = args.get("steps")
    file_path = args.get("file")

    if not steps_raw and not file_path:
        raise UsageError("Must provide either '--steps' (JSON string) or '--file' (path to JSON file)")

    if steps_raw and file_path:
        raise UsageError("Cannot specify both '--steps' and '--file'")

    if file_path:
        p = Path(file_path)
        if not p.is_file():
            raise UsageError(f"Batch file not found: {file_path}")
        try:
            with open(p, "r", encoding="utf-8") as f:
                steps_data = json.load(f)
        except Exception as e:
            raise UsageError(f"Failed to parse batch JSON file {file_path}: {e}")
    else:
        try:
            steps_data = json.loads(steps_raw)
        except Exception as e:
            raise UsageError(f"Failed to parse '--steps' JSON string: {e}")

    if not isinstance(steps_data, list):
        raise UsageError("Batch steps payload must be a JSON array of step objects")

    return execute_batch_steps(steps_data, ctx)


RUN_DOMAIN = DomainSpec(
    name="run",
    description="Batch execution domain for multi-step atomic sequences",
    tools=[
        ToolSpec(
            name="run.steps",
            domain="run",
            description="Execute multiple commands sequentially in a single process / connection batch.",
            input_schema={
                "type": "object",
                "properties": {
                    "steps": {"type": "string", "description": "JSON array string containing step definitions [{'tool': ..., 'args': ...}]"},
                    "file": {"type": "string", "description": "File path to JSON file containing step definitions array"},
                },
                "additionalProperties": False,
            },
            output_schema={
                "type": "object",
                "required": ["completed_steps", "total_steps", "aborted", "step_results"],
                "properties": {
                    "completed_steps": {"type": "integer"},
                    "total_steps": {"type": "integer"},
                    "aborted": {"type": "boolean"},
                    "step_results": {"type": "array"},
                    "failed_step": {"type": "object"},
                },
            },
            handler=run_steps_handler,
            safety="interactive",
            idempotent=False,
            expect={"schema": {"type": "object", "required": ["completed_steps", "total_steps"]}},
        ),
    ],
)
