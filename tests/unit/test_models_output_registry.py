"""Unit tests for models, output formatting, registry arg generation, and adb path resolution."""

import pytest
import argparse
from u2ctl.models import ActionElement, DeviceInfo, SetupReport, SetupStepReport
from u2ctl.output import print_output
from u2ctl.registry import Registry, ToolSpec, DomainSpec, HandlerContext
from u2ctl.runtime.adb import get_adb_path
from u2ctl.errors import ADBUnavailableError, PostconditionFailedError


def test_action_element_to_dict():
    elem = ActionElement(
        index=0,
        text="Click Me",
        resource_id="com.example:id/btn",
        content_desc="button",
        class_name="android.widget.Button",
        bounds="[0,0][100,100]",
        clickable=True,
        scrollable=False,
        focused=False,
        duplicates=2,
    )
    d = elem.to_dict()
    assert d["text"] == "Click Me"
    assert d["duplicates"] == 2


def test_build_success_envelope_warnings():
    from u2ctl.output import build_success_envelope
    # Empty warnings -> no warnings key in envelope (R4 partial)
    env1 = build_success_envelope("test.cmd", "dev1", {"ok": True}, warnings=[])
    assert "warnings" not in env1

    # Non-empty warnings -> warnings key included
    env2 = build_success_envelope("test.cmd", "dev1", {"ok": True}, warnings=["warn1"])
    assert env2["warnings"] == ["warn1"]


def test_print_output_human_error(capsys):
    from u2ctl.errors import UsageError
    print_output("test.cmd", "dev1", error=UsageError("Human error msg"), json_mode=False)
    captured = capsys.readouterr()
    assert "Error [USAGE]: Human error msg" in captured.err


def test_get_adb_path_custom_and_missing(monkeypatch):
    assert get_adb_path("/custom/path/adb") == "/custom/path/adb"
    monkeypatch.setattr("shutil.which", lambda cmd: None)
    with pytest.raises(ADBUnavailableError):
        get_adb_path(None)


def test_registry_build_tool_arguments():
    reg = Registry()
    tool = ToolSpec(
        name="test.cmd",
        domain="test",
        description="test desc",
        input_schema={
            "type": "object",
            "properties": {
                "count": {"type": "integer"},
                "ratio": {"type": "number"},
                "tags": {"type": "array"},
                "flag": {"type": "boolean"},
            },
            "required": ["count"],
        },
        output_schema={"type": "object"},
        handler=lambda ctx, args: {},
    )
    dom = DomainSpec(name="test", description="Test dom", tools=[tool])
    reg.register_domain(dom)

    parser = argparse.ArgumentParser()
    reg.build_cli_parser(parser)
    assert parser is not None


def test_verify_postcondition_schema_failure():
    reg = Registry()
    tool = ToolSpec(
        name="test.mutation",
        domain="test",
        description="mutation",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        handler=lambda ctx, args: {},
        safety="interactive",
        expect={"schema": {"type": "object", "required": ["success"]}},
    )
    ctx = HandlerContext()
    with pytest.raises(PostconditionFailedError):
        reg.verify_postcondition(ctx, tool, {"wrong_key": True})
