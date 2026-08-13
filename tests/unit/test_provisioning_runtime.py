"""Unit tests for provisioning and setup functions."""

import pytest
from unittest.mock import MagicMock
from u2ctl.models import DeviceInfo
from u2ctl.errors import ProvisionBlockedError, ProvisionFailedError
from u2ctl.runtime.provisioning import verify_setup, install_setup, diagnose_setup


def test_verify_setup_success(monkeypatch):
    target = DeviceInfo(serial="dev1", state="device")
    monkeypatch.setattr("u2ctl.runtime.provisioning.select_target_device", lambda s, a=None: (target, [target]))

    mock_run = MagicMock()
    mock_run.return_value.stdout = "ro.build.version.sdk: 31\ncom.github.uiautomator"
    monkeypatch.setattr("subprocess.run", mock_run)

    mock_u2 = MagicMock()
    mock_u2.connect.return_value.info = {"screenOn": True}
    monkeypatch.setitem(__import__("sys").modules, "uiautomator2", mock_u2)

    report = verify_setup("dev1")
    assert report.status == "ready"
    assert len(report.steps) == 4


def test_install_setup_success(monkeypatch):
    target = DeviceInfo(serial="dev1", state="device")
    monkeypatch.setattr("u2ctl.runtime.provisioning.select_target_device", lambda s, a=None: (target, [target]))

    mock_run = MagicMock()
    monkeypatch.setattr("subprocess.run", mock_run)

    mock_u2 = MagicMock()
    mock_u2.connect.return_value.info = {"screenOn": True}
    monkeypatch.setitem(__import__("sys").modules, "uiautomator2", mock_u2)

    report = install_setup("dev1", keep_awake=True)
    assert report.status == "ready"


def test_install_setup_blocked_by_xiaomi(monkeypatch):
    target = DeviceInfo(serial="dev1", state="device")
    monkeypatch.setattr("u2ctl.runtime.provisioning.select_target_device", lambda s, a=None: (target, [target]))

    mock_u2 = MagicMock()
    mock_u2.connect.side_effect = Exception("INSTALL_FAILED_USER_RESTRICTED: User denied installation")
    monkeypatch.setitem(__import__("sys").modules, "uiautomator2", mock_u2)

    with pytest.raises(ProvisionBlockedError) as exc_info:
        install_setup("dev1")
    assert "INSTALL_FAILED_USER_RESTRICTED" in str(exc_info.value)


def test_diagnose_setup(monkeypatch):
    target = DeviceInfo(serial="dev1", state="device", model="Mi9")
    monkeypatch.setattr("u2ctl.runtime.provisioning.select_target_device", lambda s, a=None: (target, [target]))

    mock_run = MagicMock()
    mock_run.return_value.stdout = "[ro.build.version.sdk]: [31]\n[ro.product.model]: [Mi9]\n"
    monkeypatch.setattr("subprocess.run", mock_run)

    diag = diagnose_setup("dev1")
    assert diag["serial"] == "dev1"
    assert "props_sample" in diag
