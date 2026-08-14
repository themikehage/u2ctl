"""Configuration loading and precedence logic for u2ctl."""

import os
import json
import shutil
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Dict, Any

from u2ctl.errors import UsageError


@dataclass
class Config:
    serial: Optional[str] = None
    timeout: int = 30
    json_output: bool = True
    safety_ceiling: str = "interactive"
    adb_path: Optional[str] = None
    strict_selector: bool = False
    filter_packages: Optional[set] = None


VALID_SAFETY_LEVELS = {"read", "interactive", "destructive"}


def load_config_file(custom_path: Optional[str] = None) -> Dict[str, Any]:
    """Load JSON config file if present."""
    paths_to_check = []
    if custom_path:
        paths_to_check.append(Path(custom_path))
    else:
        env_config = os.getenv("U2CTL_CONFIG")
        if env_config:
            paths_to_check.append(Path(env_config))
        paths_to_check.append(Path(".u2ctl.json"))
        paths_to_check.append(Path.home() / ".config" / "u2ctl" / "config.json")

    for p in paths_to_check:
        if p.is_file():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
            except Exception as e:
                raise UsageError(f"Failed to parse config file at {p}: {e}")
    return {}


def resolve_config(cli_args: Optional[Dict[str, Any]] = None) -> Config:
    """Resolve config hierarchy: flags > env > config file > defaults."""
    cli_args = cli_args or {}
    file_cfg = load_config_file()

    # 1. Serial
    serial = cli_args.get("serial")
    if not serial:
        serial = os.getenv("U2CTL_SERIAL") or os.getenv("ANDROID_SERIAL")
    if not serial:
        serial = file_cfg.get("serial")

    # 2. Timeout
    raw_timeout = cli_args.get("timeout")
    if raw_timeout is None:
        env_timeout = os.getenv("U2CTL_TIMEOUT")
        if env_timeout:
            try:
                raw_timeout = int(env_timeout)
            except ValueError:
                raise UsageError(f"Invalid U2CTL_TIMEOUT value: {env_timeout}")
    if raw_timeout is None:
        raw_timeout = file_cfg.get("timeout", 30)
    timeout = int(raw_timeout)

    # 3. JSON Output (Default True; --human forces human-readable format)
    json_output = True
    if cli_args.get("human"):
        json_output = False
    elif os.getenv("U2CTL_HUMAN", "").lower() in ("1", "true", "yes"):
        json_output = False
    elif file_cfg.get("human"):
        json_output = False
    elif cli_args.get("json"):
        json_output = True
    elif os.getenv("U2CTL_JSON", "").lower() in ("0", "false", "no"):
        json_output = False

    # 4. Safety Ceiling
    safety = os.getenv("U2CTL_SAFETY") or file_cfg.get("safety") or "interactive"
    safety = safety.lower()
    if safety not in VALID_SAFETY_LEVELS:
        raise UsageError(f"Invalid safety level: '{safety}'. Must be one of {VALID_SAFETY_LEVELS}")

    # 5. ADB Path
    adb_path = os.getenv("ADB_PATH") or file_cfg.get("adbPath") or shutil.which("adb")

    # 6. Strict Selectors
    strict_selector = cli_args.get("strict_selector", False)
    if not strict_selector:
        env_strict = os.getenv("U2CTL_STRICT_SELECTOR", "").lower()
        if env_strict in ("1", "true", "yes"):
            strict_selector = True
    if not strict_selector:
        strict_selector = bool(file_cfg.get("strictSelector", False))

    # 7. Filter Packages
    extra_filter = os.getenv("U2CTL_FILTER_PACKAGES")
    filter_packages = set()
    if extra_filter:
        filter_packages.update(pkg.strip() for pkg in extra_filter.split(",") if pkg.strip())
    if "filterPackages" in file_cfg and isinstance(file_cfg["filterPackages"], list):
        filter_packages.update(file_cfg["filterPackages"])

    return Config(
        serial=serial,
        timeout=timeout,
        json_output=json_output,
        safety_ceiling=safety,
        adb_path=adb_path,
        strict_selector=strict_selector,
        filter_packages=filter_packages if filter_packages else None,
    )

