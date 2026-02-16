[![Last image-template](https://img.shields.io/badge/last%20template%20update-v0.1.3-informational)](https://github.com/Tecnativa/image-template/tree/v0.1.3)
[![GitHub Container Registry](https://img.shields.io/badge/GitHub%20Container%20Registry-latest-%2324292e)](https://github.com/orgs/Tecnativa/packages/container/package/docker-whitelist)
[![Docker Hub](https://img.shields.io/badge/Docker%20Hub-latest-%23099cec)](https://hub.docker.com/r/tecnativa/whitelist)
[![Docker Pulls](https://img.shields.io/docker/pulls/tecnativa/whitelist.svg)](https://hub.docker.com/r/tecnativa/whitelist)
[![Layers](https://images.microbadger.com/badges/image/tecnativa/whitelist.svg)](https://microbadger.com/images/tecnativa/whitelist)
[![Commit](https://images.microbadger.com/badges/commit/tecnativa/whitelist.svg)](https://microbadger.com/images/tecnativa/whitelist)
[![License](https://images.microbadger.com/badges/license/tecnativa/whitelist.svg)](https://microbadger.com/images/tecnativa/whitelist)

# Docker Whitelister

## What?

A transparent TCP whitelist proxy based on iptables and asyncio.

## Why?

Docker supports internal networks; but when you use them, you cannot
open outbound connections unless the container is attached to a public
network.

This proxy allows selected external endpoints to be reachable from
containers attached to restricted internal networks.

Typical use cases:

-   Allowing connections only to specific external APIs.
-   Allowing limited outbound access while keeping containers isolated.
-   Whitelisting external services such as SMTP, payment gateways,
    font/CDN APIs, etc.

## How?

The proxy works by:

-   Installing iptables NAT REDIRECT rules (requires `CAP_NET_ADMIN`)
-   Running a single TCP listener
-   Redirecting inbound traffic to that listener
-   Recovering the original destination port using `SO_ORIGINAL_DST`
-   Forwarding traffic to `TARGET:<original_port>`

Unlike previous versions, this implementation:

-   Does not spawn one process per port
-   Uses a single async TCP server
-   Scales better under load
-   Handles DNS refresh more reliably

## Required capability

This implementation requires:

``` yaml
cap_add:
  - NET_ADMIN
```

Without this capability, the container cannot configure iptables and
will fail at startup.

## Environment variables

### TARGET

Required. Hostname where incoming connections will be forwarded.

### PORT

Default: `*` (all TCP ports allowed)

Defines which TCP ports are redirected and proxied.

Examples:

Allow all ports (default):

``` yaml
environment:
  TARGET: api.example.com
```

Restrict to HTTPS only:

``` yaml
environment:
  TARGET: api.example.com
  PORT: "443"
```

Multiple ports:

``` yaml
environment:
  TARGET: api.example.com
  PORT: "80 443 8080"
```

Port ranges:

``` yaml
environment:
  TARGET: ftp.example.com
  PORT: "21 50000-51000"
```

If `PORT` is not set, all TCP ports are allowed.

### PRE_RESOLVE

Default: `0`

Set to `1` to resolve `TARGET` using the configured `NAMESERVERS`
instead of the system resolver.

When enabled, DNS is refreshed periodically.

### RESOLVE_INTERVAL

Default: `60`

Interval in seconds to refresh DNS resolution when `PRE_RESOLVE=1`.

If the IP changes, new connections automatically use the new address.

### NAMESERVERS

Default: 208.67.222.222 8.8.8.8 208.67.220.220 8.8.4.4

Used only when `PRE_RESOLVE=1`.

### LISTEN_PORT

Default: `15000`

Internal port where the proxy listens after iptables redirection.

### HTTP_HEALTHCHECK

Default: `0`

Set to `1` to enable HTTP-based healthcheck using pycurl.

### HTTP_HEALTHCHECK_URL

Default: `http://$TARGET/`

### HTTP_HEALTHCHECK_TIMEOUT_MS

Default: `2000`

### SMTP_HEALTHCHECK

Default: `0`

Set to `1` to enable SMTP healthcheck using pycurl.

### SMTP_HEALTHCHECK_URL

Default: `smtp://$TARGET/`

### SMTP_HEALTHCHECK_COMMAND

Default: `HELP`

### SMTP_HEALTHCHECK_TIMEOUT_MS

Default: `2000`

### VERBOSE

Default: `0`

Set to `1` to log all connections.

## Example

``` yaml
services:
  fonts_googleapis_proxy:
    image: ghcr.io/tecnativa/docker-whitelist:latest
    cap_add:
      - NET_ADMIN
    networks:
      default:
        aliases:
          - fonts.googleapis.com
      public:
    environment:
      TARGET: fonts.googleapis.com
      PRE_RESOLVE: 1
```
