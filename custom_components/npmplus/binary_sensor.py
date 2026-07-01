"""Binary sensor entities for NPMplus proxy hosts."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .const import DOMAIN, PREFIX_PROXY
from .coordinator import NPMplusDataUpdateCoordinator
from .entity import NPMplusProxyHostEntity


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
        entities: list[BinarySensorEntity] = []
        for host_id in new_host_ids:
            entities.append(ProxyHostSslEnabledSensor(coordinator, entry, host_id))
            entities.append(ProxyHostForceHttpsSensor(coordinator, entry, host_id))
        async_add_entities(entities)

    _add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_entities))


class _ProxyHostBinarySensorBase(NPMplusProxyHostEntity, BinarySensorEntity):
    _suffix = "binary"
    _attr_entity_category = None

    def __init__(
        self, coordinator: NPMplusDataUpdateCoordinator, entry: ConfigEntry, host_id: int
    ) -> None:
        super().__init__(coordinator, entry, host_id, self._suffix)
        host = coordinator.data.proxy_hosts.get(host_id)
        domain_slug = slugify(host.primary_domain) if host else f"host_{host_id}"
        self.entity_id = f"binary_sensor.{PREFIX_PROXY}_{domain_slug}_{self._suffix}"


class ProxyHostSslEnabledSensor(_ProxyHostBinarySensorBase):
    """Whether the proxy host has an SSL certificate assigned."""

    _suffix = "ssl_enabled"
    _attr_translation_key = "proxy_ssl_enabled"
    _attr_icon = "mdi:lock-check-outline"

    @property
    def is_on(self) -> bool | None:
        host = self.proxy_host
        return host.ssl_enabled if host else None


class ProxyHostForceHttpsSensor(_ProxyHostBinarySensorBase):
    """Whether HTTPS is forced (ssl_forced) for the proxy host."""

    _suffix = "force_https"
    _attr_translation_key = "proxy_force_https"

    @property
    def is_on(self) -> bool | None:
        host = self.proxy_host
        return host.ssl_forced if host else None
