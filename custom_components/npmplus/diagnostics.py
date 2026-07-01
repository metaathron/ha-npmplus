"""Diagnostics support for NPMplus."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import DOMAIN

TO_REDACT = {CONF_PASSWORD, CONF_USERNAME, "domain_names", "forward_host", "host"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    data = coordinator.data

    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "summary": vars(data.summary),
        "proxy_hosts": [
            async_redact_data(vars(host), TO_REDACT)
            for host in data.proxy_hosts.values()
        ],
        "streams": [vars(stream) for stream in data.streams.values()],
        "dead_hosts": [
            async_redact_data(vars(host), TO_REDACT)
            for host in data.dead_hosts.values()
        ],
        "redirection_hosts": [
            async_redact_data(vars(host), TO_REDACT)
            for host in data.redirection_hosts.values()
        ],
        "certificates_count": len(data.certificates),
    }
