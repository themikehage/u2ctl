"""Device domain capability definitions."""

from typing import Dict, Any
from u2ctl.models import DeviceInfo
from u2ctl.registry import ToolSpec, DomainSpec, HandlerContext
from u2ctl.runtime.adb import list_adb_devices, select_target_device, reconnect_device


def device_list_handler(ctx: HandlerContext, args: Dict[str, Any]) -> Dict[str, Any]:
    devices = list_adb_devices()
    selected_serial = ctx.serial
    out_devices = []
    for d in devices:
        if selected_serial and d.serial == selected_serial:
            d.selected = True
        elif not selected_serial and len(devices) == 1:
            d.selected = True
        out_devices.append(d.to_dict())
    return {"devices": out_devices}


def device_status_handler(ctx: HandlerContext, args: Dict[str, Any]) -> Dict[str, Any]:
    target, _ = select_target_device(ctx.serial)
    ctx.serial = target.serial
    return {
        "serial": target.serial,
        "state": target.state,
        "model": target.model,
        "transport": target.transport,
    }


def device_info_handler(ctx: HandlerContext, args: Dict[str, Any]) -> Dict[str, Any]:
    target, _ = select_target_device(ctx.serial)
    ctx.serial = target.serial
    import uiautomator2 as u2
    d = u2.connect(target.serial)
    info = d.info
    return {
        "serial": target.serial,
        "model": target.model,
        "sdk_version": info.get("sdkInt"),
        "display_size": [info.get("displayWidth"), info.get("displayHeight")],
        "display_rotation": info.get("displayRotation"),
        "screen_on": info.get("screenOn"),
    }


def device_reconnect_handler(ctx: HandlerContext, args: Dict[str, Any]) -> Dict[str, Any]:
    hard = args.get("hard", False)
    target_serial = ctx.serial
    if not target_serial and not hard:
        target, _ = select_target_device(ctx.serial)
        target_serial = target.serial

    res_msg = reconnect_device(target_serial or "", hard=hard)
    return {
        "reconnected": True,
        "serial": target_serial or "",
        "message": res_msg,
        "hard": hard,
    }


DEVICE_DOMAIN = DomainSpec(
    name="device",
    description="Device state, discovery, and recovery commands",
    tools=[
        ToolSpec(
            name="device.list",
            domain="device",
            description="List connected ADB devices and mark selected target.",
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
            output_schema={
                "type": "object",
                "required": ["devices"],
                "properties": {
                    "devices": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["serial", "state"],
                        },
                    }
                },
            },
            handler=device_list_handler,
            safety="read",
        ),
        ToolSpec(
            name="device.status",
            domain="device",
            description="Check health and readiness of target device.",
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
            output_schema={
                "type": "object",
                "required": ["serial", "state"],
                "properties": {
                    "serial": {"type": "string"},
                    "state": {"type": "string"},
                    "model": {"type": "string"},
                    "transport": {"type": "string"},
                },
            },
            handler=device_status_handler,
            safety="read",
        ),
        ToolSpec(
            name="device.info",
            domain="device",
            description="Fetch static hardware and OS facts.",
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
            output_schema={
                "type": "object",
                "required": ["serial"],
                "properties": {
                    "serial": {"type": "string"},
                    "model": {"type": "string"},
                    "sdk_version": {"type": ["integer", "null"]},
                    "display_size": {"type": "array"},
                    "display_rotation": {"type": ["integer", "null"]},
                    "screen_on": {"type": ["boolean", "null"]},
                },
            },
            handler=device_info_handler,
            safety="read",
        ),
        ToolSpec(
            name="device.reconnect",
            domain="device",
            description="Perform soft transport reconnect or hard adb server restart.",
            input_schema={
                "type": "object",
                "properties": {
                    "hard": {"type": "boolean", "description": "Restart local adb server (destructive to all devices)"},
                },
                "additionalProperties": False,
            },
            output_schema={
                "type": "object",
                "required": ["reconnected", "serial", "message"],
                "properties": {
                    "reconnected": {"type": "boolean"},
                    "serial": {"type": "string"},
                    "message": {"type": "string"},
                    "hard": {"type": "boolean"},
                },
            },
            handler=device_reconnect_handler,
            safety="destructive",
            idempotent=True,
            expect={"schema": {"type": "object", "required": ["reconnected"]}},
        ),
    ],
)
