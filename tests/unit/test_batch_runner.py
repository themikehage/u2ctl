"""Unit tests for batch execution mode (u2ctl run)."""

import json
import pytest
from unittest.mock import MagicMock

from u2ctl.models import DeviceInfo

SAMPLE_XML = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<hierarchy rotation="0">
  <node index="0" text="Battery" resource-id="com.android.settings:id/title" class="android.widget.TextView" bounds="[100,200][500,300]" clickable="true" />
</hierarchy>
"""


def test_batch_runner_success(invoke_cli, monkeypatch):
    target = DeviceInfo(serial="dev1", state="device")
    monkeypatch.setattr("u2ctl.runtime.device.select_target_device", lambda s, a=None: (target, [target]))
    monkeypatch.setenv("U2CTL_SAFETY", "interactive")

    mock_u2 = MagicMock()
    mock_u2.dump_hierarchy.return_value = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
    <hierarchy rotation="0">
      <node index="0" text="Battery" resource-id="com.android.settings:id/title" class="android.widget.TextView" bounds="[100,200][500,300]" clickable="true" />
    </hierarchy>
    """
    mock_u2.app_current.return_value = {"package": "com.android.settings"}
    monkeypatch.setattr("uiautomator2.connect", lambda s: mock_u2)

    steps_json = json.dumps([
        {"tool": "app.current", "args": {}},
        {"tool": "ui.input", "args": {"text": "Hello Batch"}},
    ])

    code, stdout, stderr = invoke_cli(["run", "steps", "--steps", steps_json])
    assert code == 0
    data = json.loads(stdout)

    res = data["result"]
    assert res["completed_steps"] == 2
    assert res["total_steps"] == 2
    assert res["aborted"] is False
    assert len(res["step_results"]) == 2
    assert res["step_results"][0]["tool"] == "app.current"
    assert res["step_results"][1]["tool"] == "ui.input"


def test_batch_runner_aborts_on_step_failure(invoke_cli, monkeypatch):
    target = DeviceInfo(serial="dev1", state="device")
    monkeypatch.setattr("u2ctl.runtime.device.select_target_device", lambda s, a=None: (target, [target]))
    monkeypatch.setenv("U2CTL_SAFETY", "interactive")

    mock_u2 = MagicMock()
    mock_u2.dump_hierarchy.return_value = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
    <hierarchy rotation="0">
      <node index="0" text="Battery" resource-id="com.android.settings:id/title" class="android.widget.TextView" bounds="[100,200][500,300]" clickable="true" />
    </hierarchy>
    """
    mock_u2.app_current.return_value = {"package": "com.android.settings"}
    monkeypatch.setattr("uiautomator2.connect", lambda s: mock_u2)

    steps_json = json.dumps([
        {"tool": "app.current", "args": {}},
        {"tool": "ui.tap", "args": {"text": "NonExistentButton"}},  # fails selector match
        {"tool": "ui.input", "args": {"text": "ShouldNotBeReached"}},
    ])

def test_batch_runner_file_execution(invoke_cli, monkeypatch, tmp_path):
    target = DeviceInfo(serial="dev1", state="device")
    monkeypatch.setattr("u2ctl.runtime.device.select_target_device", lambda s, a=None: (target, [target]))
    monkeypatch.setenv("U2CTL_SAFETY", "interactive")

    mock_u2 = MagicMock()
    mock_u2.app_current.return_value = {"package": "com.android.settings"}
    monkeypatch.setattr("uiautomator2.connect", lambda s: mock_u2)

    batch_file = tmp_path / "steps.json"
    batch_file.write_text(json.dumps([
        {"tool": "app.current", "args": {}},
    ]), encoding="utf-8")

    code, stdout, stderr = invoke_cli(["run", "steps", "--file", str(batch_file)])
    assert code == 0
    data = json.loads(stdout)
    assert data["result"]["completed_steps"] == 1
    assert data["result"]["total_steps"] == 1


def test_batch_runner_invalid_inputs(invoke_cli):
    # Missing both flags
    code, stdout, stderr = invoke_cli(["run", "steps"])
    assert code == 1
    data = json.loads(stdout)
    assert "USAGE" in data["error"]["code"]

    # Both flags specified
    code, stdout, stderr = invoke_cli(["run", "steps", "--steps", "[]", "--file", "steps.json"])
    assert code == 1

    # File not found
    code, stdout, stderr = invoke_cli(["run", "steps", "--file", "non_existent_file.json"])
    assert code == 1

    # Invalid JSON string
    code, stdout, stderr = invoke_cli(["run", "steps", "--steps", "invalid_json"])
    assert code == 1


def test_device_session_auto_reconnect(monkeypatch):
    from u2ctl.runtime.device import DeviceSession
    from u2ctl.errors import DeviceOfflineError

    target = DeviceInfo(serial="dev1", state="device")
    monkeypatch.setattr("u2ctl.runtime.device.select_target_device", lambda s, a=None: (target, [target]))

    attempts = 0

    def mock_connect(serial):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise Exception("Connection reset")
        mock_d = MagicMock()
        mock_d.wait_timeout = 30
        return mock_d

    monkeypatch.setattr("uiautomator2.connect", mock_connect)

    session = DeviceSession(serial="dev1")
    d = session.connect()
    assert attempts == 2
    assert d is not None

