"""UI domain capability definitions for hierarchy dumping, interaction, and gestures."""

import hashlib
import time
from typing import Dict, Any, List, Optional, Tuple
import xml.etree.ElementTree as ET

from u2ctl.errors import UsageError, SelectorNotFoundError, TimeoutError
from u2ctl.models import ActionElement
from u2ctl.registry import ToolSpec, DomainSpec, HandlerContext
from u2ctl.runtime.device import DeviceSession
from u2ctl.selectors.parser import parse_selector_args
from u2ctl.selectors.resolver import resolve_selector, parse_bounds_rect, rect_overlap_ratio


ACTIONABLE_CLASSES = {
    "android.widget.Button",
    "android.widget.ImageButton",
    "android.widget.CheckBox",
    "android.widget.RadioButton",
    "android.widget.Switch",
    "android.widget.EditText",
    "Button",
    "ImageButton",
    "CheckBox",
    "RadioButton",
    "Switch",
    "EditText",
}


def compute_screen_fingerprint(elements: List[ActionElement]) -> str:
    """Compute stable screen fingerprint hash from sorted actionable element properties (G3/G12)."""
    raw_tuples = []
    for e in elements:
        raw_tuples.append((e.resource_id, e.text, e.content_desc, e.class_name, e.bounds))
    raw_tuples.sort()
    repr_str = "|".join(f"{r[0]}:{r[1]}:{r[2]}:{r[3]}:{r[4]}" for r in raw_tuples)
    return hashlib.sha256(repr_str.encode("utf-8")).hexdigest()[:16]


def parse_xml_dump(xml_content: str, include_system_bars: bool = False, include_containers: bool = False) -> List[ActionElement]:
    """Parse hierarchy XML and filter actionable elements (BUILDSPEC G3)."""
    elements = []
    if not xml_content:
        return elements

    try:
        root = ET.fromstring(xml_content)
    except Exception:
        return elements

    index_counter = 0
    for elem in root.iter():
        if elem.tag == "hierarchy":
            continue
        attrib = elem.attrib
        res_id = attrib.get("resource-id", "")
        text = attrib.get("text", "")
        desc = attrib.get("content-desc", "")
        cls_name = attrib.get("class", "")
        bounds = attrib.get("bounds", "")
        if not bounds:
            continue

        clickable = attrib.get("clickable", "false").lower() == "true"
        scrollable = attrib.get("scrollable", "false").lower() == "true"
        checkable = attrib.get("checkable", "false").lower() == "true"
        focused = attrib.get("focused", "false").lower() == "true"
        editable = attrib.get("focusable", "false").lower() == "true" and cls_name.endswith("EditText")

        # Exclude system chrome unless explicitly included (G3)
        if not include_system_bars:
            if res_id.startswith("com.android.systemui"):
                continue

        # Actionable filter rules
        is_actionable = (
            clickable
            or scrollable
            or checkable
            or focused
            or editable
            or (cls_name in ACTIONABLE_CLASSES)
            or (len(text) > 0 and len(text) <= 200)
            or (len(desc) > 0 and len(desc) <= 200)
        )

        if is_actionable or include_containers:
            elements.append(
                ActionElement(
                    index=index_counter,
                    text=text,
                    resource_id=res_id,
                    content_desc=desc,
                    class_name=cls_name,
                    bounds=bounds,
                    clickable=clickable,
                    scrollable=scrollable,
                    focused=focused,
                )
            )
            index_counter += 1

    # Deduplicate elements overlapping >= 90%
    deduped: List[ActionElement] = []
    for e in elements:
        b = parse_bounds_rect(e.bounds)
        duplicate_found = False
        if b:
            for existing in deduped:
                eb = parse_bounds_rect(existing.bounds)
                if (
                    eb
                    and existing.text == e.text
                    and existing.resource_id == e.resource_id
                    and existing.content_desc == e.content_desc
                    and existing.class_name == e.class_name
                    and rect_overlap_ratio(b, eb) >= 0.9
                ):
                    existing.duplicates += 1
                    duplicate_found = True
                    break
        if not duplicate_found:
            deduped.append(e)

    # Re-index
    for i, e in enumerate(deduped):
        e.index = i

    return deduped


def ui_dump_handler(ctx: HandlerContext, args: Dict[str, Any]) -> Dict[str, Any]:
    session = DeviceSession(serial=ctx.serial, timeout=ctx.timeout)
    d = session.u2
    ctx.serial = session.serial

    limit = args.get("limit", 30)
    raw = args.get("raw", False)
    include_system_bars = args.get("include_system_bars", False)
    include_containers = args.get("include_containers", False)

    xml_content = d.dump_hierarchy()

    if raw:
        return {"raw_xml": xml_content}

    elements = parse_xml_dump(xml_content, include_system_bars=include_system_bars, include_containers=include_containers)
    fingerprint = compute_screen_fingerprint(elements)

    out_elements = elements if limit == 0 else elements[:limit]

    return {
        "screen_fingerprint": fingerprint,
        "total_actionable": len(elements),
        "limit": limit,
        "elements": [e.to_dict() for e in out_elements],
    }


def ui_tap_handler(ctx: HandlerContext, args: Dict[str, Any]) -> Dict[str, Any]:
    selector = parse_selector_args(args)
    session = DeviceSession(serial=ctx.serial, timeout=ctx.timeout)
    d = session.u2
    ctx.serial = session.serial

    xml_content = d.dump_hierarchy()
    elements = parse_xml_dump(xml_content, include_system_bars=True)
    pre_fingerprint = compute_screen_fingerprint(elements)

    target_elem, warnings = resolve_selector(elements, selector)
    for w in warnings:
        ctx.warn(w)

    bounds = parse_bounds_rect(target_elem.bounds)
    if bounds:
        cx = (bounds[0] + bounds[2]) // 2
        cy = (bounds[1] + bounds[3]) // 2
        d.click(cx, cy)
    else:
        # Fallback click via u2 selector
        if "text" in selector:
            d(text=selector["text"]).click()
        elif "text_contains" in selector:
            d(textContains=selector["text_contains"]).click()
        elif "resource_id" in selector:
            d(resourceId=selector["resource_id"]).click()
        elif "description" in selector:
            d(description=selector["description"]).click()
        elif "desc_contains" in selector:
            d(descriptionContains=selector["desc_contains"]).click()

    time.sleep(0.5)

    # Postcondition check (G6)
    post_xml = d.dump_hierarchy()
    post_elements = parse_xml_dump(post_xml, include_system_bars=True)
    post_fingerprint = compute_screen_fingerprint(post_elements)

    return {
        "element": target_elem.to_dict(),
        "bounds": target_elem.bounds,
        "postcondition": {
            "screen_changed": pre_fingerprint != post_fingerprint,
            "pre_fingerprint": pre_fingerprint,
            "post_fingerprint": post_fingerprint,
        },
    }


def ui_long_press_handler(ctx: HandlerContext, args: Dict[str, Any]) -> Dict[str, Any]:
    selector = parse_selector_args(args)
    duration = args.get("duration", 1.0)
    session = DeviceSession(serial=ctx.serial, timeout=ctx.timeout)
    d = session.u2
    ctx.serial = session.serial

    xml_content = d.dump_hierarchy()
    elements = parse_xml_dump(xml_content, include_system_bars=True)
    pre_fingerprint = compute_screen_fingerprint(elements)

    target_elem, warnings = resolve_selector(elements, selector)
    for w in warnings:
        ctx.warn(w)

    bounds = parse_bounds_rect(target_elem.bounds)
    if bounds:
        cx = (bounds[0] + bounds[2]) // 2
        cy = (bounds[1] + bounds[3]) // 2
        d.long_click(cx, cy, duration=duration)
    else:
        if "text" in selector:
            d(text=selector["text"]).long_click(duration=duration)
        elif "text_contains" in selector:
            d(textContains=selector["text_contains"]).long_click(duration=duration)
        elif "resource_id" in selector:
            d(resourceId=selector["resource_id"]).long_click(duration=duration)
        elif "description" in selector:
            d(description=selector["description"]).long_click(duration=duration)
        elif "desc_contains" in selector:
            d(descriptionContains=selector["desc_contains"]).long_click(duration=duration)

    time.sleep(0.5)

    post_xml = d.dump_hierarchy()
    post_elements = parse_xml_dump(post_xml, include_system_bars=True)
    post_fingerprint = compute_screen_fingerprint(post_elements)

    return {
        "element": target_elem.to_dict(),
        "bounds": target_elem.bounds,
        "duration": duration,
        "postcondition": {
            "screen_changed": pre_fingerprint != post_fingerprint,
            "pre_fingerprint": pre_fingerprint,
            "post_fingerprint": post_fingerprint,
        },
    }


def ui_input_handler(ctx: HandlerContext, args: Dict[str, Any]) -> Dict[str, Any]:
    text_to_type = args["text"]
    session = DeviceSession(serial=ctx.serial, timeout=ctx.timeout)
    d = session.u2
    ctx.serial = session.serial

    d.send_keys(text_to_type)

    return {
        "text_typed": text_to_type,
        "postcondition": {"satisfied": True},
    }


def ui_swipe_handler(ctx: HandlerContext, args: Dict[str, Any]) -> Dict[str, Any]:
    from_pos = args["from_pos"]  # "X1,Y1"
    to_pos = args["to_pos"]      # "X2,Y2"
    duration = args.get("duration", 0.2)

    fx, fy = map(int, from_pos.replace(" ", "").split(","))
    tx, ty = map(int, to_pos.replace(" ", "").split(","))

    session = DeviceSession(serial=ctx.serial, timeout=ctx.timeout)
    d = session.u2
    ctx.serial = session.serial

    d.swipe(fx, fy, tx, ty, duration=duration)
    time.sleep(0.5)

    post_xml = d.dump_hierarchy()
    post_elements = parse_xml_dump(post_xml)
    fingerprint = compute_screen_fingerprint(post_elements)

    return {
        "swiped": True,
        "from": [fx, fy],
        "to": [tx, ty],
        "duration": duration,
        "screen_fingerprint": fingerprint,
    }


def ui_press_handler(ctx: HandlerContext, args: Dict[str, Any]) -> Dict[str, Any]:
    key = args["key"]
    session = DeviceSession(serial=ctx.serial, timeout=ctx.timeout)
    d = session.u2
    ctx.serial = session.serial

    d.press(key)
    time.sleep(0.5)

    post_xml = d.dump_hierarchy()
    post_elements = parse_xml_dump(post_xml)
    fingerprint = compute_screen_fingerprint(post_elements)

    return {
        "key": key,
        "screen_fingerprint": fingerprint,
    }


def ui_wait_handler(ctx: HandlerContext, args: Dict[str, Any]) -> Dict[str, Any]:
    selector = parse_selector_args(args)
    timeout_sec = min(args.get("timeout", ctx.timeout), 120)
    absent = args.get("absent", False)

    session = DeviceSession(serial=ctx.serial, timeout=ctx.timeout)
    d = session.u2
    ctx.serial = session.serial

    start_time = time.time()
    while time.time() - start_time < timeout_sec:
        xml = d.dump_hierarchy()
        elements = parse_xml_dump(xml, include_system_bars=True)
        try:
            matched, _ = resolve_selector(elements, selector)
            if not absent:
                return {
                    "waited_seconds": round(time.time() - start_time, 2),
                    "satisfied": True,
                    "element": matched.to_dict(),
                }
        except SelectorNotFoundError:
            if absent:
                return {
                    "waited_seconds": round(time.time() - start_time, 2),
                    "satisfied": True,
                    "element": None,
                }
        time.sleep(0.5)

    raise TimeoutError(f"Wait timed out after {timeout_sec}s for selector {selector}")


def ui_find_handler(ctx: HandlerContext, args: Dict[str, Any]) -> Dict[str, Any]:
    selector = parse_selector_args(args)
    scroll_direction = args.get("scroll_direction", "down")
    max_scrolls = min(args.get("max_scrolls", 10), 30)
    scroll_duration = args.get("scroll_duration", 0.3)

    session = DeviceSession(serial=ctx.serial, timeout=ctx.timeout)
    d = session.u2
    ctx.serial = session.serial

    try:
        w_info = d.window_size()
        width = w_info[0] if isinstance(w_info, tuple) else w_info.get("width", 1080)
        height = w_info[1] if isinstance(w_info, tuple) else w_info.get("height", 2340)
    except Exception:
        width, height = 1080, 2340

    scrolls_performed = 0

    while True:
        xml_content = d.dump_hierarchy()
        elements = parse_xml_dump(xml_content)
        fingerprint = compute_screen_fingerprint(elements)

        try:
            target_elem, _ = resolve_selector(elements, selector)
            return {
                "found": True,
                "element": target_elem.to_dict(),
                "scrolls_performed": scrolls_performed,
                "screen_fingerprint": fingerprint,
            }
        except SelectorNotFoundError:
            if scrolls_performed >= max_scrolls:
                return {
                    "found": False,
                    "element": None,
                    "scrolls_performed": scrolls_performed,
                    "screen_fingerprint": fingerprint,
                }

            if scroll_direction == "down":
                fx, fy = width // 2, int(height * 0.75)
                tx, ty = width // 2, int(height * 0.25)
            elif scroll_direction == "up":
                fx, fy = width // 2, int(height * 0.25)
                tx, ty = width // 2, int(height * 0.75)
            elif scroll_direction == "left":
                fx, fy = int(width * 0.85), height // 2
                tx, ty = int(width * 0.15), height // 2
            elif scroll_direction == "right":
                fx, fy = int(width * 0.15), height // 2
                tx, ty = int(width * 0.85), height // 2
            else:
                raise UsageError(f"Invalid scroll_direction: '{scroll_direction}'")

            d.swipe(fx, fy, tx, ty, duration=scroll_duration)
            scrolls_performed += 1
            time.sleep(0.5)


UI_DOMAIN = DomainSpec(
    name="ui",
    description="UI hierarchy inspection, element interaction, and gesture commands",
    tools=[
        ToolSpec(
            name="ui.dump",
            domain="ui",
            description="Dump hierarchy actionable elements and screen fingerprint.",
            input_schema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max elements to return (0 for all, default 30)"},
                    "include_system_bars": {"type": "boolean", "description": "Include status and navigation bars"},
                    "include_containers": {"type": "boolean", "description": "Include non-actionable container elements"},
                    "raw": {"type": "boolean", "description": "Return raw XML without filtering"},
                    "filter": {"type": "string", "enum": ["actionable"], "description": "Element filter; only 'actionable' (default behavior)"},
                },
                "additionalProperties": False,
            },
            output_schema={
                "type": "object",
                "required": [],
                "properties": {
                    "screen_fingerprint": {"type": "string"},
                    "total_actionable": {"type": "integer"},
                    "limit": {"type": "integer"},
                    "elements": {"type": "array"},
                    "raw_xml": {"type": "string"},
                },
            },
            handler=ui_dump_handler,
            safety="read",
        ),
        ToolSpec(
            name="ui.tap",
            domain="ui",
            description="Tap one visible UI element matched by selector.",
            input_schema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Exact visible text"},
                    "text_contains": {"type": "string", "description": "Case-insensitive substring match on visible text"},
                    "resource_id": {"type": "string", "description": "Resource ID"},
                    "description": {"type": "string", "description": "Accessibility description"},
                    "desc_contains": {"type": "string", "description": "Case-insensitive substring match on accessibility description"},
                    "bounds": {"type": "string", "description": "Bounds format 'X1,Y1-X2,Y2'"},
                },
                "additionalProperties": False,
            },
            output_schema={
                "type": "object",
                "required": ["element", "bounds"],
                "properties": {
                    "element": {"type": "object"},
                    "bounds": {"type": "string"},
                    "postcondition": {"type": "object"},
                },
            },
            handler=ui_tap_handler,
            safety="interactive",
            idempotent=False,
            expect={"element": {}, "state": "exists"},
        ),
        ToolSpec(
            name="ui.long_press",
            domain="ui",
            description="Long-press one visible UI element matched by selector.",
            input_schema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Exact visible text"},
                    "text_contains": {"type": "string", "description": "Case-insensitive substring match on visible text"},
                    "resource_id": {"type": "string", "description": "Resource ID"},
                    "description": {"type": "string", "description": "Accessibility description"},
                    "desc_contains": {"type": "string", "description": "Case-insensitive substring match on accessibility description"},
                    "bounds": {"type": "string", "description": "Bounds format 'X1,Y1-X2,Y2'"},
                    "duration": {"type": "number", "description": "Press duration in seconds (default 1.0)"},
                },
                "additionalProperties": False,
            },
            output_schema={
                "type": "object",
                "required": ["element", "bounds"],
                "properties": {
                    "element": {"type": "object"},
                    "bounds": {"type": "string"},
                    "duration": {"type": "number"},
                    "postcondition": {"type": "object"},
                },
            },
            handler=ui_long_press_handler,
            safety="interactive",
            idempotent=False,
            expect={"element": {}, "state": "exists"},
        ),
        ToolSpec(
            name="ui.input",
            domain="ui",
            description="Type text verbatim into focused input field.",
            input_schema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to type"},
                },
                "required": ["text"],
                "additionalProperties": False,
            },
            output_schema={
                "type": "object",
                "required": ["text_typed"],
                "properties": {
                    "text_typed": {"type": "string"},
                    "postcondition": {"type": "object"},
                },
            },
            handler=ui_input_handler,
            safety="interactive",
            idempotent=False,
            expect={"schema": {"type": "object", "required": ["text_typed"]}},
        ),
        ToolSpec(
            name="ui.swipe",
            domain="ui",
            description="Perform drag/swipe gesture from point A to B.",
            input_schema={
                "type": "object",
                "properties": {
                    "from_pos": {"type": "string", "description": "Start position 'X,Y'"},
                    "to_pos": {"type": "string", "description": "End position 'X,Y'"},
                    "duration": {"type": "number", "description": "Gesture duration in seconds"},
                },
                "required": ["from_pos", "to_pos"],
                "additionalProperties": False,
            },
            output_schema={
                "type": "object",
                "required": ["swiped", "screen_fingerprint"],
                "properties": {
                    "swiped": {"type": "boolean"},
                    "from": {"type": "array"},
                    "to": {"type": "array"},
                    "duration": {"type": "number"},
                    "screen_fingerprint": {"type": "string"},
                },
            },
            handler=ui_swipe_handler,
            safety="interactive",
            idempotent=False,
            expect={"schema": {"type": "object", "required": ["swiped"]}},
        ),
        ToolSpec(
            name="ui.press",
            domain="ui",
            description="Press hardware or navigation key (home, back, recent, enter, delete).",
            input_schema={
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Key name"},
                },
                "required": ["key"],
                "additionalProperties": False,
            },
            output_schema={
                "type": "object",
                "required": ["key", "screen_fingerprint"],
                "properties": {
                    "key": {"type": "string"},
                    "screen_fingerprint": {"type": "string"},
                },
            },
            handler=ui_press_handler,
            safety="interactive",
            idempotent=False,
            expect={"schema": {"type": "object", "required": ["key"]}},
        ),
        ToolSpec(
            name="ui.wait",
            domain="ui",
            description="Wait for an element matching selector to become present or absent.",
            input_schema={
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "text_contains": {"type": "string"},
                    "resource_id": {"type": "string"},
                    "description": {"type": "string"},
                    "desc_contains": {"type": "string"},
                    "bounds": {"type": "string"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds (max 120)"},
                    "absent": {"type": "boolean", "description": "Wait for element to disappear"},
                },
                "additionalProperties": False,
            },
            output_schema={
                "type": "object",
                "required": ["waited_seconds", "satisfied"],
                "properties": {
                    "waited_seconds": {"type": "number"},
                    "satisfied": {"type": "boolean"},
                    "element": {"type": ["object", "null"]},
                },
            },
            handler=ui_wait_handler,
            safety="read",
        ),
        ToolSpec(
            name="ui.find",
            domain="ui",
            description="Scroll repeatedly until selector element is found or max scrolls reached.",
            input_schema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Exact visible text"},
                    "text_contains": {"type": "string", "description": "Case-insensitive substring match on visible text"},
                    "resource_id": {"type": "string", "description": "Resource ID"},
                    "description": {"type": "string", "description": "Accessibility description"},
                    "desc_contains": {"type": "string", "description": "Case-insensitive substring match on accessibility description"},
                    "bounds": {"type": "string", "description": "Bounds format 'X1,Y1-X2,Y2'"},
                    "scroll_direction": {"type": "string", "enum": ["down", "up", "left", "right"], "description": "Scroll direction (default 'down')"},
                    "max_scrolls": {"type": "integer", "description": "Maximum number of scroll swipes (default 10, max 30)"},
                    "scroll_duration": {"type": "number", "description": "Swipe gesture duration in seconds (default 0.3)"},
                },
                "additionalProperties": False,
            },
            output_schema={
                "type": "object",
                "required": ["found", "scrolls_performed", "screen_fingerprint"],
                "properties": {
                    "found": {"type": "boolean"},
                    "element": {"type": ["object", "null"]},
                    "scrolls_performed": {"type": "integer"},
                    "screen_fingerprint": {"type": "string"},
                },
            },
            handler=ui_find_handler,
            safety="read",
        ),
    ],
)
