"""Setup domain capability definitions."""

from typing import Dict, Any
from u2ctl.registry import ToolSpec, DomainSpec, HandlerContext
from u2ctl.runtime.provisioning import verify_setup, install_setup, diagnose_setup


def setup_verify_handler(ctx: HandlerContext, args: Dict[str, Any]) -> Dict[str, Any]:
    report = verify_setup(serial=ctx.serial)
    return report.to_dict()


def setup_install_handler(ctx: HandlerContext, args: Dict[str, Any]) -> Dict[str, Any]:
    keep_awake = args.get("keep_awake", False)
    report = install_setup(serial=ctx.serial, keep_awake=keep_awake)
    return report.to_dict()


def setup_diagnose_handler(ctx: HandlerContext, args: Dict[str, Any]) -> Dict[str, Any]:
    evidence = diagnose_setup(serial=ctx.serial)
    return {"diagnostics": evidence}


SETUP_DOMAIN = DomainSpec(
    name="setup",
    description="Provisioning and runtime verification commands",
    tools=[
        ToolSpec(
            name="setup.verify",
            domain="setup",
            description="Read-only verification of device readiness.",
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
            output_schema={
                "type": "object",
                "required": ["status", "steps"],
                "properties": {
                    "status": {"type": "string"},
                    "steps": {"type": "array"},
                },
            },
            handler=setup_verify_handler,
            safety="read",
        ),
        ToolSpec(
            name="setup.install",
            domain="setup",
            description="Provision device runtime, input helper, and optional stay-awake settings.",
            input_schema={
                "type": "object",
                "properties": {
                    "keep_awake": {"type": "boolean", "description": "Apply stayon settings for long unattended runs"},
                },
                "additionalProperties": False,
            },
            output_schema={
                "type": "object",
                "required": ["status", "steps"],
                "properties": {
                    "status": {"type": "string"},
                    "steps": {"type": "array"},
                },
            },
            handler=setup_install_handler,
            safety="interactive",
            idempotent=True,
            expect={"schema": {"type": "object", "required": ["status"]}},
        ),
        ToolSpec(
            name="setup.diagnose",
            domain="setup",
            description="Collect evidence for failing setup steps without modifying device state.",
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
            output_schema={
                "type": "object",
                "required": ["diagnostics"],
                "properties": {
                    "diagnostics": {"type": "object"},
                },
            },
            handler=setup_diagnose_handler,
            safety="read",
        ),
    ],
)
