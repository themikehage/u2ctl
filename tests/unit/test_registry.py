"""Unit tests for registry rules and tool spec validation."""

import pytest
from u2ctl.registry import Registry, DomainSpec, ToolSpec
from u2ctl.errors import UsageError


def dummy_handler(ctx, args):
    return {"status": "ok"}


def test_macro_domain_reservation():
    reg = Registry()
    dom = DomainSpec(name="macro", description="Macro domain", tools=[])
    with pytest.raises(UsageError, match="reserved"):
        reg.register_domain(dom)


def test_tool_name_prefix_validation():
    reg = Registry()
    tool = ToolSpec(
        name="other.tool",
        domain="device",
        description="test",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        handler=dummy_handler,
    )
    dom = DomainSpec(name="device", description="Device domain", tools=[tool])
    with pytest.raises(UsageError, match="must start with domain prefix"):
        reg.register_domain(dom)


def test_mutation_tool_requires_expect():
    reg = Registry()
    tool = ToolSpec(
        name="device.action",
        domain="device",
        description="test mutation",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        handler=dummy_handler,
        safety="interactive",
        expect=None,  # Missing expect!
    )
    dom = DomainSpec(name="device", description="Device domain", tools=[tool])
    with pytest.raises(UsageError, match="must declare an 'expect'"):
        reg.register_domain(dom)
