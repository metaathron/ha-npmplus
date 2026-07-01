"""Switch entities for NPMplus proxy hosts, streams, 404 hosts and redirection hosts."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .const import DOMAIN, PREFIX_DEAD_HOST, PREFIX_PROXY, PREFIX_REDIRECTION_HOST, PREFIX_STREAM
from .coordinator import NPMplusDataUpdateCoordinator
from .entity import (
    NPMplusDeadHostEntity,
    NPMplusProxyHostEntity,
    NPMplusRedirectionHostEntity,
    NPMplusStreamEntity,
)

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
    known_stream_ids: set[int] = set()
    known_dead_host_ids: set[int] = set()
    known_redirection_host_ids: set[int] = set()

    @callback
    def _add_new_entities() -> None:
        new_entities: list[SwitchEntity] = []

        new_host_ids = set(coordinator.data.proxy_hosts) - known_host_ids
        if new_host_ids:
            known_host_ids.update(new_host_ids)
            new_entities.extend(
                ProxyHostEnabledSwitch(coordinator, entry, host_id)
                for host_id in new_host_ids
            )

        new_stream_ids = set(coordinator.data.streams) - known_stream_ids
        if new_stream_ids:
            known_stream_ids.update(new_stream_ids)
            new_entities.extend(
                StreamEnabledSwitch(coordinator, entry, stream_id)
                for stream_id in new_stream_ids
            )

        new_dead_host_ids = set(coordinator.data.dead_hosts) - known_dead_host_ids
        if new_dead_host_ids:
            known_dead_host_ids.update(new_dead_host_ids)
            new_entities.extend(
                DeadHostEnabledSwitch(coordinator, entry, host_id)
                for host_id in new_dead_host_ids
            )

        new_redirection_host_ids = (
            set(coordinator.data.redirection_hosts) - known_redirection_host_ids
        )
        if new_redirection_host_ids:
            known_redirection_host_ids.update(new_redirection_host_ids)
            new_entities.extend(
                RedirectionHostEnabledSwitch(coordinator, entry, host_id)
                for host_id in new_redirection_host_ids
            )

        if new_entities:
            async_add_entities(new_entities)

    _add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_entities))


class ProxyHostEnabledSwitch(NPMplusProxyHostEntity, SwitchEntity):
    """Enable/disable a proxy host."""

    _attr_translation_key = "proxy_enabled"
    _attr_icon = "mdi:server-network"

    def __init__(
        self, coordinator: NPMplusDataUpdateCoordinator, entry: ConfigEntry, host_id: int
    ) -> None:
        super().__init__(coordinator, entry, host_id, "enabled")
        host = coordinator.data.proxy_hosts.get(host_id)
        domain_slug = slugify(host.primary_domain) if host else f"host_{host_id}"
        self.entity_id = f"switch.{PREFIX_PROXY}_{domain_slug}_enabled"

    @property
    def is_on(self) -> bool | None:
        host = self.proxy_host
        return host.enabled if host else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        host = self.proxy_host
        if not host:
            return {}
        return {
            "domain_names": host.domain_names,
            "forward_scheme": host.forward_scheme,
            "forward_host": host.forward_host,
            "forward_port": host.forward_port,
            "ssl_forced": host.ssl_forced,
            "hsts_enabled": host.hsts_enabled,
            "allow_websocket_upgrade": host.allow_websocket_upgrade,
            "http2_support": host.http2_support,
            "block_exploits": host.block_exploits,
            "caching_enabled": host.caching_enabled,
            "access_list_id": host.access_list_id,
            "nginx_online": host.nginx_online,
            "nginx_error": host.nginx_error,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.client.async_set_proxy_host_enabled(self.host_id, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.client.async_set_proxy_host_enabled(self.host_id, False)
        await self.coordinator.async_request_refresh()


class StreamEnabledSwitch(NPMplusStreamEntity, SwitchEntity):
    """Enable/disable a stream."""

    _attr_translation_key = "stream_enabled"
    _attr_icon = "mdi:swap-horizontal"

    def __init__(
        self,
        coordinator: NPMplusDataUpdateCoordinator,
        entry: ConfigEntry,
        stream_id: int,
    ) -> None:
        super().__init__(coordinator, entry, stream_id, "enabled")
        stream = coordinator.data.streams.get(stream_id)
        slug = stream.slug if stream else f"stream_{stream_id}"
        self.entity_id = f"switch.{PREFIX_STREAM}_{slug}_enabled"

    @property
    def name(self) -> str:
        """Use the stream's NPMplus description as the entity name, if set.

        The entity_id itself stays keyed off the incoming port (see
        __init__), so renaming the description in NPMplus later only
        changes the friendly name, not the entity_id.
        """
        stream = self.stream
        if not stream:
            return f"Stream {self.stream_id}"
        return stream.display_name

    @property
    def is_on(self) -> bool | None:
        stream = self.stream
        return stream.enabled if stream else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        stream = self.stream
        if not stream:
            return {}
        return {
            "incoming_port": stream.incoming_port,
            "destination_address": stream.forward_host,
            "destination_port": stream.forward_port,
            "protocol": stream.protocol,
            "ssl": stream.ssl,
            "description": stream.description,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.client.async_set_stream_enabled(self.stream_id, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.client.async_set_stream_enabled(self.stream_id, False)
        await self.coordinator.async_request_refresh()


class DeadHostEnabledSwitch(NPMplusDeadHostEntity, SwitchEntity):
    """Enable/disable a 404 ("dead") host."""

    _attr_translation_key = "dead_host_enabled"
    _attr_icon = "mdi:server-remove"

    def __init__(
        self, coordinator: NPMplusDataUpdateCoordinator, entry: ConfigEntry, host_id: int
    ) -> None:
        super().__init__(coordinator, entry, host_id, "enabled")
        host = coordinator.data.dead_hosts.get(host_id)
        domain_slug = slugify(host.primary_domain) if host else f"host_{host_id}"
        self.entity_id = f"switch.{PREFIX_DEAD_HOST}_{domain_slug}_enabled"

    @property
    def name(self) -> str:
        host = self.dead_host
        return host.primary_domain if host else f"404 host {self.host_id}"

    @property
    def is_on(self) -> bool | None:
        host = self.dead_host
        return host.enabled if host else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        host = self.dead_host
        if not host:
            return {}
        return {
            "domain_names": host.domain_names,
            "ssl_forced": host.ssl_forced,
            "hsts_enabled": host.hsts_enabled,
            "hsts_subdomains": host.hsts_subdomains,
            "http2_support": host.http2_support,
            "http3_support": host.http3_support,
            "nginx_online": host.nginx_online,
            "nginx_error": host.nginx_error,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.client.async_set_dead_host_enabled(self.host_id, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.client.async_set_dead_host_enabled(self.host_id, False)
        await self.coordinator.async_request_refresh()


class RedirectionHostEnabledSwitch(NPMplusRedirectionHostEntity, SwitchEntity):
    """Enable/disable a redirection host."""

    _attr_translation_key = "redirection_host_enabled"
    _attr_icon = "mdi:arrow-right-bold-box-outline"

    def __init__(
        self, coordinator: NPMplusDataUpdateCoordinator, entry: ConfigEntry, host_id: int
    ) -> None:
        super().__init__(coordinator, entry, host_id, "enabled")
        host = coordinator.data.redirection_hosts.get(host_id)
        domain_slug = slugify(host.primary_domain) if host else f"host_{host_id}"
        self.entity_id = f"switch.{PREFIX_REDIRECTION_HOST}_{domain_slug}_enabled"

    @property
    def name(self) -> str:
        host = self.redirection_host
        return host.primary_domain if host else f"Redirection host {self.host_id}"

    @property
    def is_on(self) -> bool | None:
        host = self.redirection_host
        return host.enabled if host else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        host = self.redirection_host
        if not host:
            return {}
        return {
            "domain_names": host.domain_names,
            "forward_domain_name": host.forward_domain_name,
            "forward_scheme": host.forward_scheme,
            "forward_http_code": host.forward_http_code,
            "preserve_path": host.preserve_path,
            "ssl_forced": host.ssl_forced,
            "block_exploits": host.block_exploits,
            "hsts_enabled": host.hsts_enabled,
            "hsts_subdomains": host.hsts_subdomains,
            "http2_support": host.http2_support,
            "http3_support": host.http3_support,
            "nginx_online": host.nginx_online,
            "nginx_error": host.nginx_error,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.client.async_set_redirection_host_enabled(
            self.host_id, True
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.client.async_set_redirection_host_enabled(
            self.host_id, False
        )
        await self.coordinator.async_request_refresh()
