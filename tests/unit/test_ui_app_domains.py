"""Comprehensive unit tests for App and UI domains, selector parser, and resolver."""

import pytest
import json
from unittest.mock import MagicMock
from u2ctl.models import DeviceInfo, ActionElement
from u2ctl.errors import UsageError, SelectorNotFoundError, AppNotFoundError, TimeoutError
from u2ctl.selectors.parser import parse_selector_args
from u2ctl.selectors.resolver import resolve_selector, rect_overlap_ratio
from u2ctl.domains.ui import parse_xml_dump, compute_screen_fingerprint


SAMPLE_XML = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<hierarchy rotation="0">
  <node index="0" text="" resource-id="" class="android.widget.FrameLayout" bounds="[0,0][1080,2340]">
    <node index="0" text="Battery" resource-id="com.android.settings:id/title" class="android.widget.TextView" bounds="[100,200][500,300]" clickable="true" focused="false" />
    <node index="1" text="Wi-Fi" resource-id="com.android.settings:id/wifi" class="android.widget.TextView" bounds="[100,400][500,500]" clickable="true" focused="true" />
    <node index="2" text="DupText" resource-id="com.android.settings:id/dup" class="android.widget.Button" bounds="[100,600][500,700]" clickable="true" focused="false" />
    <node index="3" text="DupText" resource-id="com.android.settings:id/dup" class="android.widget.Button" bounds="[100,600][500,700]" clickable="true" focused="false" />
    <node index="4" text="" resource-id="com.android.systemui:id/status_bar" class="android.widget.View" bounds="[0,0][1080,80]" />
  </node>
</hierarchy>
"""


def test_parse_selector_args_all_forms():
    # Direct flags
    assert parse_selector_args({"resource_id": "btn_id"}) == {"resource_id": "btn_id"}
    assert parse_selector_args({"description": "btn_desc"}) == {"description": "btn_desc"}
    assert parse_selector_args({"bounds": "[10,20][100,200]"}) == {"bounds": [10, 20, 100, 200]}

    # Selector string prefixes
    assert parse_selector_args({"selector": "text:Hello"}) == {"text": "Hello"}
    assert parse_selector_args({"selector": "resourceId:com.app:id/btn"}) == {"resource_id": "com.app:id/btn"}
    assert parse_selector_args({"selector": "desc:MyDesc"}) == {"description": "MyDesc"}
    assert parse_selector_args({"selector": "bounds:10,20-100,200"}) == {"bounds": [10, 20, 100, 200]}
    assert parse_selector_args({"selector": "FallbackText"}) == {"text": "FallbackText"}

    # Invalid bounds
    with pytest.raises(UsageError):
        parse_selector_args({"bounds": "invalid_bounds"})
    with pytest.raises(UsageError):
        parse_selector_args({"selector": "bounds:invalid"})


def test_parse_xml_dump_dedup_and_system_bars():
    elements = parse_xml_dump(SAMPLE_XML, include_system_bars=False)
    # 2 distinct + 1 deduped (DupText counted once with duplicates=1)
    assert len(elements) == 3
    dup_elem = [e for e in elements if e.text == "DupText"][0]
    assert dup_elem.duplicates == 1


def test_resolve_selector_strict_mode_and_ambiguity():
    elements = parse_xml_dump(SAMPLE_XML, include_system_bars=True)

    # Priority 1: resource_id
    elem, _ = resolve_selector(elements, {"resource_id": "com.android.settings:id/title"})
    assert elem.text == "Battery"

    # Priority 2: content_desc (none matched -> exception)
    with pytest.raises(SelectorNotFoundError):
        resolve_selector(elements, {"description": "non_existent"})

    # Priority 3: bounds
    elem_b, _ = resolve_selector(elements, {"bounds": [100, 200, 500, 300]})
    assert elem_b.text == "Battery"

    # Multiple matches warning & strict failure
    matched_elements = [
        ActionElement(index=0, text="Same", resource_id="id1", content_desc="", class_name="btn", bounds="[0,0][100,100]", clickable=True, scrollable=False, focused=False),
        ActionElement(index=1, text="Same", resource_id="id2", content_desc="", class_name="btn", bounds="[10,10][200,200]", clickable=True, scrollable=False, focused=False),
    ]

    elem_warn, warnings = resolve_selector(matched_elements, {"text": "Same"}, strict_selector=False)
    assert elem_warn.index == 0
    assert len(warnings) == 1
    assert "SELECTOR_MATCHED_MULTIPLE" in warnings[0]

    with pytest.raises(SelectorNotFoundError):
        resolve_selector(matched_elements, {"text": "Same"}, strict_selector=True)


def test_app_stop_handler(invoke_cli, monkeypatch):
    target = DeviceInfo(serial="dev1", state="device")
    monkeypatch.setattr("u2ctl.runtime.device.select_target_device", lambda s, a=None: (target, [target]))
    monkeypatch.setenv("U2CTL_SAFETY", "interactive")

    mock_u2 = MagicMock()
    mock_u2.app_current.return_value = {"package": "com.android.settings"}
    monkeypatch.setattr("uiautomator2.connect", lambda s: mock_u2)

    code, stdout, stderr = invoke_cli(["app", "stop", "--package", "com.android.settings", "--json"])
    assert code == 0
    data = json.loads(stdout)
    assert data["result"]["stopped"] is True
    assert mock_u2.app_stop.called


def test_ui_wait_absent_and_timeout(invoke_cli, monkeypatch):
    target = DeviceInfo(serial="dev1", state="device")
    monkeypatch.setattr("u2ctl.runtime.device.select_target_device", lambda s, a=None: (target, [target]))

    mock_u2 = MagicMock()
    mock_u2.dump_hierarchy.return_value = SAMPLE_XML
    monkeypatch.setattr("uiautomator2.connect", lambda s: mock_u2)

    # Wait absent when element does not exist -> satisfied immediately
    code, stdout, stderr = invoke_cli(["ui", "wait", "--text", "NonExistentElement", "--absent", "--timeout", "1", "--json"])
    assert code == 0
    data = json.loads(stdout)
    assert data["result"]["satisfied"] is True
    assert data["result"]["element"] is None

    # Wait present when element never appears -> timeout error
    code_t, stdout_t, stderr_t = invoke_cli(["ui", "wait", "--text", "NeverAppears", "--timeout", "1", "--json"])
    assert code_t == 5  # TimeoutError exit code
    data_t = json.loads(stdout_t)
    assert data_t["error"]["code"] == "TIMEOUT"
