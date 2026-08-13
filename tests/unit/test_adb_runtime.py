"""Unit tests for ADB selection logic and recovery."""

import pytest
from unittest.mock import MagicMock
from u2ctl.models import DeviceInfo
from u2ctl.errors import (
    DeviceNoneError,
    DeviceAmbiguousError,
    DeviceNotFoundError,
    DeviceUnauthorizedError,
    DeviceOfflineError,
)
from u2ctl.runtime.adb import select_target_device, reconnect_device


def test_select_target_device_none(monkeypatch):
    monkeypatch.setattr("u2ctl.runtime.adb.list_adb_devices", lambda adb_path=None: [])
    with pytest.raises(DeviceNoneError):
        select_target_device()


def test_select_target_device_ambiguous(monkeypatch):
    devs = [
        DeviceInfo(serial="dev1", state="device"),
        DeviceInfo(serial="dev2", state="device"),
    ]
    monkeypatch.setattr("u2ctl.runtime.adb.list_adb_devices", lambda adb_path=None: devs)
    with pytest.raises(DeviceAmbiguousError):
        select_target_device()


def test_select_target_device_not_found(monkeypatch):
    devs = [DeviceInfo(serial="dev1", state="device")]
    monkeypatch.setattr("u2ctl.runtime.adb.list_adb_devices", lambda adb_path=None: devs)
    with pytest.raises(DeviceNotFoundError):
        select_target_device("non_existent_serial")


def test_select_target_device_unauthorized(monkeypatch):
    devs = [DeviceInfo(serial="dev1", state="unauthorized")]
    monkeypatch.setattr("u2ctl.runtime.adb.list_adb_devices", lambda adb_path=None: devs)
    with pytest.raises(DeviceUnauthorizedError):
        select_target_device("dev1")


def test_select_target_device_offline(monkeypatch):
    devs = [DeviceInfo(serial="dev1", state="offline")]
    monkeypatch.setattr("u2ctl.runtime.adb.list_adb_devices", lambda adb_path=None: devs)
    with pytest.raises(DeviceOfflineError):
        select_target_device("dev1")


def test_reconnect_device_soft(monkeypatch):
    mock_run = MagicMock()
    mock_run.return_value.stdout = "reconnected"
    monkeypatch.setattr("subprocess.run", mock_run)
    msg = reconnect_device("dev1", hard=False)
    assert "reconnected" in msg


def test_reconnect_device_hard(monkeypatch):
    mock_run = MagicMock()
    monkeypatch.setattr("subprocess.run", mock_run)
    msg = reconnect_device("dev1", hard=True)
    assert "Hard reconnect performed" in msg
