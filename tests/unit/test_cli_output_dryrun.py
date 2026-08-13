"""Unit tests for CLI execution options (dry-run, quiet, human output)."""

import json
from unittest.mock import MagicMock
from u2ctl.models import DeviceInfo


def test_cli_dry_run(invoke_cli, monkeypatch):
    monkeypatch.setenv("U2CTL_SAFETY", "interactive")
    code, stdout, stderr = invoke_cli(["setup", "install", "--dry-run", "--json"])
    assert code == 0
    data = json.loads(stdout)
    assert data["result"]["dry_run"] is True
    assert data["result"]["would_execute"] == "setup.install"
    assert "[audit]" not in stderr  # dry-run does not emit audit line


def test_cli_human_output(invoke_cli, monkeypatch):
    report_dict = {"status": "ready", "steps": []}
    monkeypatch.setattr("u2ctl.domains.setup.verify_setup", lambda serial=None, adb_path=None: MagicMock(to_dict=lambda: report_dict))

    code, stdout, stderr = invoke_cli(["setup", "verify"])
    assert code == 0
    assert "OK (setup.verify):" in stdout
    assert '"status": "ready"' in stdout


def test_device_reconnect_execution(invoke_cli, monkeypatch):
    target = DeviceInfo(serial="dev1", state="device")
    monkeypatch.setattr("u2ctl.domains.device.select_target_device", lambda s, a=None: (target, [target]))
    monkeypatch.setattr("u2ctl.domains.device.reconnect_device", lambda serial, hard, adb_path=None: "reconnected ok")
    monkeypatch.setenv("U2CTL_SAFETY", "destructive")

    code, stdout, stderr = invoke_cli(["device", "reconnect", "--yes", "--json"])
    assert code == 0
    data = json.loads(stdout)
    assert data["result"]["reconnected"] is True
    assert data["result"]["message"] == "reconnected ok"
    assert "[audit] device.reconnect" in stderr
