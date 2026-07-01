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

## Features

- **Proxy hosts** - one device per host, with:
  - a switch to enable/disable the host (with forwarding, SSL and security settings as attributes)
  - binary sensors for SSL enabled and forced HTTPS
  - a certificate expiration sensor
  - public URL and local (upstream) URL sensors
  - a button to force-renew the assigned certificate (automatically disabled for custom/uploaded certificates, which can't be renewed through the API)
- **Streams** - one shared device, with a switch per stream (incoming port, destination, protocol and SSL as attributes). If a stream has an NPMplus description set, it's used as the entity's friendly name.
- **404 hosts** and **redirection hosts** - one shared device each, with a switch per host and its relevant settings as attributes.
- **NPMplus server overview** - a device with aggregated counters: proxy hosts (total/enabled/disabled), streams (total/enabled/disabled), and certificates expiring within 14 days, within 7 days, or already expired.
- Dynamic device/entity creation and removal - hosts and streams added or removed in NPMplus are automatically reflected in Home Assistant without a restart.
- Full configuration and reconfiguration from the UI, including credentials, SSL verification and polling interval.
- Diagnostics download support (Settings → Devices & Services → NPMplus → Download diagnostics), with credentials redacted.

---

## Notes and limitations

- NPMplus does not track real upstream reachability for a proxy host, so this integration does not expose an online/offline sensor for hosts - the `enabled`/`disabled` switch state is the source of truth on the NPMplus side. The `nginx_online`/`nginx_error` fields NPMplus reports (whether nginx itself could load the host's config) are exposed as attributes on the relevant switch entities.

## License

This project is free to use, modify, and distribute.

Author: metaathron
Please retain attribution and link to the original repository: <https://github.com/metaathron/ha-npmplus>
