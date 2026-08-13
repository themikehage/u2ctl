"""Unit tests for config resolution precedence."""

import os
import pytest
from u2ctl.config import resolve_config, Config
from u2ctl.errors import UsageError


def test_config_defaults(monkeypatch):
    monkeypatch.delenv("U2CTL_SERIAL", raising=False)
    monkeypatch.delenv("ANDROID_SERIAL", raising=False)
    monkeypatch.delenv("U2CTL_TIMEOUT", raising=False)
    monkeypatch.delenv("U2CTL_JSON", raising=False)
    monkeypatch.delenv("U2CTL_SAFETY", raising=False)

    cfg = resolve_config()
    assert cfg.serial is None
    assert cfg.timeout == 30
    assert cfg.json_output is False
    assert cfg.safety_ceiling == "interactive"


def test_config_env_override(monkeypatch):
    monkeypatch.setenv("U2CTL_SERIAL", "device123")
    monkeypatch.setenv("U2CTL_TIMEOUT", "60")
    monkeypatch.setenv("U2CTL_JSON", "1")
    monkeypatch.setenv("U2CTL_SAFETY", "read")

    cfg = resolve_config()
    assert cfg.serial == "device123"
    assert cfg.timeout == 60
    assert cfg.json_output is True
    assert cfg.safety_ceiling == "read"


def test_config_cli_flags_win_over_env(monkeypatch):
    monkeypatch.setenv("U2CTL_SERIAL", "env_device")
    monkeypatch.setenv("U2CTL_TIMEOUT", "60")

    cfg = resolve_config({"serial": "cli_device", "timeout": 15, "json": True})
    assert cfg.serial == "cli_device"
    assert cfg.timeout == 15
    assert cfg.json_output is True


def test_config_invalid_safety_raises_usage(monkeypatch):
    monkeypatch.setenv("U2CTL_SAFETY", "invalid_safety")
    with pytest.raises(UsageError):
        resolve_config()
