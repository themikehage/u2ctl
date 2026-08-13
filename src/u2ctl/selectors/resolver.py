"""Selector priority resolution and ambiguity warning logic."""

import re
from typing import List, Dict, Any, Tuple, Optional
from u2ctl.errors import SelectorNotFoundError
from u2ctl.models import ActionElement


def parse_bounds_rect(bounds_str: str) -> Optional[Tuple[int, int, int, int]]:
    m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds_str)
    if m:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)))
    return None


def rect_overlap_ratio(rect1: Tuple[int, int, int, int], rect2: Tuple[int, int, int, int]) -> float:
    """Calculate overlap ratio relative to smaller rectangle area."""
    x1 = max(rect1[0], rect2[0])
    y1 = max(rect1[1], rect2[1])
    x2 = min(rect1[2], rect2[2])
    y2 = min(rect1[3], rect2[3])

    if x2 <= x1 or y2 <= y1:
        return 0.0

    intersection = (x2 - x1) * (y2 - y1)
    area1 = (rect1[2] - rect1[0]) * (rect1[3] - rect1[1])
    area2 = (rect2[2] - rect2[0]) * (rect2[3] - rect2[1])
    smaller_area = min(area1, area2)

    if smaller_area <= 0:
        return 0.0
    return intersection / float(smaller_area)


def resolve_selector(
    elements: List[ActionElement],
    selector: Dict[str, Any],
    strict_selector: bool = False,
) -> Tuple[ActionElement, List[str]]:
    """Resolve element matching selector according to priority and ambiguity rules."""
    warnings: List[str] = []
    matched: List[ActionElement] = []

    # Priority matching: resource_id > description > text > desc_contains > text_contains > bounds
    if "resource_id" in selector:
        rid = selector["resource_id"]
        matched = [e for e in elements if e.resource_id == rid or e.resource_id.endswith(f":id/{rid}")]
    elif "description" in selector:
        desc = selector["description"]
        matched = [e for e in elements if e.content_desc == desc]
    elif "text" in selector:
        txt = selector["text"]
        matched = [e for e in elements if e.text == txt]
    elif "desc_contains" in selector:
        sub = selector["desc_contains"].lower()
        matched = [e for e in elements if sub in e.content_desc.lower()]
    elif "text_contains" in selector:
        sub = selector["text_contains"].lower()
        matched = [e for e in elements if sub in e.text.lower()]
    elif "bounds" in selector:
        req_b = selector["bounds"]  # [x1, y1, x2, y2]
        matched = []
        for e in elements:
            b = parse_bounds_rect(e.bounds)
            if b and rect_overlap_ratio((req_b[0], req_b[1], req_b[2], req_b[3]), b) >= 0.9:
                matched.append(e)

        def _get_area(elem: ActionElement) -> int:
            b = parse_bounds_rect(elem.bounds)
            if not b:
                return 2**62
            return (b[2] - b[0]) * (b[3] - b[1])

        matched.sort(key=_get_area)

    if not matched:
        raise SelectorNotFoundError(
            f"No element found matching selector {selector}",
            hint="Run `u2ctl ui dump --filter actionable` to inspect current on-screen elements",
        )

    if len(matched) == 1:
        return matched[0], warnings

    # Ambiguity resolution rules (G4)
    # 1. Focused
    focused_matches = [e for e in matched if e.focused]
    if len(focused_matches) == 1:
        return focused_matches[0], warnings

    # 2. Same screen rect
    first_b = parse_bounds_rect(matched[0].bounds)
    if first_b:
        all_same = True
        for m in matched[1:]:
            mb = parse_bounds_rect(m.bounds)
            if not mb or rect_overlap_ratio(first_b, mb) < 0.9:
                all_same = False
                break
        if all_same:
            return matched[0], warnings

    # 3. Multiple matches warning or strict failure
    if strict_selector:
        raise SelectorNotFoundError(
            f"Selector matched {len(matched)} elements in strict mode: {[m.bounds for m in matched]}",
            hint="Pass --bounds or specify exact resource-id/description to uniquely target element",
        )

    bounds_list = ", ".join(m.bounds for m in matched[:3])
    warnings.append(f"SELECTOR_MATCHED_MULTIPLE matched {len(matched)}, used first ({matched[0].bounds}). Pass --bounds to disambiguate: [{bounds_list}]")
    return matched[0], warnings
