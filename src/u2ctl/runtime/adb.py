"""ADB discovery, device selection, and recovery operations."""

import shutil
import subprocess
from typing import List, Optional, Tuple

import adbutils

from u2ctl.errors import (
    ADBUnavailableError,
    DeviceNoneError,
    DeviceAmbiguousError,
    DeviceNotFoundError,
    DeviceOfflineError,
    DeviceUnauthorizedError,
)
from u2ctl.models import DeviceInfo


def get_adb_path(custom_adb_path: Optional[str] = None) -> str:
    path = custom_adb_path or shutil.which("adb")
    if not path:
        raise ADBUnavailableError("`adb` command not found on system PATH")
    return path


def list_adb_devices(adb_path: Optional[str] = None) -> List[DeviceInfo]:
    """List all ADB devices with state and transport."""
    path = get_adb_path(adb_path)
    try:
        res = subprocess.run([path, "devices", "-l"], capture_output=True, text=True, check=True)
    except Exception as e:
        raise ADBUnavailableError(f"Failed to execute adb devices: {e}")

    devices = []
    lines = res.stdout.strip().splitlines()
    for line in lines[1:]:  # skip 'List of devices attached' header
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        serial = parts[0]
        state = parts[1]
        model = ""
        transport = "wifi" if ":" in serial else "usb"

        for p in parts[2:]:
            if p.startswith("model:"):
                model = p.split(":", 1)[1]

        devices.append(DeviceInfo(serial=serial, state=state, model=model, transport=transport))
    return devices


def select_target_device(
    requested_serial: Optional[str] = None,
    adb_path: Optional[str] = None,
) -> Tuple[DeviceInfo, List[DeviceInfo]]:
    """Select target device deterministically according to G8 selection rules."""
    devices = list_adb_devices(adb_path)

    if not devices:
        raise DeviceNoneError("No ADB devices connected")

    if requested_serial:
        matched = [d for d in devices if d.serial == requested_serial]
        if not matched:
            raise DeviceNotFoundError(f"Requested device serial '{requested_serial}' not found in ADB device list")
        target = matched[0]
    else:
        if len(devices) == 1:
            target = devices[0]
        else:
            serials = ", ".join(d.serial for d in devices)
            raise DeviceAmbiguousError(f"Multiple ADB devices connected ({serials}). Must specify --serial")

    # Mark selected
    for d in devices:
        if d.serial == target.serial:
            d.selected = True

    # Validate state of selected device
    if target.state == "unauthorized":
        raise DeviceUnauthorizedError(f"Device '{target.serial}' is unauthorized. Accept RSA key on device screen")
    elif target.state == "offline":
        raise DeviceOfflineError(f"Device '{target.serial}' is offline")
    elif target.state != "device":
        raise DeviceOfflineError(f"Device '{target.serial}' is in non-usable state '{target.state}'")

    return target, devices


def reconnect_device(serial: str, hard: bool = False, adb_path: Optional[str] = None) -> str:
    """Reconnect device via soft adb reconnect or hard server restart."""
    path = get_adb_path(adb_path)
    if hard:
        subprocess.run([path, "kill-server"], capture_output=True, text=True)
        subprocess.run([path, "start-server"], capture_output=True, text=True)
        return "Hard reconnect performed: adb server restarted"
    else:
        res = subprocess.run([path, "reconnect", serial], capture_output=True, text=True)
        return res.stdout.strip() or f"Soft reconnect sent to {serial}"
