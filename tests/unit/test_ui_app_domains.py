"""Unit tests for App and UI domains, parser, and resolver."""

import pytest
import json
from unittest.mock import MagicMock
from u2ctl.models import DeviceInfo, ActionElement
from u2ctl.errors import UsageError, SelectorNotFoundError, AppNotFoundError
from u2ctl.selectors.parser import parse_selector_args
from u2ctl.selectors.resolver import resolve_selector, rect_overlap_ratio
from u2ctl.domains.ui import parse_xml_dump, compute_screen_fingerprint


SAMPLE_XML = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<hierarchy rotation="0">
  <node index="0" text="" resource-id="" class="android.widget.FrameLayout" bounds="[0,0][1080,2340]">
    <node index="0" text="Battery" resource-id="com.android.settings:id/title" class="android.widget.TextView" bounds="[100,200][500,300]" clickable="true" focused="false" />
    <node index="1" text="Wi-Fi" resource-id="com.android.settings:id/wifi" class="android.widget.TextView" bounds="[100,400][500,500]" clickable="true" focused="true" />
    <node index="2" text="" resource-id="com.android.systemui:id/status_bar" class="android.widget.View" bounds="[0,0][1080,80]" />
  </node>
</hierarchy>
"""


def test_parse_selector_args():
    parsed = parse_selector_args({"text": "Hello"})
    assert parsed["text"] == "Hello"

    parsed_b = parse_selector_args({"bounds": "10,20-100,200"})
    assert parsed_b["bounds"] == [10, 20, 100, 200]

    with pytest.raises(UsageError):
        parse_selector_args({})


def test_parse_xml_dump_and_fingerprint():
    elements = parse_xml_dump(SAMPLE_XML, include_system_bars=False)
    assert len(elements) == 2  # systemui status bar dropped by default
    assert elements[0].text == "Battery"
    assert elements[1].text == "Wi-Fi"

    fingerprint = compute_screen_fingerprint(elements)
    assert len(fingerprint) == 16


def test_resolve_selector_priority_and_ambiguity():
    elements = parse_xml_dump(SAMPLE_XML, include_system_bars=True)

    # 1. Exact text match
    elem, warnings = resolve_selector(elements, {"text": "Battery"})
    assert elem.text == "Battery"
    assert len(warnings) == 0

    # 2. Strict selector failure on missing
    with pytest.raises(SelectorNotFoundError):
        resolve_selector(elements, {"text": "NonExistent"}, strict_selector=True)


def test_rect_overlap_ratio():
    r1 = (0, 0, 100, 100)
    r2 = (0, 0, 100, 100)
    assert rect_overlap_ratio(r1, r2) == 1.0

    r3 = (200, 200, 300, 300)
    assert rect_overlap_ratio(r1, r3) == 0.0


def test_app_current_handler(invoke_cli, monkeypatch):
    target = DeviceInfo(serial="dev1", state="device")
    monkeypatch.setattr("u2ctl.runtime.device.select_target_device", lambda s, a=None: (target, [target]))

    mock_u2 = MagicMock()
    mock_u2.app_current.return_value = {"package": "com.android.settings", "activity": ".Settings"}
    monkeypatch.setattr("uiautomator2.connect", lambda s: mock_u2)

    code, stdout, stderr = invoke_cli(["app", "current", "--json"])
    assert code == 0
    data = json.loads(stdout)
    assert data["result"]["package"] == "com.android.settings"


def test_app_start_handler(invoke_cli, monkeypatch):
    target = DeviceInfo(serial="dev1", state="device")
    monkeypatch.setattr("u2ctl.runtime.device.select_target_device", lambda s, a=None: (target, [target]))
    monkeypatch.setenv("U2CTL_SAFETY", "interactive")

    mock_u2 = MagicMock()
    mock_u2.app_current.return_value = {"package": "com.android.settings"}
    monkeypatch.setattr("uiautomator2.connect", lambda s: mock_u2)

    code, stdout, stderr = invoke_cli(["app", "start", "--package", "com.android.settings", "--json"])
    assert code == 0
    data = json.loads(stdout)
    assert data["result"]["package"] == "com.android.settings"


def test_ui_dump_handler(invoke_cli, monkeypatch):
    target = DeviceInfo(serial="dev1", state="device")
    monkeypatch.setattr("u2ctl.runtime.device.select_target_device", lambda s, a=None: (target, [target]))

    mock_u2 = MagicMock()
    mock_u2.dump_hierarchy.return_value = SAMPLE_XML
    monkeypatch.setattr("uiautomator2.connect", lambda s: mock_u2)

    code, stdout, stderr = invoke_cli(["ui", "dump", "--json"])
    assert code == 0
    data = json.loads(stdout)
    assert "screen_fingerprint" in data["result"]
    assert len(data["result"]["elements"]) == 2


def test_ui_tap_handler(invoke_cli, monkeypatch):
    target = DeviceInfo(serial="dev1", state="device")
    monkeypatch.setattr("u2ctl.runtime.device.select_target_device", lambda s, a=None: (target, [target]))
    monkeypatch.setenv("U2CTL_SAFETY", "interactive")

    mock_u2 = MagicMock()
    mock_u2.dump_hierarchy.return_value = SAMPLE_XML
    monkeypatch.setattr("uiautomator2.connect", lambda s: mock_u2)

    code, stdout, stderr = invoke_cli(["ui", "tap", "--text", "Battery", "--json"])
    assert code == 0
    data = json.loads(stdout)
    assert data["result"]["element"]["text"] == "Battery"
    assert mock_u2.click.called


def test_ui_input_handler(invoke_cli, monkeypatch):
    target = DeviceInfo(serial="dev1", state="device")
    monkeypatch.setattr("u2ctl.runtime.device.select_target_device", lambda s, a=None: (target, [target]))
    monkeypatch.setenv("U2CTL_SAFETY", "interactive")

    mock_u2 = MagicMock()
    monkeypatch.setattr("uiautomator2.connect", lambda s: mock_u2)

    code, stdout, stderr = invoke_cli(["ui", "input", "--text", "Hello World 123", "--json"])
    assert code == 0
    data = json.loads(stdout)
    assert data["result"]["text_typed"] == "Hello World 123"
    assert mock_u2.send_keys.called


def test_ui_swipe_handler(invoke_cli, monkeypatch):
    target = DeviceInfo(serial="dev1", state="device")
    monkeypatch.setattr("u2ctl.runtime.device.select_target_device", lambda s, a=None: (target, [target]))
    monkeypatch.setenv("U2CTL_SAFETY", "interactive")

    mock_u2 = MagicMock()
    mock_u2.dump_hierarchy.return_value = SAMPLE_XML
    monkeypatch.setattr("uiautomator2.connect", lambda s: mock_u2)

    code, stdout, stderr = invoke_cli(["ui", "swipe", "--from-pos", "500,1000", "--to-pos", "500,200", "--json"])
    assert code == 0
    data = json.loads(stdout)
    assert data["result"]["swiped"] is True


def test_ui_press_handler(invoke_cli, monkeypatch):
    target = DeviceInfo(serial="dev1", state="device")
    monkeypatch.setattr("u2ctl.runtime.device.select_target_device", lambda s, a=None: (target, [target]))
    monkeypatch.setenv("U2CTL_SAFETY", "interactive")

    mock_u2 = MagicMock()
    mock_u2.dump_hierarchy.return_value = SAMPLE_XML
    monkeypatch.setattr("uiautomator2.connect", lambda s: mock_u2)

    code, stdout, stderr = invoke_cli(["ui", "press", "--key", "home", "--json"])
    assert code == 0
    data = json.loads(stdout)
    assert data["result"]["key"] == "home"
    assert mock_u2.press.called


def test_ui_wait_handler_success(invoke_cli, monkeypatch):
    target = DeviceInfo(serial="dev1", state="device")
    monkeypatch.setattr("u2ctl.runtime.device.select_target_device", lambda s, a=None: (target, [target]))

    mock_u2 = MagicMock()
    mock_u2.dump_hierarchy.return_value = SAMPLE_XML
    monkeypatch.setattr("uiautomator2.connect", lambda s: mock_u2)

    code, stdout, stderr = invoke_cli(["ui", "wait", "--text", "Battery", "--timeout", "2", "--json"])
    assert code == 0
    data = json.loads(stdout)
    assert data["result"]["satisfied"] is True
    assert data["result"]["element"]["text"] == "Battery"
