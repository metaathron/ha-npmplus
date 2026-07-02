# NPMplus – Home Assistant Integration

Custom integration for Home Assistant that connects to [NPMplus](https://github.com/ZoeyVid/NPMplus) (a fork of [Nginx Proxy Manager](https://nginxproxymanager.com/)) and exposes proxy hosts, streams, 404 hosts and redirection hosts as devices with switches, sensors and buttons.

## Source project

<https://github.com/ZoeyVid/NPMplus>

---

## Installation

### Installation via HACS

1. Add this repository as a custom repository to HACS:

[![Add Repository](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=metaathron&repository=ha-npmplus&category=Integration)

2. Use HACS to install the integration.
3. Restart Home Assistant.
4. Set up the integration using the UI:

[![Add Integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=npmplus)

### Manual Installation

1. Download the integration files from the GitHub repository.
2. Place the `custom_components/npmplus` folder in the `custom_components` directory of Home Assistant.
3. Restart Home Assistant.
4. Set up the integration using the UI:

[![Add Integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=npmplus)

## Setup

1. Go to Settings → Devices & Services
2. Click "Add Integration"
3. Select NPMplus
4. Enter:
   - Host or IP address of your NPMplus instance
   - Port (admin UI / API, default `81`)
   - Email address and password of an NPMplus user
   - Whether to verify the SSL certificate (NPMplus commonly runs on a self-signed certificate on port 81 - leave this off unless you have a trusted certificate there)

Connection settings and credentials can be changed later from the integration's **Reconfigure** option, and the polling interval from its **Options**, without needing to remove and re-add the integration.

---

## Devices & Entities

### Proxy hosts

One device per proxy host (named after its primary domain), with:

- `switch.proxy_<domain>_enabled` - enable/disable the host. Attributes: `domain_names`, `forward_scheme`, `forward_host`, `forward_port`, `ssl_forced`, `hsts_enabled`, `allow_websocket_upgrade`, `http2_support`, `block_exploits`, `caching_enabled`, `access_list_id`, `nginx_online`, `nginx_error`
- `binary_sensor.proxy_<domain>_ssl_enabled` - whether a certificate is assigned
- `binary_sensor.proxy_<domain>_force_https` - whether HTTPS is forced
- `sensor.proxy_<domain>_certificate_expiration` - certificate expiration timestamp
- `sensor.proxy_<domain>_public_url` / `sensor.proxy_<domain>_local_url` - the state is the URL itself, so it can be used directly in automations or clickable Lovelace cards
- `button.proxy_<domain>_renew_certificate` - force-renew the assigned certificate. Automatically unavailable for custom/uploaded certificates, which can't be renewed through the API

### Streams

One shared "Streams" device, with `switch.stream_port_<port>_enabled` per stream. Attributes: `incoming_port`, `destination_address`, `destination_port`, `protocol`, `ssl`, `description`. If a stream has an NPMplus description set, it's used as the entity's friendly name.

### 404 hosts

One shared "404 Hosts" device, with `switch.error404_<domain>_enabled` per host. Attributes: `domain_names`, `ssl_forced`, `hsts_enabled`, `hsts_subdomains`, `http2_support`, `http3_support`, `nginx_online`, `nginx_error`.

### Redirection hosts

One shared "Redirection Hosts" device, with `switch.redirect_<domain>_enabled` per host. Attributes: `domain_names`, `forward_domain_name`, `forward_scheme`, `forward_http_code`, `preserve_path`, `ssl_forced`, `block_exploits`, `hsts_enabled`, `hsts_subdomains`, `http2_support`, `http3_support`, `nginx_online`, `nginx_error`.

### NPMplus server overview

One "NPMplus" device with aggregated counters:

- Proxy hosts: total / enabled / disabled
- Streams: total / enabled / disabled
- 404 hosts: total / enabled / disabled
- Redirection hosts: total / enabled / disabled
- Certificates: expiring within 14 days, expiring within 7 days, already expired

---

## Features

- Dynamic device/entity creation and removal - hosts and streams added or removed in NPMplus are automatically reflected in Home Assistant without a restart.
- Full configuration and reconfiguration from the UI, including credentials, SSL verification and polling interval.
- Diagnostics download support (Settings → Devices & Services → NPMplus → Download diagnostics), with credentials redacted.

## Notes

- NPMplus does not track real upstream reachability for a proxy host, so this integration does not expose an online/offline sensor for hosts - the `enabled`/`disabled` switch state is the source of truth on the NPMplus side. The `nginx_online`/`nginx_error` fields NPMplus reports (whether nginx itself could load the host's config) are exposed as attributes on the relevant switch entities instead.

---

## Support

If you find this integration useful, you can support the development:

[![Buy Me a Coffee](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://buymeacoffee.com/metaathron)

---

## License

This project is licensed under the MIT License.

Copyright (c) 2026 [metaathron](https://github.com/metaathron/)

You are free to use, modify, and distribute this software in accordance with the MIT License.

If you find this project useful, attribution and a link back to the original repository are appreciated:
<https://github.com/metaathron/ha-npmplus>
