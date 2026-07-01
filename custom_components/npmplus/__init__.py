"""The NPMplus integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import NPMplusClient
from .config_flow import CONF_SCAN_INTERVAL
from .const import CONF_VERIFY_SSL, DEFAULT_SCAN_INTERVAL, DOMAIN
from .coordinator import NPMplusDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SWITCH,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.BUTTON,
]

# Unique-id prefixes for entities that live on a *shared* device (Streams,
# 404 Hosts, Redirection Hosts). These are pruned at the entity level.
# Proxy hosts get their own per-host device and are pruned at the device
# level instead (see _async_prune_stale).
_SHARED_DEVICE_ENTITY_PREFIXES = ("stream_", "dead_", "redirect_")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up NPMplus from a config entry."""
    session = async_get_clientsession(hass, verify_ssl=entry.data[CONF_VERIFY_SSL])
    client = NPMplusClient(
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        identity=entry.data[CONF_USERNAME],
        secret=entry.data[CONF_PASSWORD],
        verify_ssl=entry.data[CONF_VERIFY_SSL],
        session=session,
    )

    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    coordinator = NPMplusDataUpdateCoordinator(
        hass, entry, client, timedelta(seconds=scan_interval)
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"coordinator": coordinator}

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    @callback
    def _on_coordinator_update() -> None:
        _async_prune_stale(hass, entry, coordinator)

    entry.async_on_unload(coordinator.async_add_listener(_on_coordinator_update))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when options (e.g. scan interval) change."""
    await hass.config_entries.async_reload(entry.entry_id)


def _async_prune_stale(
    hass: HomeAssistant, entry: ConfigEntry, coordinator: NPMplusDataUpdateCoordinator
) -> None:
    """Remove devices/entities that no longer exist in NPMplus.

    Runs after every coordinator refresh.

    - Proxy hosts each have their own device, so when a host disappears from
      NPMplus we remove the whole device (which cascades to all of its
      entities automatically).
    - Streams, 404 hosts and redirection hosts share a single device each
      ("Streams", "404 Hosts", "Redirection Hosts"), so those are pruned at
      the entity level instead of removing the shared device.
    """
    try:
        device_registry = dr.async_get(hass)
        entity_registry = er.async_get(hass)

        current_host_ids = set(coordinator.data.proxy_hosts)
        current_stream_ids = set(coordinator.data.streams)
        current_dead_host_ids = set(coordinator.data.dead_hosts)
        current_redirection_host_ids = set(coordinator.data.redirection_hosts)

        proxy_prefix = f"{entry.entry_id}_proxy_"
        removed_devices = 0
        for device in dr.async_entries_for_config_entry(
            device_registry, entry.entry_id
        ):
            for device_domain, identifier in device.identifiers:
                if device_domain != DOMAIN or not identifier.startswith(proxy_prefix):
                    continue
                host_id_str = identifier[len(proxy_prefix) :]
                if not host_id_str.isdigit():
                    continue
                if int(host_id_str) not in current_host_ids:
                    _LOGGER.debug(
                        "Removing stale NPMplus proxy host device %s (id=%s)",
                        device.name,
                        host_id_str,
                    )
                    device_registry.async_remove_device(device.id)
                    removed_devices += 1

        current_by_prefix = {
            "stream_": current_stream_ids,
            "dead_": current_dead_host_ids,
            "redirect_": current_redirection_host_ids,
        }

        removed_entities = 0
        for reg_entry in er.async_entries_for_config_entry(
            entity_registry, entry.entry_id
        ):
            unique_id = reg_entry.unique_id
            # unique_id format: "<entry_id>_<prefix><item_id>_<suffix>"
            if not unique_id.startswith(f"{entry.entry_id}_"):
                continue
            remainder = unique_id[len(entry.entry_id) + 1 :]
            for prefix, current_ids in current_by_prefix.items():
                if not remainder.startswith(prefix):
                    continue
                item_id_str = remainder[len(prefix) :].split("_", 1)[0]
                if item_id_str.isdigit() and int(item_id_str) not in current_ids:
                    _LOGGER.debug(
                        "Removing stale NPMplus entity %s (unique_id=%s)",
                        reg_entry.entity_id,
                        unique_id,
                    )
                    entity_registry.async_remove(reg_entry.entity_id)
                    removed_entities += 1
                break

        if removed_devices or removed_entities:
            _LOGGER.info(
                "NPMplus cleanup: removed %d device(s) and %d entity/entities "
                "no longer present on the server",
                removed_devices,
                removed_entities,
            )
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Error while pruning stale NPMplus devices/entities")
