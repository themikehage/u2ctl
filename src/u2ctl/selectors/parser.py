"""Selector string and flag parsing."""

import re
from typing import Dict, Any, Optional
from u2ctl.errors import UsageError


def parse_selector_args(args: Dict[str, Any]) -> Dict[str, Any]:
    """Parse dedicated selector flags (--text, --text-contains, --resource-id, --description, --desc-contains, --bounds) or raw selector dict."""
    selector = {}

    if args.get("text"):
        selector["text"] = args["text"]
    if args.get("text_contains"):
        selector["text_contains"] = args["text_contains"]
    if args.get("resource_id"):
        selector["resource_id"] = args["resource_id"]
    if args.get("description"):
        selector["description"] = args["description"]
    if args.get("desc_contains"):
        selector["desc_contains"] = args["desc_contains"]
    if args.get("bounds"):
        bounds_str = args["bounds"]
        # Format: X1,Y1-X2,Y2 or [X1,Y1][X2,Y2]
        m = re.match(r"\[?(\d+),\s*(\d+)\]?\[?(\d+),\s*(\d+)\]?", bounds_str.replace("-", "]["))
        if not m:
            raise UsageError(f"Invalid bounds format: '{bounds_str}'. Expected 'X1,Y1-X2,Y2' or '[X1,Y1][X2,Y2]'")
        selector["bounds"] = [int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))]

    if not selector and args.get("selector"):
        raw = args["selector"]
        if raw.startswith("text:"):
            selector["text"] = raw[5:]
        elif raw.startswith("textContains:"):
            selector["text_contains"] = raw[13:]
        elif raw.startswith("resourceId:"):
            selector["resource_id"] = raw[11:]
        elif raw.startswith("desc:"):
            selector["description"] = raw[5:]
        elif raw.startswith("descContains:"):
            selector["desc_contains"] = raw[13:]
        elif raw.startswith("bounds:"):
            bounds_str = raw[7:]
            m = re.match(r"\[?(\d+),\s*(\d+)\]?\[?(\d+),\s*(\d+)\]?", bounds_str.replace("-", "]["))
            if not m:
                raise UsageError(f"Invalid bounds format in selector: '{bounds_str}'")
            selector["bounds"] = [int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))]
        else:
            # Default fallback to text selector
            selector["text"] = raw

    if not selector:
        raise UsageError("Must provide at least one selector flag: --text, --text-contains, --resource-id, --description, --desc-contains, or --bounds")

    return selector
