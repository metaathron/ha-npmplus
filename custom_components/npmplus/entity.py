"""Base entity classes shared by all NPMplus platforms."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DEVICE_DEAD_HOSTS,
    DEVICE_REDIRECTION_HOSTS,
    DEVICE_SERVER,
    DEVICE_STREAMS,
    DOMAIN,
    MANUFACTURER,
)
from .coordinator import NPMplusDataUpdateCoordinator


def server_device_info(entry: ConfigEntry) -> DeviceInfo:
    """Device representing the NPMplus server itself."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_SERVER}")},
        name="NPMplus",
        manufacturer=MANUFACTURER,
        configuration_url=f"https://{entry.data['host']}:{entry.data['port']}",
        model="NPMplus server",
    )


def streams_device_info(entry: ConfigEntry) -> DeviceInfo:
    """Shared device for all stream entities."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_STREAMS}")},
        name="Streams",
        manufacturer=MANUFACTURER,
        via_device=(DOMAIN, f"{entry.entry_id}_{DEVICE_SERVER}"),
        model="NPMplus streams",
    )


def dead_hosts_device_info(entry: ConfigEntry) -> DeviceInfo:
    """Shared device for all 404 ("dead") host entities."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_DEAD_HOSTS}")},
        name="404 Hosts",
        manufacturer=MANUFACTURER,
        via_device=(DOMAIN, f"{entry.entry_id}_{DEVICE_SERVER}"),
        model="NPMplus 404 hosts",
    )


def redirection_hosts_device_info(entry: ConfigEntry) -> DeviceInfo:
    """Shared device for all redirection host entities."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_REDIRECTION_HOSTS}")},
        name="Redirection Hosts",
        manufacturer=MANUFACTURER,
        via_device=(DOMAIN, f"{entry.entry_id}_{DEVICE_SERVER}"),
        model="NPMplus redirection hosts",
    )


def proxy_host_device_info(entry: ConfigEntry, host_id: int, domain: str) -> DeviceInfo:
    """Per-proxy-host device."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_proxy_{host_id}")},
        name=domain,
        manufacturer=MANUFACTURER,
        via_device=(DOMAIN, f"{entry.entry_id}_{DEVICE_SERVER}"),
        model="NPMplus proxy host",
    )


class NPMplusEntity(CoordinatorEntity[NPMplusDataUpdateCoordinator]):
    """Common base for all NPMplus entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NPMplusDataUpdateCoordinator,
        entry: ConfigEntry,
        unique_id_suffix: str,
    ) -> None:
        super().__init__(coordinator)
        self.entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{unique_id_suffix}"


class NPMplusProxyHostEntity(NPMplusEntity):
    """Base for entities that belong to a single proxy host device."""

    def __init__(
        self,
        coordinator: NPMplusDataUpdateCoordinator,
        entry: ConfigEntry,
        host_id: int,
        unique_id_suffix: str,
    ) -> None:
        self.host_id = host_id
        super().__init__(coordinator, entry, f"proxy_{host_id}_{unique_id_suffix}")
        host = coordinator.data.proxy_hosts.get(host_id)
        domain = host.primary_domain if host else f"host {host_id}"
        self._attr_device_info = proxy_host_device_info(entry, host_id, domain)

    @property
    def proxy_host(self):
        """Return the current ProxyHostData, or None if it was removed."""
        return self.coordinator.data.proxy_hosts.get(self.host_id)

    @property
    def available(self) -> bool:
        return super().available and self.proxy_host is not None


class NPMplusStreamEntity(NPMplusEntity):
    """Base for entities that belong to the shared Streams device."""

    def __init__(
        self,
        coordinator: NPMplusDataUpdateCoordinator,
        entry: ConfigEntry,
        stream_id: int,
        unique_id_suffix: str,
    ) -> None:
        self.stream_id = stream_id
        super().__init__(coordinator, entry, f"stream_{stream_id}_{unique_id_suffix}")
        self._attr_device_info = streams_device_info(entry)

    @property
    def stream(self):
        """Return the current StreamData, or None if it was removed."""
        return self.coordinator.data.streams.get(self.stream_id)

    @property
    def available(self) -> bool:
        return super().available and self.stream is not None


class NPMplusDeadHostEntity(NPMplusEntity):
    """Base for entities that belong to the shared 404 Hosts device."""

    def __init__(
        self,
        coordinator: NPMplusDataUpdateCoordinator,
        entry: ConfigEntry,
        host_id: int,
        unique_id_suffix: str,
    ) -> None:
        self.host_id = host_id
        super().__init__(coordinator, entry, f"dead_{host_id}_{unique_id_suffix}")
        self._attr_device_info = dead_hosts_device_info(entry)

    @property
    def dead_host(self):
        """Return the current DeadHostData, or None if it was removed."""
        return self.coordinator.data.dead_hosts.get(self.host_id)

    @property
    def available(self) -> bool:
        return super().available and self.dead_host is not None


class NPMplusRedirectionHostEntity(NPMplusEntity):
    """Base for entities that belong to the shared Redirection Hosts device."""

    def __init__(
        self,
        coordinator: NPMplusDataUpdateCoordinator,
        entry: ConfigEntry,
        host_id: int,
        unique_id_suffix: str,
    ) -> None:
        self.host_id = host_id
        super().__init__(coordinator, entry, f"redirect_{host_id}_{unique_id_suffix}")
        self._attr_device_info = redirection_hosts_device_info(entry)

    @property
    def redirection_host(self):
        """Return the current RedirectionHostData, or None if it was removed."""
        return self.coordinator.data.redirection_hosts.get(self.host_id)

    @property
    def available(self) -> bool:
        return super().available and self.redirection_host is not None


class NPMplusServerEntity(NPMplusEntity):
    """Base for entities on the aggregate NPMplus server device."""

    def __init__(
        self,
        coordinator: NPMplusDataUpdateCoordinator,
        entry: ConfigEntry,
        unique_id_suffix: str,
    ) -> None:
        super().__init__(coordinator, entry, f"server_{unique_id_suffix}")
        self._attr_device_info = server_device_info(entry)
