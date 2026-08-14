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
    assert parse_selector_args({"text_contains": "bat"}) == {"text_contains": "bat"}
    assert parse_selector_args({"desc_contains": "desc_sub"}) == {"desc_contains": "desc_sub"}
    assert parse_selector_args({"bounds": "[10,20][100,200]"}) == {"bounds": [10, 20, 100, 200]}

    # Selector string prefixes
    assert parse_selector_args({"selector": "text:Hello"}) == {"text": "Hello"}
    assert parse_selector_args({"selector": "textContains:hell"}) == {"text_contains": "hell"}
    assert parse_selector_args({"selector": "resourceId:com.app:id/btn"}) == {"resource_id": "com.app:id/btn"}
    assert parse_selector_args({"selector": "desc:MyDesc"}) == {"description": "MyDesc"}
    assert parse_selector_args({"selector": "descContains:mydesc"}) == {"desc_contains": "mydesc"}
    assert parse_selector_args({"selector": "bounds:10,20-100,200"}) == {"bounds": [10, 20, 100, 200]}
    assert parse_selector_args({"selector": "FallbackText"}) == {"text": "FallbackText"}

    # Invalid bounds
    with pytest.raises(UsageError):
        parse_selector_args({"bounds": "invalid_bounds"})
    with pytest.raises(UsageError):
        parse_selector_args({"selector": "bounds:invalid"})


def test_parse_xml_dump_dedup_and_system_bars():
    elements = parse_xml_dump(SAMPLE_XML, include_system_bars=False)
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

    # Substring matching
    elem_sub, _ = resolve_selector(elements, {"text_contains": "att"})
    assert elem_sub.text == "Battery"

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


def test_rect_overlap_ratio():
    r1 = (0, 0, 100, 100)
    r2 = (0, 0, 100, 100)
    assert rect_overlap_ratio(r1, r2) == 1.0


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
    assert len(data["result"]["elements"]) == 3


def test_ui_dump_filter_actionable_flag(invoke_cli, monkeypatch):
    target = DeviceInfo(serial="dev1", state="device")
    monkeypatch.setattr("u2ctl.runtime.device.select_target_device", lambda s, a=None: (target, [target]))

    mock_u2 = MagicMock()
    mock_u2.dump_hierarchy.return_value = SAMPLE_XML
    monkeypatch.setattr("uiautomator2.connect", lambda s: mock_u2)

    code, stdout, stderr = invoke_cli(["ui", "dump", "--filter", "actionable", "--json"])
    assert code == 0
    data = json.loads(stdout)
    assert data["result"]["total_actionable"] == 3

    code_bad, stdout_bad, stderr_bad = invoke_cli(["ui", "dump", "--filter", "everything", "--json"])
    assert code_bad == 2  # argparse rejects values outside the enum
    assert "invalid choice" in stderr_bad


def test_ui_tap_handler(invoke_cli, monkeypatch):
    target = DeviceInfo(serial="dev1", state="device")
    monkeypatch.setattr("u2ctl.runtime.device.select_target_device", lambda s, a=None: (target, [target]))
    monkeypatch.setenv("U2CTL_SAFETY", "interactive")

    mock_u2 = MagicMock()
    mock_u2.dump_hierarchy.return_value = SAMPLE_XML
    monkeypatch.setattr("uiautomator2.connect", lambda s: mock_u2)

    # Standard tap returns postcondition without full element payload
    code, stdout, stderr = invoke_cli(["ui", "tap", "--text", "Battery"])
    assert code == 0
    data = json.loads(stdout)
    assert "postcondition" in data["result"]
    assert "screen_fingerprint" in data["result"]["postcondition"]
    assert mock_u2.click.called

    # Debug mode returns full element payload
    code_dbg, stdout_dbg, _ = invoke_cli(["ui", "tap", "--text", "Battery", "--debug"])
    assert code_dbg == 0
    data_dbg = json.loads(stdout_dbg)
    assert data_dbg["result"]["element"]["text"] == "Battery"


def test_ui_scroll_handler(invoke_cli, monkeypatch):
    target = DeviceInfo(serial="dev1", state="device")
    monkeypatch.setattr("u2ctl.runtime.device.select_target_device", lambda s, a=None: (target, [target]))
    monkeypatch.setenv("U2CTL_SAFETY", "interactive")

    mock_u2 = MagicMock()
    mock_u2.window_size.return_value = (1080, 2340)
    mock_u2.dump_hierarchy.return_value = SAMPLE_XML
    monkeypatch.setattr("uiautomator2.connect", lambda s: mock_u2)

    code, stdout, _ = invoke_cli(["ui", "scroll", "--direction", "down"])
    assert code == 0
    data = json.loads(stdout)
    assert data["result"]["swiped"] is True
    assert data["result"]["direction"] == "down"
    assert "screen_fingerprint" in data["result"]
    assert mock_u2.swipe.called


def test_ui_type_handler(invoke_cli, monkeypatch):
    target = DeviceInfo(serial="dev1", state="device")
    monkeypatch.setattr("u2ctl.runtime.device.select_target_device", lambda s, a=None: (target, [target]))
    monkeypatch.setenv("U2CTL_SAFETY", "interactive")

    mock_u2 = MagicMock()
    mock_u2.dump_hierarchy.return_value = SAMPLE_XML
    monkeypatch.setattr("uiautomator2.connect", lambda s: mock_u2)

    code, stdout, _ = invoke_cli(["ui", "type", "--text-contains", "Battery", "--text", "TypedSearchText"])
    assert code == 0
    data = json.loads(stdout)
    assert data["result"]["text_typed"] == "TypedSearchText"
    assert "screen_fingerprint" in data["result"]
    assert mock_u2.send_keys.called


def test_parse_xml_dump_filters_ime_and_systemui():
    xml_with_ime = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
    <hierarchy rotation="0">
        <node index="0" text="App Button" resource-id="com.app:id/btn" class="android.widget.Button" bounds="[0,0][100,100]" clickable="true" />
        <node index="1" text="Key q" resource-id="com.google.android.inputmethod.latin:id/key_pos" package="com.google.android.inputmethod.latin" class="android.widget.TextView" bounds="[0,500][50,600]" clickable="true" />
        <node index="2" text="System Bar" resource-id="com.android.systemui:id/bar" class="android.widget.View" bounds="[0,0][1080,80]" />
    </hierarchy>"""

    filtered = parse_xml_dump(xml_with_ime, include_system_bars=False)
    assert len(filtered) == 1
    assert filtered[0].text == "App Button"

    unfiltered = parse_xml_dump(xml_with_ime, include_system_bars=True)
    assert len(unfiltered) == 3


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


def test_bounds_selector_prefers_smaller_specific_rect():
    large_scroll = ActionElement(
        index=0, text="", resource_id="com.app:id/scroll", content_desc="",
        class_name="android.widget.ScrollView", bounds="[0,0][1080,2340]",
        clickable=True, scrollable=True, focused=False
    )
    small_cell = ActionElement(
        index=1, text="Cell Text", resource_id="com.app:id/cell", content_desc="",
        class_name="android.widget.TextView", bounds="[100,200][500,300]",
        clickable=True, scrollable=False, focused=False
    )
    # Order in hierarchy puts large ScrollView first
    elements = [large_scroll, small_cell]
    resolved, _ = resolve_selector(elements, {"bounds": [100, 200, 500, 300]})
    assert resolved.resource_id == "com.app:id/cell"


def test_parse_xml_dump_includes_content_desc_non_clickable():
    xml_with_desc = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
    <hierarchy rotation="0">
        <node index="0" text="" resource-id="com.app:id/reaction" class="android.view.View" package="com.app"
              content-desc="Reaction button state" bounds="[10,10][100,100]" checkable="false" checked="false"
              clickable="false" enabled="true" focusable="false" focused="false" scrollable="false"
              long-clickable="false" password="false" selected="false" visible-to-user="true" />
    </hierarchy>"""
    elements = parse_xml_dump(xml_with_desc)
    assert len(elements) == 1
    assert elements[0].content_desc == "Reaction button state"


def test_parse_xml_dump_include_containers():
    xml_container = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
    <hierarchy rotation="0">
        <node index="0" text="" resource-id="com.app:id/container" class="android.widget.FrameLayout" bounds="[0,0][100,100]" clickable="false" scrollable="false" />
    </hierarchy>"""
    elements_default = parse_xml_dump(xml_container, include_containers=False)
    assert len(elements_default) == 0

    elements_with_containers = parse_xml_dump(xml_container, include_containers=True)
    assert len(elements_with_containers) == 1
    assert elements_with_containers[0].resource_id == "com.app:id/container"


def test_ui_tap_postcondition_includes_fingerprint_transition(invoke_cli, monkeypatch):
    target = DeviceInfo(serial="dev1", state="device")
    monkeypatch.setattr("u2ctl.runtime.device.select_target_device", lambda s, a=None: (target, [target]))
    monkeypatch.setenv("U2CTL_SAFETY", "interactive")

    mock_u2 = MagicMock()
    mock_u2.dump_hierarchy.return_value = SAMPLE_XML
    monkeypatch.setattr("uiautomator2.connect", lambda s: mock_u2)

    # Without --debug flag: fingerprints omitted by default (R7)
    code, stdout, stderr = invoke_cli(["ui", "tap", "--text", "Battery", "--json"])
    assert code == 0
    data = json.loads(stdout)
    postcond = data["result"]["postcondition"]
    assert "screen_changed" in postcond
    assert "pre_fingerprint" not in postcond
    assert "post_fingerprint" not in postcond

    # With --debug flag: fingerprints included
    code_dbg, stdout_dbg, _ = invoke_cli(["ui", "tap", "--text", "Battery", "--debug", "--json"])
    assert code_dbg == 0
    data_dbg = json.loads(stdout_dbg)
    postcond_dbg = data_dbg["result"]["postcondition"]
    assert "screen_changed" in postcond_dbg
    assert "pre_fingerprint" in postcond_dbg
    assert "post_fingerprint" in postcond_dbg


def test_ui_tap_expect_postcondition(invoke_cli, monkeypatch):
    target = DeviceInfo(serial="dev1", state="device")
    monkeypatch.setattr("u2ctl.runtime.device.select_target_device", lambda s, a=None: (target, [target]))
    monkeypatch.setenv("U2CTL_SAFETY", "interactive")

    mock_u2 = MagicMock()
    mock_u2.dump_hierarchy.return_value = SAMPLE_XML
    monkeypatch.setattr("uiautomator2.connect", lambda s: mock_u2)

    # Expect satisfied
    code, stdout, _ = invoke_cli(["ui", "tap", "--text", "Battery", "--expect-text-contains", "Wi-Fi", "--json"])
    assert code == 0
    data = json.loads(stdout)
    postcond = data["result"]["postcondition"]
    assert postcond["expect_satisfied"] is True
    assert postcond["matched_element"]["text"] == "Wi-Fi"

    # Expect not satisfied (exit code 0, expect_satisfied False)
    code_f, stdout_f, _ = invoke_cli(["ui", "tap", "--text", "Battery", "--expect-text-contains", "NonExistent", "--json"])
    assert code_f == 0
    data_f = json.loads(stdout_f)
    postcond_f = data_f["result"]["postcondition"]
    assert postcond_f["expect_satisfied"] is False
    assert "matched_element" not in postcond_f

    # Expect element absent
    code_a, stdout_a, _ = invoke_cli(["ui", "tap", "--text", "Battery", "--expect-text-contains", "NonExistent", "--expect-element-absent", "--json"])
    assert code_a == 0
    data_a = json.loads(stdout_a)
    postcond_a = data_a["result"]["postcondition"]
    assert postcond_a["expect_satisfied"] is True


def test_ui_dump_server_side_filter_and_compact(invoke_cli, monkeypatch):
    target = DeviceInfo(serial="dev1", state="device")
    monkeypatch.setattr("u2ctl.runtime.device.select_target_device", lambda s, a=None: (target, [target]))

    mock_u2 = MagicMock()
    mock_u2.dump_hierarchy.return_value = SAMPLE_XML
    monkeypatch.setattr("uiautomator2.connect", lambda s: mock_u2)

    # Filter text_contains
    code, stdout, _ = invoke_cli(["ui", "dump", "--text-contains", "Wi-Fi", "--json"])
    assert code == 0
    data = json.loads(stdout)
    assert data["result"]["matched"] == 1
    assert len(data["result"]["elements"]) == 1
    assert data["result"]["elements"][0]["text"] == "Wi-Fi"

    # Compact mode
    code_c, stdout_c, _ = invoke_cli(["ui", "dump", "--text-contains", "Battery", "--compact", "--json"])
    assert code_c == 0
    data_c = json.loads(stdout_c)
    elem = data_c["result"]["elements"][0]
    assert elem["text"] == "Battery"
    assert "focused" not in elem  # focused is False, omitted in compact mode
    assert "scrollable" not in elem  # scrollable is False, omitted in compact mode


def test_ui_long_press_handler(invoke_cli, monkeypatch):
    target = DeviceInfo(serial="dev1", state="device")
    monkeypatch.setattr("u2ctl.runtime.device.select_target_device", lambda s, a=None: (target, [target]))
    monkeypatch.setenv("U2CTL_SAFETY", "interactive")

    mock_u2 = MagicMock()
    mock_u2.dump_hierarchy.return_value = SAMPLE_XML
    monkeypatch.setattr("uiautomator2.connect", lambda s: mock_u2)

    code, stdout, stderr = invoke_cli(["ui", "long-press", "--text", "Battery", "--duration", "1.5", "--debug"])
    assert code == 0
    data = json.loads(stdout)
    assert data["result"]["element"]["text"] == "Battery"
    assert data["result"]["duration"] == 1.5
    assert mock_u2.long_click.called


def test_ui_find_handler_found_immediately(invoke_cli, monkeypatch):
    target = DeviceInfo(serial="dev1", state="device")
    monkeypatch.setattr("u2ctl.runtime.device.select_target_device", lambda s, a=None: (target, [target]))

    mock_u2 = MagicMock()
    mock_u2.dump_hierarchy.return_value = SAMPLE_XML
    monkeypatch.setattr("uiautomator2.connect", lambda s: mock_u2)

    code, stdout, stderr = invoke_cli(["ui", "find", "--text-contains", "Bat", "--json"])
    assert code == 0
    data = json.loads(stdout)
    assert data["result"]["found"] is True
    assert data["result"]["scrolls_performed"] == 0
    assert data["result"]["element"]["text"] == "Battery"


def test_ui_find_handler_not_found(invoke_cli, monkeypatch):
    target = DeviceInfo(serial="dev1", state="device")
    monkeypatch.setattr("u2ctl.runtime.device.select_target_device", lambda s, a=None: (target, [target]))

    mock_u2 = MagicMock()
    mock_u2.dump_hierarchy.return_value = SAMPLE_XML
    mock_u2.window_size.return_value = (1080, 2340)
    monkeypatch.setattr("uiautomator2.connect", lambda s: mock_u2)

    code, stdout, stderr = invoke_cli(["ui", "find", "--text-contains", "NonExistent", "--max-scrolls", "2", "--json"])
    assert code == 0
    data = json.loads(stdout)
    assert data["result"]["found"] is False
    assert data["result"]["scrolls_performed"] == 2
    assert data["result"]["element"] is None
    assert mock_u2.swipe.call_count == 2

