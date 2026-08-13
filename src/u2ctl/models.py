"""Data models for device, setup, and UI elements."""

from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any


@dataclass
class DeviceInfo:
    serial: str
    state: str  # device, offline, unauthorized, recovery, no permissions
    model: str = ""
    transport: str = "usb"  # usb, wifi
    selected: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ActionElement:
    index: int
    text: str
    resource_id: str
    content_desc: str
    class_name: str
    bounds: str
    clickable: bool
    scrollable: bool
    focused: bool
    duplicates: int = 0

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "index": self.index,
            "text": self.text,
            "resourceId": self.resource_id,
            "contentDesc": self.content_desc,
            "className": self.class_name,
            "bounds": self.bounds,
            "clickable": self.clickable,
            "scrollable": self.scrollable,
            "focused": self.focused,
        }
        if self.duplicates > 0:
            d["duplicates"] = self.duplicates
        return d

    def to_compact_dict(self) -> Dict[str, Any]:
        d = {
            "index": self.index,
            "text": self.text,
            "resourceId": self.resource_id,
            "contentDesc": self.content_desc,
            "bounds": self.bounds,
            "clickable": self.clickable,
        }
        if self.scrollable:
            d["scrollable"] = True
        if self.focused:
            d["focused"] = True
        if self.duplicates > 0:
            d["duplicates"] = self.duplicates
        return d


@dataclass
class SetupStepReport:
    name: str
    status: str  # installed, already_present, skipped, failed
    detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SetupReport:
    status: str  # ready, not_ready
    steps: List[SetupStepReport] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "steps": [s.to_dict() for s in self.steps],
        }
