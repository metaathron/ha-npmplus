"""Sensor entities for NPMplus: per-host sensors and server-wide summary."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .const import DOMAIN, PREFIX_PROXY
from .coordinator import NPMplusDataUpdateCoordinator
from .entity import NPMplusProxyHostEntity, NPMplusServerEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: NPMplusDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    known_host_ids: set[int] = set()
    server_entities_added = False

    @callback
    def _add_new_entities() -> None:
        nonlocal server_entities_added
        entities: list[SensorEntity] = []

        new_host_ids = set(coordinator.data.proxy_hosts) - known_host_ids
        if new_host_ids:
            known_host_ids.update(new_host_ids)
            for host_id in new_host_ids:
                entities.append(
                    ProxyHostCertificateExpirationSensor(coordinator, entry, host_id)
                )
                entities.append(ProxyHostPublicUrlSensor(coordinator, entry, host_id))
                entities.append(ProxyHostLocalUrlSensor(coordinator, entry, host_id))

        if not server_entities_added:
            server_entities_added = True
            entities.extend(_build_server_sensors(coordinator, entry))

        if entities:
            async_add_entities(entities)

    _add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_entities))


def _build_server_sensors(
    coordinator: NPMplusDataUpdateCoordinator, entry: ConfigEntry
) -> list[SensorEntity]:
    return [
        ServerSummarySensor(
            coordinator, entry, "proxy_hosts_total", "Proxy hosts total", "mdi:server"
        ),
        ServerSummarySensor(
            coordinator,
            entry,
            "proxy_hosts_enabled",
            "Proxy hosts enabled",
            "mdi:server-network",
        ),
        ServerSummarySensor(
            coordinator,
            entry,
            "proxy_hosts_disabled",
            "Proxy hosts disabled",
            "mdi:server-off",
        ),
        ServerSummarySensor(
            coordinator, entry, "streams_total", "Streams total", "mdi:swap-horizontal"
        ),
        ServerSummarySensor(
            coordinator,
            entry,
            "streams_enabled",
            "Streams enabled",
            "mdi:swap-horizontal-bold",
        ),
        ServerSummarySensor(
            coordinator,
            entry,
            "streams_disabled",
            "Streams disabled",
            "mdi:swap-horizontal-circle-outline",
        ),
        ServerSummarySensor(
            coordinator,
            entry,
            "dead_hosts_total",
            "404 hosts total",
            "mdi:server-remove",
        ),
        ServerSummarySensor(
            coordinator,
            entry,
            "dead_hosts_enabled",
            "404 hosts enabled",
            "mdi:server-remove",
        ),
        ServerSummarySensor(
            coordinator,
            entry,
            "dead_hosts_disabled",
            "404 hosts disabled",
            "mdi:server-off",
        ),
        ServerSummarySensor(
            coordinator,
            entry,
            "redirection_hosts_total",
            "Redirection hosts total",
            "mdi:arrow-right-bold-box-outline",
        ),
        ServerSummarySensor(
            coordinator,
            entry,
            "redirection_hosts_enabled",
            "Redirection hosts enabled",
            "mdi:arrow-right-bold-box-outline",
        ),
        ServerSummarySensor(
            coordinator,
            entry,
            "redirection_hosts_disabled",
            "Redirection hosts disabled",
            "mdi:server-off",
        ),
        ServerSummarySensor(
            coordinator,
            entry,
            "certificates_expiring_14d",
            "Certificates expiring within 14 days",
            "mdi:certificate-outline",
        ),
        ServerSummarySensor(
            coordinator,
            entry,
            "certificates_expiring_7d",
            "Certificates expiring within 7 days",
            "mdi:alert-outline",
        ),
        ServerSummarySensor(
            coordinator,
            entry,
            "certificates_expired",
            "Certificates expired",
            "mdi:alert-circle-outline",
        ),
    ]


class _ProxyHostSensorBase(NPMplusProxyHostEntity, SensorEntity):
    _suffix = "sensor"

    def __init__(
        self, coordinator: NPMplusDataUpdateCoordinator, entry: ConfigEntry, host_id: int
    ) -> None:
        super().__init__(coordinator, entry, host_id, self._suffix)
        host = coordinator.data.proxy_hosts.get(host_id)
        domain_slug = slugify(host.primary_domain) if host else f"host_{host_id}"
        self.entity_id = f"sensor.{PREFIX_PROXY}_{domain_slug}_{self._suffix}"


class ProxyHostCertificateExpirationSensor(_ProxyHostSensorBase):
    """Expiration timestamp of the certificate assigned to this host."""

    _suffix = "certificate_expiration"
    _attr_translation_key = "proxy_certificate_expiration"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:certificate"

    @property
    def native_value(self):
        host = self.proxy_host
        return host.certificate_expires_on if host else None


class ProxyHostPublicUrlSensor(_ProxyHostSensorBase):
    """Public URL of the proxy host.

    The state is the URL itself so it can be used directly in automations,
    scripts, or as a clickable link (e.g. via a markdown card) in Lovelace.
    """

    _suffix = "public_url"
    _attr_translation_key = "proxy_public_url"
    _attr_icon = "mdi:web"

    @property
    def native_value(self) -> str | None:
        host = self.proxy_host
        return host.public_url if host else None


class ProxyHostLocalUrlSensor(_ProxyHostSensorBase):
    """Local (upstream) URL the proxy host forwards to."""

    _suffix = "local_url"
    _attr_translation_key = "proxy_local_url"
    _attr_icon = "mdi:lan-connect"

    @property
    def native_value(self) -> str | None:
        host = self.proxy_host
        return host.local_url if host else None


class ServerSummarySensor(NPMplusServerEntity, SensorEntity):
    """A single counter from the aggregated NPMplus summary."""

    _attr_state_class = "measurement"

    def __init__(
        self,
        coordinator: NPMplusDataUpdateCoordinator,
        entry: ConfigEntry,
        field_name: str,
        name: str,
        icon: str,
    ) -> None:
        super().__init__(coordinator, entry, field_name)
        self._field_name = field_name
        self._attr_name = name
        self._attr_icon = icon
        self.entity_id = f"sensor.npmplus_{field_name}"

    @property
    def native_value(self) -> int:
        return getattr(self.coordinator.data.summary, self._field_name)
