"""Selector string and flag parsing."""

import re
from typing import Dict, Any, Optional
from u2ctl.errors import UsageError


def parse_selector_args(args: Dict[str, Any]) -> Dict[str, Any]:
    """Parse dedicated selector flags (--text, --resource-id, --description, --bounds) or raw selector dict."""
    selector = {}

    if args.get("text"):
        selector["text"] = args["text"]
    if args.get("resource_id"):
        selector["resource_id"] = args["resource_id"]
    if args.get("description"):
        selector["description"] = args["description"]
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
        elif raw.startswith("resourceId:"):
            selector["resource_id"] = raw[11:]
        elif raw.startswith("desc:"):
            selector["description"] = raw[5:]
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
        raise UsageError("Must provide at least one selector flag: --text, --resource-id, --description, or --bounds")

    return selector
