"""Unit tests for typed errors and exit codes."""

from u2ctl.errors import (
    UsageError,
    DeviceNoneError,
    DeviceAmbiguousError,
    DeviceNotFoundError,
    DeviceUnauthorizedError,
    DeviceOfflineError,
    ADBUnavailableError,
    SelectorNotFoundError,
    AppNotFoundError,
    ProvisionBlockedError,
    ProvisionFailedError,
    TimeoutError,
    PostconditionFailedError,
    TransientError,
    InternalError,
)


def test_error_exit_codes_and_codes():
    assert UsageError("msg").exit_code == 1
    assert UsageError("msg").code == "USAGE"

    assert DeviceNoneError("msg").exit_code == 2
    assert DeviceAmbiguousError("msg").exit_code == 2
    assert DeviceNotFoundError("msg").exit_code == 2
    assert DeviceUnauthorizedError("msg").exit_code == 2
    assert DeviceOfflineError("msg").exit_code == 2
    assert ADBUnavailableError("msg").exit_code == 2

    assert SelectorNotFoundError("msg").exit_code == 3
    assert AppNotFoundError("msg").exit_code == 3

    assert ProvisionBlockedError("msg").exit_code == 4
    assert ProvisionFailedError("msg").exit_code == 4

    assert TimeoutError("msg").exit_code == 5
    assert PostconditionFailedError("msg").exit_code == 5
    assert TransientError("msg").exit_code == 5

    assert InternalError("msg").exit_code == 10


def test_error_to_dict():
    err = ProvisionBlockedError("Blocked by Xiaomi policy", hint="Enable USB Install")
    d = err.to_dict()
    assert d["code"] == "PROVISION_BLOCKED"
    assert d["message"] == "Blocked by Xiaomi policy"
    assert d["retryable"] is False
    assert d["hint"] == "Enable USB Install"
