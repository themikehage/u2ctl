"""Contract tests for CLI output envelopes, introspection, and schema generation."""

import json
from u2ctl.domains import init_domains
from u2ctl.registry import registry


def test_tools_list_contract(invoke_cli):
    code, stdout, stderr = invoke_cli(["tools", "list", "--json"])
    assert code == 0
    data = json.loads(stdout)
    assert data["schema_version"] == "1"
    assert data["ok"] is True
    assert data["command"] == "tools.list"
    assert "result" in data
    assert "tools" in data["result"]

    tool_names = [t["name"] for t in data["result"]["tools"]]
    assert "device.list" in tool_names
    assert "setup.verify" in tool_names
    assert "tools.schema" in tool_names


def test_tools_schema_openai_contract(invoke_cli):
    code, stdout, stderr = invoke_cli(["tools", "schema", "--format", "openai", "--json"])
    assert code == 0
    data = json.loads(stdout)
    assert data["ok"] is True
    result = data["result"]
    assert result["format"] == "openai"
    caps = result["capabilities"]
    assert len(caps) > 0
    for cap in caps:
        assert cap["type"] == "function"
        assert "name" in cap["function"]
        assert "parameters" in cap["function"]


def test_safety_ceiling_blocks_mutation(invoke_cli, monkeypatch):
    monkeypatch.setenv("U2CTL_SAFETY", "read")
    code, stdout, stderr = invoke_cli(["setup", "install", "--json"])
    assert code == 1  # UsageError exit code
    data = json.loads(stdout)
    assert data["ok"] is False
    assert data["error"]["code"] == "USAGE"
    assert "environment safety ceiling" in data["error"]["message"]


def test_destructive_requires_yes_flag(invoke_cli, monkeypatch):
    monkeypatch.setenv("U2CTL_SAFETY", "destructive")
    code, stdout, stderr = invoke_cli(["device", "reconnect", "--hard", "--json"])
    assert code == 1
    data = json.loads(stdout)
    assert data["ok"] is False
    assert data["error"]["code"] == "USAGE"
    assert "requires explicit confirmation '--yes'" in data["error"]["message"]
