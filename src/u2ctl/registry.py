"""Capability registry, ToolSpec definitions, and CLI argument parsing generation."""

import argparse
from dataclasses import dataclass, field
from typing import Callable, Dict, Any, List, Optional
import jsonschema

from u2ctl.errors import UsageError, InternalError, PostconditionFailedError


@dataclass
class HandlerContext:
    device: Any = None
    serial: str = ""
    timeout: int = 30
    warnings: List[str] = field(default_factory=list)
    client: Any = None

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def call_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """Intra-command delegation for composite tools or macro execution."""
        spec = registry.get_tool(tool_name)
        if not spec:
            raise InternalError(f"Delegated tool '{tool_name}' not found in registry")
        # Validate args
        jsonschema.validate(instance=kwargs, schema=spec.input_schema)
        res = spec.handler(self, kwargs)
        jsonschema.validate(instance=res, schema=spec.output_schema)
        return res


@dataclass
class ToolSpec:
    name: str
    domain: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    handler: Callable[[HandlerContext, Dict[str, Any]], Dict[str, Any]]
    safety: str = "read"  # read, interactive, destructive
    idempotent: bool = True
    requires: List[str] = field(default_factory=list)
    expect: Optional[Dict[str, Any]] = None


@dataclass
class DomainSpec:
    name: str
    description: str
    tools: List[ToolSpec]


class Registry:
    def __init__(self):
        self._domains: Dict[str, DomainSpec] = {}
        self._tools: Dict[str, ToolSpec] = {}

    def register_domain(self, domain: DomainSpec) -> None:
        if domain.name == "macro":
            raise UsageError("Domain name 'macro' is reserved and cannot be registered in MVP")

        for tool in domain.tools:
            self._validate_tool_spec(domain, tool)
            self._tools[tool.name] = tool
        self._domains[domain.name] = domain

    def _validate_tool_spec(self, domain: DomainSpec, tool: ToolSpec) -> None:
        if tool.name.startswith("macro."):
            raise UsageError(f"Tool '{tool.name}' is reserved for future macro domain")

        expected_prefix = f"{domain.name}."
        if not tool.name.startswith(expected_prefix):
            raise UsageError(f"Tool name '{tool.name}' must start with domain prefix '{expected_prefix}'")

        if tool.name in self._tools:
            raise UsageError(f"Duplicate tool registration: '{tool.name}'")

        if tool.safety not in {"read", "interactive", "destructive"}:
            raise UsageError(f"Invalid safety class '{tool.safety}' for tool '{tool.name}'")

        if tool.safety in {"interactive", "destructive"} and tool.expect is None:
            raise UsageError(f"Mutation tool '{tool.name}' ({tool.safety}) must declare an 'expect' postcondition contract")

        if not callable(tool.handler):
            raise UsageError(f"Handler for tool '{tool.name}' is not callable")

        try:
            jsonschema.Draft202012Validator.check_schema(tool.input_schema)
            jsonschema.Draft202012Validator.check_schema(tool.output_schema)
        except jsonschema.exceptions.SchemaError as e:
            raise UsageError(f"Invalid JSON Schema for tool '{tool.name}': {e}")

    def get_tool(self, name: str) -> Optional[ToolSpec]:
        return self._tools.get(name)

    def get_domain(self, name: str) -> Optional[DomainSpec]:
        return self._domains.get(name)

    def list_domains(self) -> List[DomainSpec]:
        return list(self._domains.values())

    def list_tools(self) -> List[ToolSpec]:
        return list(self._tools.values())

    def verify_postcondition(self, ctx: HandlerContext, tool: ToolSpec, result: Dict[str, Any]) -> None:
        """Verify declarative postcondition contract declared on ToolSpec."""
        if not tool.expect:
            return

        if "schema" in tool.expect:
            try:
                jsonschema.validate(instance=result, schema=tool.expect["schema"])
            except jsonschema.exceptions.ValidationError as e:
                raise PostconditionFailedError(f"Postcondition schema validation failed: {e.message}")

        if "element" in tool.expect:
            # Check element status if postcondition element reported in result
            elem_cond = tool.expect["element"]
            state_cond = tool.expect.get("state", "exists")
            postcond_res = result.get("postcondition", {})
            if state_cond == "exists" and not postcond_res.get("satisfied", True):
                raise PostconditionFailedError(f"Postcondition failed: expected element matching {elem_cond} to exist")

    def build_cli_parser(self, main_parser: argparse.ArgumentParser, parent_parser: Optional[argparse.ArgumentParser] = None) -> None:
        parents = [parent_parser] if parent_parser else []
        subparsers = main_parser.add_subparsers(dest="_cli_domain", help="Available domains")
        subparsers.required = False

        for domain in self._domains.values():
            dom_parser = subparsers.add_parser(domain.name, help=domain.description, parents=parents)
            tool_subparsers = dom_parser.add_subparsers(dest="_cli_tool", help=f"Commands for {domain.name}")
            tool_subparsers.required = False

            for tool in domain.tools:
                tool_subcommand = tool.name.split(".", 1)[1]
                t_parser = tool_subparsers.add_parser(tool_subcommand, help=tool.description, parents=parents)

                # Generate args from input_schema
                self._build_tool_arguments(t_parser, tool)

    def _build_tool_arguments(self, parser: argparse.ArgumentParser, tool: ToolSpec) -> None:
        schema = tool.input_schema
        properties = schema.get("properties", {})
        required = set(schema.get("required", []))

        for prop_name, prop_spec in properties.items():
            kebab_name = prop_name.replace("_", "-")
            flag_name = f"--{kebab_name}"
            prop_type = prop_spec.get("type", "string")
            help_text = prop_spec.get("description", "")
            enum_vals = prop_spec.get("enum")

            kwargs: Dict[str, Any] = {"help": help_text}

            if enum_vals:
                kwargs["choices"] = enum_vals

            if prop_type == "boolean":
                parser.add_argument(flag_name, action=argparse.BooleanOptionalAction, default=None, help=help_text)
            elif prop_type == "integer":
                kwargs["type"] = int
                if prop_name in required:
                    kwargs["required"] = True
                parser.add_argument(flag_name, **kwargs)
            elif prop_type == "number":
                kwargs["type"] = float
                if prop_name in required:
                    kwargs["required"] = True
                parser.add_argument(flag_name, **kwargs)
            elif prop_type == "array":
                kwargs["nargs"] = "+"
                if prop_name in required:
                    kwargs["required"] = True
                parser.add_argument(flag_name, **kwargs)
            else:  # string
                kwargs["type"] = str
                if prop_name in required:
                    kwargs["required"] = True
                parser.add_argument(flag_name, **kwargs)


registry = Registry()
