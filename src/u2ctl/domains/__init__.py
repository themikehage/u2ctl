"""Domain module initialization and registration."""

from u2ctl.registry import registry
from u2ctl.domains.device import DEVICE_DOMAIN
from u2ctl.domains.setup import SETUP_DOMAIN
from u2ctl.domains.tools import TOOLS_DOMAIN

# Will include APP_DOMAIN, UI_DOMAIN in Phase 3
DOMAINS = [
    DEVICE_DOMAIN,
    SETUP_DOMAIN,
    TOOLS_DOMAIN,
]

_REGISTERED = False


def init_domains() -> None:
    global _REGISTERED
    if _REGISTERED:
        return
    for domain in DOMAINS:
        registry.register_domain(domain)
    _REGISTERED = True
