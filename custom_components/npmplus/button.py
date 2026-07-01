"""Button entities for NPMplus proxy hosts."""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .const import DOMAIN, PREFIX_PROXY
from .coordinator import NPMplusDataUpdateCoordinator
from .entity import NPMplusProxyHostEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: NPMplusDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    known_host_ids: set[int] = set()

    @callback
    def _add_new_entities() -> None:
        new_host_ids = set(coordinator.data.proxy_hosts) - known_host_ids
        if not new_host_ids:
            return
        known_host_ids.update(new_host_ids)
        async_add_entities(
            ProxyHostRenewCertificateButton(coordinator, entry, host_id)
            for host_id in new_host_ids
        )

    _add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_entities))


class ProxyHostRenewCertificateButton(NPMplusProxyHostEntity, ButtonEntity):
    """Force-renew the certificate assigned to a proxy host."""

    _attr_translation_key = "proxy_renew_certificate"
    _attr_icon = "mdi:certificate-outline"

    def __init__(
        self, coordinator: NPMplusDataUpdateCoordinator, entry: ConfigEntry, host_id: int
    ) -> None:
        super().__init__(coordinator, entry, host_id, "renew_certificate")
        host = coordinator.data.proxy_hosts.get(host_id)
        domain_slug = slugify(host.primary_domain) if host else f"host_{host_id}"
        self.entity_id = f"button.{PREFIX_PROXY}_{domain_slug}_renew_certificate"

    @property
    def available(self) -> bool:
        host = self.proxy_host
        return (
            super().available
            and host is not None
            and host.certificate_id is not None
            and host.certificate_renewable
        )

    async def async_press(self) -> None:
        host = self.proxy_host
        if host is None or host.certificate_id is None:
            raise HomeAssistantError(
                "This proxy host has no certificate assigned, nothing to renew."
            )
        if not host.certificate_renewable:
            raise HomeAssistantError(
                "This host uses a custom (non-Let's Encrypt) certificate, "
                "which cannot be renewed through the API."
            )
        await self.coordinator.client.async_renew_certificate(host.certificate_id)
        await self.coordinator.async_request_refresh()
