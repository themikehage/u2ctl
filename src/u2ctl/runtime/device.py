"""Device session lifecycle and connection management."""

from typing import Optional, Any
import uiautomator2 as u2

from u2ctl.errors import DeviceOfflineError, TimeoutError
from u2ctl.runtime.adb import select_target_device, get_adb_path


class DeviceSession:
    def __init__(self, serial: Optional[str] = None, timeout: int = 30, adb_path: Optional[str] = None):
        self.serial = serial
        self.timeout = timeout
        self.adb_path = adb_path
        self._u2_device: Optional[Any] = None

    def connect(self) -> Any:
        target, _ = select_target_device(self.serial, self.adb_path)
        self.serial = target.serial
        try:
            d = u2.connect(target.serial)
            d.wait_timeout = self.timeout
            self._u2_device = d
            return d
        except Exception as first_err:
            # Single auto-reconnect retry attempt for retryable connection errors
            try:
                d = u2.connect(target.serial)
                d.wait_timeout = self.timeout
                self._u2_device = d
                return d
            except Exception as second_err:
                raise DeviceOfflineError(
                    f"Failed to connect uiautomator2 to device '{target.serial}' after retry: {second_err}"
                )

    @property
    def u2(self) -> Any:
        if self._u2_device is None:
            return self.connect()
        return self._u2_device
