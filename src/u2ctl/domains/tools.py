"""Tools domain capability definitions for capability catalog introspection."""

from typing import Dict, Any, List
from u2ctl.registry import registry, ToolSpec, DomainSpec, HandlerContext


def tools_list_handler(ctx: HandlerContext, args: Dict[str, Any]) -> Dict[str, Any]:
    tools = registry.list_tools()
    out = []
    for t in tools:
        out.append({
            "name": t.name,
            "domain": t.domain,
            "description": t.description,
            "safety": t.safety,
            "idempotent": t.idempotent,
        })
    return {"tools": out}


def tools_show_handler(ctx: HandlerContext, args: Dict[str, Any]) -> Dict[str, Any]:
    target_domain = args.get("domain")
    dom = registry.get_domain(target_domain or "")
    if not dom:
        return {"domain": target_domain, "found": False, "tools": []}

    tools_out = []
    for t in dom.tools:
        tools_out.append({
            "name": t.name,
            "description": t.description,
            "input_schema": t.input_schema,
            "output_schema": t.output_schema,
            "safety": t.safety,
            "idempotent": t.idempotent,
        })
    return {"domain": dom.name, "found": True, "description": dom.description, "tools": tools_out}


def tools_schema_handler(ctx: HandlerContext, args: Dict[str, Any]) -> Dict[str, Any]:
    fmt = args.get("format", "openai")
    tools = registry.list_tools()
    functions = []

    for t in tools:
        if fmt == "openai":
            functions.append({
                "type": "function",
                "function": {
                    "name": t.name.replace(".", "_"),
                    "description": f"[{t.name}] {t.description}",
                    "parameters": t.input_schema,
                },
            })
        else:
            functions.append({
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
            })

    return {"format": fmt, "capabilities": functions}


TOOLS_DOMAIN = DomainSpec(
    name="tools",
    description="Introspection and schema discovery for capability catalog",
    tools=[
        ToolSpec(
            name="tools.list",
            domain="tools",
            description="List all registered CLI tools and their safety classes.",
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
            output_schema={
                "type": "object",
                "required": ["tools"],
                "properties": {
                    "tools": {"type": "array"},
                },
            },
            handler=tools_list_handler,
            safety="read",
        ),
        ToolSpec(
            name="tools.show",
            domain="tools",
            description="Show complete schemas and metadata for a specific domain.",
            input_schema={
                "type": "object",
                "properties": {
                    "domain": {"type": "string", "description": "Target domain name (e.g. device, setup)"},
                },
                "required": ["domain"],
                "additionalProperties": False,
            },
            output_schema={
                "type": "object",
                "required": ["domain", "found"],
                "properties": {
                    "domain": {"type": "string"},
                    "found": {"type": "boolean"},
                    "description": {"type": "string"},
                    "tools": {"type": "array"},
                },
            },
            handler=tools_show_handler,
            safety="read",
        ),
        ToolSpec(
            name="tools.schema",
            domain="tools",
            description="Export standard OpenAI-compatible function-calling JSON schemas.",
            input_schema={
                "type": "object",
                "properties": {
                    "format": {
                        "type": "string",
                        "enum": ["openai", "raw"],
                        "description": "Export format style",
                    },
                },
                "additionalProperties": False,
            },
            output_schema={
                "type": "object",
                "required": ["format", "capabilities"],
                "properties": {
                    "format": {"type": "string"},
                    "capabilities": {"type": "array"},
                },
            },
            handler=tools_schema_handler,
            safety="read",
        ),
    ],
)
