"""App domain capability definitions."""

import time
from typing import Dict, Any
from u2ctl.errors import AppNotFoundError
from u2ctl.registry import ToolSpec, DomainSpec, HandlerContext
from u2ctl.runtime.device import DeviceSession


def app_current_handler(ctx: HandlerContext, args: Dict[str, Any]) -> Dict[str, Any]:
    session = DeviceSession(serial=ctx.serial, timeout=ctx.timeout)
    d = session.u2
    ctx.serial = session.serial
    app_info = d.app_current()
    return {
        "package": app_info.get("package", ""),
        "activity": app_info.get("activity", ""),
    }


def app_start_handler(ctx: HandlerContext, args: Dict[str, Any]) -> Dict[str, Any]:
    pkg = args["package"]
    session = DeviceSession(serial=ctx.serial, timeout=ctx.timeout)
    d = session.u2
    ctx.serial = session.serial

    current_before = d.app_current().get("package", "")
    try:
        d.app_start(pkg)
    except Exception as e:
        raise AppNotFoundError(f"Failed to start package '{pkg}': {e}")

    time.sleep(1.0)
    current_after = d.app_current().get("package", "")

    return {
        "package": pkg,
        "prior_package": current_before,
        "foreground_package": current_after,
        "postcondition": {
            "satisfied": current_after == pkg,
            "expected_package": pkg,
            "actual_package": current_after,
        },
    }


def app_stop_handler(ctx: HandlerContext, args: Dict[str, Any]) -> Dict[str, Any]:
    pkg = args["package"]
    session = DeviceSession(serial=ctx.serial, timeout=ctx.timeout)
    d = session.u2
    ctx.serial = session.serial

    current_before = d.app_current().get("package", "")
    d.app_stop(pkg)
    time.sleep(0.5)

    return {
        "package": pkg,
        "prior_package": current_before,
        "stopped": True,
    }


APP_DOMAIN = DomainSpec(
    name="app",
    description="Application lifecycle commands",
    tools=[
        ToolSpec(
            name="app.current",
            domain="app",
            description="Get currently displayed foreground application and activity.",
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
            output_schema={
                "type": "object",
                "required": ["package", "activity"],
                "properties": {
                    "package": {"type": "string"},
                    "activity": {"type": "string"},
                },
            },
            handler=app_current_handler,
            safety="read",
        ),
        ToolSpec(
            name="app.start",
            domain="app",
            description="Launch application package and verify foreground postcondition.",
            input_schema={
                "type": "object",
                "properties": {
                    "package": {"type": "string", "description": "Android package name (e.g. com.android.settings)"},
                },
                "required": ["package"],
                "additionalProperties": False,
            },
            output_schema={
                "type": "object",
                "required": ["package", "foreground_package"],
                "properties": {
                    "package": {"type": "string"},
                    "prior_package": {"type": "string"},
                    "foreground_package": {"type": "string"},
                    "postcondition": {"type": "object"},
                },
            },
            handler=app_start_handler,
            safety="interactive",
            idempotent=True,
            expect={"schema": {"type": "object", "required": ["package"]}},
        ),
        ToolSpec(
            name="app.stop",
            domain="app",
            description="Force-stop application package.",
            input_schema={
                "type": "object",
                "properties": {
                    "package": {"type": "string", "description": "Android package name to stop"},
                },
                "required": ["package"],
                "additionalProperties": False,
            },
            output_schema={
                "type": "object",
                "required": ["package", "stopped"],
                "properties": {
                    "package": {"type": "string"},
                    "prior_package": {"type": "string"},
                    "stopped": {"type": "boolean"},
                },
            },
            handler=app_stop_handler,
            safety="interactive",
            idempotent=True,
            expect={"schema": {"type": "object", "required": ["stopped"]}},
        ),
    ],
)
