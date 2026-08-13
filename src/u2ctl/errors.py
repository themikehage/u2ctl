"""Typed errors and stable error code definitions for u2ctl."""

from typing import Optional, Dict, Any


class U2CtlError(Exception):
    """Base exception for all u2ctl errors."""

    code: str = "INTERNAL"
    exit_code: int = 10
    retryable: bool = False
    default_hint: str = "Report the command + JSON envelope"

    def __init__(self, message: str, hint: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.hint = hint or self.default_hint
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
            "hint": self.hint,
        }


class UsageError(U2CtlError):
    code = "USAGE"
    exit_code = 1
    retryable = False
    default_hint = "Run u2ctl <domain> <tool> --help"


class DeviceNoneError(U2CtlError):
    code = "DEVICE_NONE"
    exit_code = 2
    retryable = True
    default_hint = "Connect USB or run `adb connect <ip>`"


class DeviceAmbiguousError(U2CtlError):
    code = "DEVICE_AMBIGUOUS"
    exit_code = 2
    retryable = False
    default_hint = "Pass --serial <serial> from `u2ctl device list`"


class DeviceNotFoundError(U2CtlError):
    code = "DEVICE_NOT_FOUND"
    exit_code = 2
    retryable = True
    default_hint = "Run `u2ctl device reconnect` or check `adb devices`"


class DeviceUnauthorizedError(U2CtlError):
    code = "DEVICE_UNAUTHORIZED"
    exit_code = 2
    retryable = True
    default_hint = "Accept the RSA prompt on the device screen"


class DeviceOfflineError(U2CtlError):
    code = "DEVICE_OFFLINE"
    exit_code = 2
    retryable = True
    default_hint = "Run `u2ctl device reconnect --serial <serial>`"


class ADBUnavailableError(U2CtlError):
    code = "ADB_UNAVAILABLE"
    exit_code = 2
    retryable = False
    default_hint = "Install platform-tools or set ADB_PATH environment variable"


class SelectorNotFoundError(U2CtlError):
    code = "SELECTOR_NOT_FOUND"
    exit_code = 3
    retryable = False
    default_hint = "Re-dump with `u2ctl ui dump --filter actionable`"


class AppNotFoundError(U2CtlError):
    code = "APP_NOT_FOUND"
    exit_code = 3
    retryable = False
    default_hint = "Check package name or inspect installed apps"


class ProvisionBlockedError(U2CtlError):
    code = "PROVISION_BLOCKED"
    exit_code = 4
    retryable = False
    default_hint = "Enable 'Install via USB' in Android Developer options"


class ProvisionFailedError(U2CtlError):
    code = "PROVISION_FAILED"
    exit_code = 4
    retryable = True
    default_hint = "Run `u2ctl setup diagnose`"


class TimeoutError(U2CtlError):
    code = "TIMEOUT"
    exit_code = 5
    retryable = True
    default_hint = "Raise `--timeout` or reconnect device first"


class PostconditionFailedError(U2CtlError):
    code = "POSTCONDITION_FAILED"
    exit_code = 5
    retryable = False
    default_hint = "Re-dump hierarchy; UI state may have changed"


class TransientError(U2CtlError):
    code = "TRANSIENT"
    exit_code = 5
    retryable = True
    default_hint = "Retry once, then run `u2ctl device reconnect`"


class InternalError(U2CtlError):
    code = "INTERNAL"
    exit_code = 10
    retryable = False
    default_hint = "Report the command + JSON envelope"
