"""Unit tests for domain handlers and fake runtime adapters."""

import pytest
import json
from unittest.mock import MagicMock

from u2ctl.models import DeviceInfo, SetupReport, SetupStepReport
from u2ctl.errors import DeviceNoneError, DeviceAmbiguousError, DeviceNotFoundError, ProvisionBlockedError


def test_device_list_handler(invoke_cli, monkeypatch):
    mock_devices = [
        DeviceInfo(serial="dev1", state="device", model="Mi9", transport="usb"),
        DeviceInfo(serial="dev2", state="device", model="Pixel", transport="wifi"),
    ]
    monkeypatch.setattr("u2ctl.domains.device.list_adb_devices", lambda adb_path=None: mock_devices)

    code, stdout, stderr = invoke_cli(["device", "list", "--json"])
    assert code == 0
    data = json.loads(stdout)
    assert len(data["result"]["devices"]) == 2
    assert data["result"]["devices"][0]["serial"] == "dev1"


def test_device_status_handler(invoke_cli, monkeypatch):
    target_device = DeviceInfo(serial="dev1", state="device", model="Mi9", transport="usb")
    monkeypatch.setattr("u2ctl.domains.device.select_target_device", lambda s, adb_path=None: (target_device, [target_device]))

    code, stdout, stderr = invoke_cli(["device", "status", "--json"])
    assert code == 0
    data = json.loads(stdout)
    assert data["result"]["serial"] == "dev1"
    assert data["result"]["state"] == "device"


def test_device_info_handler(invoke_cli, monkeypatch):
    target_device = DeviceInfo(serial="dev1", state="device", model="Mi9", transport="usb")
    monkeypatch.setattr("u2ctl.domains.device.select_target_device", lambda s, adb_path=None: (target_device, [target_device]))

    mock_u2_dev = MagicMock()
    mock_u2_dev.info = {
        "sdkInt": 31,
        "displayWidth": 1080,
        "displayHeight": 2340,
        "displayRotation": 0,
        "screenOn": True,
    }
    monkeypatch.setattr("uiautomator2.connect", lambda s: mock_u2_dev)

    code, stdout, stderr = invoke_cli(["device", "info", "--json"])
    assert code == 0
    data = json.loads(stdout)
    assert data["result"]["sdk_version"] == 31
    assert data["result"]["display_size"] == [1080, 2340]


def test_setup_verify_handler(invoke_cli, monkeypatch):
    report = SetupReport(status="ready", steps=[SetupStepReport(name="adb", status="already_present")])
    monkeypatch.setattr("u2ctl.domains.setup.verify_setup", lambda serial=None, adb_path=None: report)

    code, stdout, stderr = invoke_cli(["setup", "verify", "--json"])
    assert code == 0
    data = json.loads(stdout)
    assert data["result"]["status"] == "ready"


def test_setup_install_handler(invoke_cli, monkeypatch):
    report = SetupReport(status="ready", steps=[SetupStepReport(name="u2", status="installed")])
    monkeypatch.setattr("u2ctl.domains.setup.install_setup", lambda serial=None, keep_awake=False, adb_path=None: report)

    code, stdout, stderr = invoke_cli(["setup", "install", "--json"])
    assert code == 0
    data = json.loads(stdout)
    assert data["result"]["status"] == "ready"


def test_setup_diagnose_handler(invoke_cli, monkeypatch):
    monkeypatch.setattr("u2ctl.domains.setup.diagnose_setup", lambda serial=None, adb_path=None: {"sample": "ok"})

    code, stdout, stderr = invoke_cli(["setup", "diagnose", "--json"])
    assert code == 0
    data = json.loads(stdout)
    assert data["result"]["diagnostics"]["sample"] == "ok"


def test_tools_show_handler(invoke_cli):
    code, stdout, stderr = invoke_cli(["tools", "show", "--domain", "device", "--json"])
    assert code == 0
    data = json.loads(stdout)
    assert data["result"]["found"] is True
    assert data["result"]["domain"] == "device"
    assert len(data["result"]["tools"]) > 0
