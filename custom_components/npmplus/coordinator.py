"""DataUpdateCoordinator for the NPMplus integration."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from homeassistant.config_entries import ConfigEntry, ConfigEntryAuthFailed
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import NPMplusApiError, NPMplusAuthError, NPMplusClient
from .api import _parse_datetime as _parse_dt
from .const import CERT_EXPIRY_CRITICAL_DAYS, CERT_EXPIRY_WARNING_DAYS, DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class CertificateData:
    """A single NPMplus certificate."""

    id: int
    nice_name: str
    domain_names: list[str]
    provider: str
    expires_on: datetime | None

    @property
    def is_renewable(self) -> bool:
        """Only ACME (Let's Encrypt) certificates can be force-renewed via the API.

        Custom/uploaded certificates (provider "other") have no ACME account
        behind them, so the renew endpoint has nothing to renew.
        """
        return self.provider == "letsencrypt"


def _meta_fields(item: dict) -> tuple[bool | None, str | None]:
    """Extract the (nginx_online, nginx_err) diagnostic fields NPMplus attaches to hosts."""
    meta = item.get("meta") or {}
    return meta.get("nginx_online"), meta.get("nginx_err")


@dataclass
class ProxyHostData:
    """A single NPMplus proxy host, with certificate data merged in."""

    id: int
    domain_names: list[str]
    primary_domain: str
    enabled: bool
    forward_scheme: str
    forward_host: str
    forward_port: int
    certificate_id: int | None
    ssl_forced: bool
    hsts_enabled: bool
    allow_websocket_upgrade: bool
    http2_support: bool
    block_exploits: bool
    caching_enabled: bool
    access_list_id: int | None
    certificate_expires_on: datetime | None = None
    certificate_renewable: bool = False
    nginx_online: bool | None = None
    nginx_error: str | None = None

    @property
    def slug(self) -> str:
        return self.primary_domain

    @property
    def ssl_enabled(self) -> bool:
        return self.certificate_id is not None and self.certificate_id != 0

    @property
    def public_url(self) -> str:
        scheme = "https" if (self.ssl_enabled or self.ssl_forced) else "http"
        return f"{scheme}://{self.primary_domain}"

    @property
    def local_url(self) -> str:
        return f"{self.forward_scheme}://{self.forward_host}:{self.forward_port}"


@dataclass
class StreamData:
    """A single NPMplus stream."""

    id: int
    incoming_port: int
    forward_host: str
    forward_port: int
    tcp_forwarding: bool
    udp_forwarding: bool
    enabled: bool
    certificate_id: int | None
    description: str | None = None

    @property
    def slug(self) -> str:
        return f"port_{self.incoming_port}"

    @property
    def protocol(self) -> str:
        if self.tcp_forwarding and self.udp_forwarding:
            return "tcp+udp"
        if self.udp_forwarding:
            return "udp"
        return "tcp"

    @property
    def ssl(self) -> bool:
        return self.certificate_id is not None and self.certificate_id != 0

    @property
    def display_name(self) -> str:
        return self.description if self.description else f"Port {self.incoming_port}"


@dataclass
class DeadHostData:
    """A single NPMplus 404 ("dead") host."""

    id: int
    domain_names: list[str]
    primary_domain: str
    enabled: bool
    certificate_id: int | None
    ssl_forced: bool
    hsts_enabled: bool
    hsts_subdomains: bool
    http2_support: bool
    http3_support: bool
    nginx_online: bool | None = None
    nginx_error: str | None = None
    certificate_expires_on: datetime | None = None
    certificate_renewable: bool = False

    @property
    def slug(self) -> str:
        return self.primary_domain

    @property
    def ssl_enabled(self) -> bool:
        return self.certificate_id is not None and self.certificate_id != 0


@dataclass
class RedirectionHostData:
    """A single NPMplus redirection host."""

    id: int
    domain_names: list[str]
    primary_domain: str
    enabled: bool
    forward_domain_name: str
    forward_scheme: str
    forward_http_code: int
    preserve_path: bool
    certificate_id: int | None
    ssl_forced: bool
    block_exploits: bool
    hsts_enabled: bool
    hsts_subdomains: bool
    http2_support: bool
    http3_support: bool
    nginx_online: bool | None = None
    nginx_error: str | None = None
    certificate_expires_on: datetime | None = None
    certificate_renewable: bool = False

    @property
    def slug(self) -> str:
        return self.primary_domain

    @property
    def ssl_enabled(self) -> bool:
        return self.certificate_id is not None and self.certificate_id != 0

    @property
    def target_url(self) -> str:
        return f"{self.forward_scheme}://{self.forward_domain_name}"


@dataclass
class ServerSummary:
    """Aggregated counters shown on the NPMplus server device."""

    proxy_hosts_total: int = 0
    proxy_hosts_enabled: int = 0
    proxy_hosts_disabled: int = 0
    streams_total: int = 0
    streams_enabled: int = 0
    streams_disabled: int = 0
    certificates_expiring_14d: int = 0
    certificates_expiring_7d: int = 0
    certificates_expired: int = 0


@dataclass
class NPMplusData:
    """Container for a single coordinator refresh result."""

    proxy_hosts: dict[int, ProxyHostData] = field(default_factory=dict)
    streams: dict[int, StreamData] = field(default_factory=dict)
    dead_hosts: dict[int, DeadHostData] = field(default_factory=dict)
    redirection_hosts: dict[int, RedirectionHostData] = field(default_factory=dict)
    certificates: dict[int, CertificateData] = field(default_factory=dict)
    summary: ServerSummary = field(default_factory=ServerSummary)


class NPMplusDataUpdateCoordinator(DataUpdateCoordinator[NPMplusData]):
    """Coordinator that polls the NPMplus API."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: NPMplusClient,
        update_interval,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
            # Always notify listeners after a refresh, even if the newly
            # fetched data happens to compare equal to the previous data.
            # Our own device/entity pruning logic (see __init__.py) relies
            # on running after every refresh cycle, not just on changes.
            always_update=True,
        )
        self.entry = entry
        self.client = client

    async def _async_update_data(self) -> NPMplusData:
        try:
            raw_hosts = await self.client.async_get_proxy_hosts()
            raw_streams = await self.client.async_get_streams()
            raw_certs = await self.client.async_get_certificates()
            raw_dead_hosts = await self.client.async_get_dead_hosts()
            raw_redirection_hosts = await self.client.async_get_redirection_hosts()
        except NPMplusAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except NPMplusApiError as err:
            raise UpdateFailed(str(err)) from err

        certificates = {
            cert["id"]: CertificateData(
                id=cert["id"],
                nice_name=cert.get("nice_name", ""),
                domain_names=cert.get("domain_names", []),
                provider=cert.get("provider", "other"),
                expires_on=_parse_dt(cert.get("expires_on")),
            )
            for cert in raw_certs
        }

        def _cert_for(certificate_id: int | None) -> CertificateData | None:
            return certificates.get(certificate_id) if certificate_id else None

        proxy_hosts: dict[int, ProxyHostData] = {}
        for item in raw_hosts:
            domain_names = item.get("domain_names") or ["unknown"]
            certificate_id = item.get("certificate_id") or None
            cert = _cert_for(certificate_id)
            nginx_online, nginx_error = _meta_fields(item)
            proxy_hosts[item["id"]] = ProxyHostData(
                id=item["id"],
                domain_names=domain_names,
                primary_domain=domain_names[0],
                enabled=bool(item.get("enabled", True)),
                forward_scheme=item.get("forward_scheme", "http"),
                forward_host=item.get("forward_host", ""),
                forward_port=item.get("forward_port", 0),
                certificate_id=certificate_id,
                ssl_forced=bool(item.get("ssl_forced", False)),
                hsts_enabled=bool(item.get("hsts_enabled", False)),
                allow_websocket_upgrade=bool(
                    item.get("allow_websocket_upgrade", False)
                ),
                http2_support=bool(item.get("http2_support", False)),
                block_exploits=bool(item.get("block_exploits", False)),
                caching_enabled=bool(item.get("caching_enabled", False)),
                access_list_id=item.get("access_list_id") or None,
                certificate_expires_on=cert.expires_on if cert else None,
                certificate_renewable=cert.is_renewable if cert else False,
                nginx_online=nginx_online,
                nginx_error=nginx_error,
            )

        streams: dict[int, StreamData] = {}
        for item in raw_streams:
            streams[item["id"]] = StreamData(
                id=item["id"],
                incoming_port=item.get("incoming_port", 0),
                forward_host=item.get("forwarding_host", item.get("forward_host", "")),
                forward_port=item.get(
                    "forwarding_port", item.get("forward_port", 0)
                ),
                tcp_forwarding=bool(item.get("tcp_forwarding", True)),
                udp_forwarding=bool(item.get("udp_forwarding", False)),
                enabled=bool(item.get("enabled", True)),
                certificate_id=item.get("certificate_id") or None,
                description=item.get("npmplus_description") or None,
            )

        dead_hosts: dict[int, DeadHostData] = {}
        for item in raw_dead_hosts:
            domain_names = item.get("domain_names") or ["unknown"]
            certificate_id = item.get("certificate_id") or None
            cert = _cert_for(certificate_id)
            nginx_online, nginx_error = _meta_fields(item)
            dead_hosts[item["id"]] = DeadHostData(
                id=item["id"],
                domain_names=domain_names,
                primary_domain=domain_names[0],
                enabled=bool(item.get("enabled", True)),
                certificate_id=certificate_id,
                ssl_forced=bool(item.get("ssl_forced", False)),
                hsts_enabled=bool(item.get("hsts_enabled", False)),
                hsts_subdomains=bool(item.get("hsts_subdomains", False)),
                http2_support=bool(item.get("http2_support", False)),
                http3_support=bool(item.get("npmplus_http3_support", False)),
                nginx_online=nginx_online,
                nginx_error=nginx_error,
                certificate_expires_on=cert.expires_on if cert else None,
                certificate_renewable=cert.is_renewable if cert else False,
            )

        redirection_hosts: dict[int, RedirectionHostData] = {}
        for item in raw_redirection_hosts:
            domain_names = item.get("domain_names") or ["unknown"]
            certificate_id = item.get("certificate_id") or None
            cert = _cert_for(certificate_id)
            nginx_online, nginx_error = _meta_fields(item)
            redirection_hosts[item["id"]] = RedirectionHostData(
                id=item["id"],
                domain_names=domain_names,
                primary_domain=domain_names[0],
                enabled=bool(item.get("enabled", True)),
                forward_domain_name=item.get("forward_domain_name", ""),
                forward_scheme=item.get("forward_scheme", "http"),
                forward_http_code=item.get("forward_http_code", 301),
                preserve_path=bool(item.get("preserve_path", False)),
                certificate_id=certificate_id,
                ssl_forced=bool(item.get("ssl_forced", False)),
                block_exploits=bool(item.get("block_exploits", False)),
                hsts_enabled=bool(item.get("hsts_enabled", False)),
                hsts_subdomains=bool(item.get("hsts_subdomains", False)),
                http2_support=bool(item.get("http2_support", False)),
                http3_support=bool(item.get("npmplus_http3_support", False)),
                nginx_online=nginx_online,
                nginx_error=nginx_error,
                certificate_expires_on=cert.expires_on if cert else None,
                certificate_renewable=cert.is_renewable if cert else False,
            )

        summary = _build_summary(proxy_hosts, streams, certificates)

        return NPMplusData(
            proxy_hosts=proxy_hosts,
            streams=streams,
            dead_hosts=dead_hosts,
            redirection_hosts=redirection_hosts,
            certificates=certificates,
            summary=summary,
        )


def _build_summary(
    proxy_hosts: dict[int, ProxyHostData],
    streams: dict[int, StreamData],
    certificates: dict[int, CertificateData],
) -> ServerSummary:
    summary = ServerSummary()

    summary.proxy_hosts_total = len(proxy_hosts)
    summary.proxy_hosts_enabled = sum(1 for h in proxy_hosts.values() if h.enabled)
    summary.proxy_hosts_disabled = (
        summary.proxy_hosts_total - summary.proxy_hosts_enabled
    )

    summary.streams_total = len(streams)
    summary.streams_enabled = sum(1 for s in streams.values() if s.enabled)
    summary.streams_disabled = summary.streams_total - summary.streams_enabled

    now = datetime.now(timezone.utc)
    for cert in certificates.values():
        if not cert.expires_on:
            continue
        delta_days = (cert.expires_on - now).days
        if delta_days < 0:
            summary.certificates_expired += 1
        elif delta_days <= CERT_EXPIRY_CRITICAL_DAYS:
            summary.certificates_expiring_7d += 1
        elif delta_days <= CERT_EXPIRY_WARNING_DAYS:
            summary.certificates_expiring_14d += 1

    return summary
