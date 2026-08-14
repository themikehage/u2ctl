"""Batch execution runner for u2ctl multi-step sequences."""

import time
import json
from typing import List, Dict, Any, Optional

import jsonschema

from u2ctl.errors import UsageError, InternalError, U2CtlError
from u2ctl.registry import registry, HandlerContext


def execute_batch_steps(
    steps: List[Dict[str, Any]],
    ctx: HandlerContext,
) -> Dict[str, Any]:
    """Execute a list of tool steps sequentially over a single device connection context.
    
    Aborts sequence immediately if any step fails.
    """
    if not isinstance(steps, list) or len(steps) == 0:
        raise UsageError("Batch execution requires a non-empty list of steps")

    step_results = []
    aborted = False
    abort_reason: Optional[Dict[str, Any]] = None

    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            raise UsageError(f"Step at index {i} must be a JSON object with 'tool' and 'args'")

        tool_name = step.get("tool")
        if not tool_name or not isinstance(tool_name, str):
            raise UsageError(f"Step at index {i} missing valid 'tool' string")

        args = step.get("args", {})
        if not isinstance(args, dict):
            raise UsageError(f"Step at index {i} 'args' must be an object")

        spec = registry.get_tool(tool_name)
        if not spec:
            raise UsageError(f"Tool '{tool_name}' at step index {i} not found in registry")

        start_time = time.time()
        try:
            # Validate input schema
            try:
                jsonschema.validate(instance=args, schema=spec.input_schema)
            except jsonschema.exceptions.ValidationError as e:
                raise UsageError(f"Invalid arguments for {tool_name} at step {i}: {e.message}")

            # Execute handler
            res = spec.handler(ctx, args)

            # Validate output schema
            try:
                jsonschema.validate(instance=res, schema=spec.output_schema)
            except jsonschema.exceptions.ValidationError as e:
                raise InternalError(f"Handler output for {tool_name} at step {i} failed schema validation: {e.message}")

            # Verify postcondition
            registry.verify_postcondition(ctx, spec, res)

            duration = round(time.time() - start_time, 3)
            step_results.append({
                "step_index": i,
                "tool": tool_name,
                "duration_sec": duration,
                "result": res,
            })

        except U2CtlError as err:
            duration = round(time.time() - start_time, 3)
            aborted = True
            abort_reason = {
                "step_index": i,
                "tool": tool_name,
                "duration_sec": duration,
                "error": err.to_dict(),
            }
            break
        except Exception as exc:
            duration = round(time.time() - start_time, 3)
            aborted = True
            err = InternalError(f"Unexpected internal error at step {i} ({tool_name}): {exc}")
            abort_reason = {
                "step_index": i,
                "tool": tool_name,
                "duration_sec": duration,
                "error": err.to_dict(),
            }
            break

    output: Dict[str, Any] = {
        "completed_steps": len(step_results),
        "total_steps": len(steps),
        "aborted": aborted,
        "step_results": step_results,
    }
    if abort_reason:
        output["failed_step"] = abort_reason

    return output
