# Docker Whitelister

[![Docker Pulls](https://img.shields.io/docker/pulls/tecnativa/whitelist.svg)](https://hub.docker.com/r/tecnativa/whitelist)
[![Layers](https://images.microbadger.com/badges/image/tecnativa/whitelist.svg)](https://microbadger.com/images/tecnativa/whitelist)
[![Commit](https://images.microbadger.com/badges/commit/tecnativa/whitelist.svg)](https://microbadger.com/images/tecnativa/whitelist)
[![License](https://images.microbadger.com/badges/license/tecnativa/whitelist.svg)](https://microbadger.com/images/tecnativa/whitelist)

## What?

A whitelist proxy that uses netcat. 🔌😼

## Why?

tl;dr: To workaround https://github.com/moby/moby/issues/36174.

Basically, Docker supports internal networks; but when you use them, you simply cannot open ports from those services, which is not very convenient: you either have full or none isolation.

This proxy allows some whitelist endpoints to have network connectivity. It can be used for:

- Allowing connection only to some APIs, but not to the rest of the WWW.
- Exposing ports from a container while still not letting the container access the WWW.

## How?

Use these environment variables:

### `TARGET`

Required. It's the host name where the incoming connections will be redirected to.


### `NAMESERVERS`

Default: `208.67.222.222 8.8.8.8 208.67.220.220 8.8.4.4` to use OpenDNS and Google DNS resolution servers by default.

Only used when [pre-resolving](#pre-resolve) is enabled.

### `PORT`

Default: `443`. If you're proxying HTTPS services, no need to specify!

The port where this service will listen, and where the [target](#target) service is expected to be listening on also.

### `PRE_RESOLVE`

Default: `0`

Set to `1` to force using the specified [nameservers](#nameservers) to resolve the [target](#target) before proxying.

This is especially useful when using a network alias to whitelist an external API.

### `UDP`

Default: `0`

Set to `1` to proxy in UDP mode.

### `VERBOSE`

Default: `0`

Set to `1` to log all connections.

## Example

So say you have a production app called `coolapp` that sends and reads emails, and uses Google Font APIs to render some PDF reports.

It is defined in a `docker-compose.yaml` file like this:

```yaml
# Production deployment
version: "2.0"
services:
    app:
        image: Tecnativa/coolapp
        ports:
            - "80:80"
        environment:
            DB_HOST: db
        depends_on:
            - db

    db:
        image: postgres:alpine
        volumes:
            - dbvol:/var/lib/postgresql/data:z

volumes:
    dbvol:
```

Now you want to set up a staging environment for your QA team, which includes a fresh copy of the production database. To avoid the app to send or read emails, you put all into a safe internal network:

```yaml
# Staging deployment
version: "2.0"
services:
    proxy:
        image: traefik
        networks:
            default:
            public:
        ports:
            - "8080:8080"
        volumes:
            # Here you redirect incoming connections to the app container
            - /etc/traefik/traefik.toml

    app:
        image: Tecnativa/coolapp
        environment:
            DB_HOST: db
        depends_on:
            - db

    db:
        image: postgres:alpine

networks:
    default:
        internal: true
    public:
```

Now, it turns out your QA detects font problems. Logic! `app` cannot contact `fonts.google.com`. Yikes! What to do? 🤷

`tecnativa/whitelist` to the rescue!! 💪🤠

```yaml
# Staging deployment
version: "2.0"
services:
    fonts_googleapis_proxy:
        image: tecnativa/whitelist
        environment:
            TARGET: fonts.googleapis.com
            PRE_RESOLVE: 1 # Otherwise it would resolve to localhost
        networks:
            # Containers in default restricted network will ask here for fonts
            default:
                aliases:
                    - fonts.googleapis.com
            # We need public access to "open the door"
            public:

    fonts_gstatic_proxy:
        image: tecnativa/whitelist
        networks:
            default:
                aliases:
                    - fonts.gstatic.com
            public:
        environment:
            TARGET: fonts.gstatic.com
            PRE_RESOLVE: 1

    proxy:
        image: traefik
        networks:
            default:
            public:
        ports:
            - "8080:8080"
        volumes:
            # Here you redirect incoming connections to the app container
            - /etc/traefik/traefik.toml

    app:
        image: Tecnativa/coolapp
        environment:
            DB_HOST: db
        depends_on:
            - db

    db:
        image: postgres:alpine

networks:
    default:
        internal: true
    public:
```

And voilà! `app` has fonts, but nothing more. ✋👮
