"""Constants for the NPMplus integration."""
from __future__ import annotations

from datetime import timedelta

DOMAIN = "npmplus"

CONF_VERIFY_SSL = "verify_ssl"

DEFAULT_PORT = 81
DEFAULT_VERIFY_SSL = False
DEFAULT_SCAN_INTERVAL = 60  # seconds
MIN_SCAN_INTERVAL = 15

UPDATE_INTERVAL = timedelta(seconds=DEFAULT_SCAN_INTERVAL)

# Thresholds (days) for certificate expiration "soon" sensors on the server device
CERT_EXPIRY_WARNING_DAYS = 14
CERT_EXPIRY_CRITICAL_DAYS = 7

MANUFACTURER = "NPMplus"

# Device identifiers (sub-identifier appended to the config entry id)
DEVICE_SERVER = "server"
DEVICE_STREAMS = "streams"
DEVICE_DEAD_HOSTS = "dead_hosts"
DEVICE_REDIRECTION_HOSTS = "redirection_hosts"

# Entity id prefixes, kept distinct so other host types (redirection, 404)
# can be added later without colliding with proxy host entities.
PREFIX_PROXY = "proxy"
PREFIX_STREAM = "stream"
PREFIX_DEAD_HOST = "error404"
PREFIX_REDIRECTION_HOST = "redirect"

ATTRIBUTION = "Data provided by NPMplus"
