[![Last image-template](https://img.shields.io/badge/last%20template%20update-v0.1.3-informational)](https://github.com/Tecnativa/image-template/tree/v0.1.3)
[![GitHub Container Registry](https://img.shields.io/badge/GitHub%20Container%20Registry-latest-%2324292e)](https://github.com/orgs/Tecnativa/packages/container/package/docker-whitelist)
[![Docker Hub](https://img.shields.io/badge/Docker%20Hub-latest-%23099cec)](https://hub.docker.com/r/tecnativa/whitelist)
[![Docker Pulls](https://img.shields.io/docker/pulls/tecnativa/whitelist.svg)](https://hub.docker.com/r/tecnativa/whitelist)
[![Layers](https://images.microbadger.com/badges/image/tecnativa/whitelist.svg)](https://microbadger.com/images/tecnativa/whitelist)
[![Commit](https://images.microbadger.com/badges/commit/tecnativa/whitelist.svg)](https://microbadger.com/images/tecnativa/whitelist)
[![License](https://images.microbadger.com/badges/license/tecnativa/whitelist.svg)](https://microbadger.com/images/tecnativa/whitelist)

# Docker Whitelister

## What?

A whitelist proxy that uses socat. 🔌😼

## Why?

tl;dr: To workaround https://github.com/moby/moby/issues/36174.

Basically, Docker supports internal networks; but when you use them, you simply cannot
open ports from those services, which is not very convenient: you either have full or
none isolation.

This proxy allows some whitelist endpoints to have network connectivity. It can be used
for:

-   Allowing connection only to some APIs, but not to the rest of the WWW.
-   Exposing ports from a container while still not letting the container access the
    WWW.

## How?

Use these environment variables:

### `TARGET`

Required. It's the host name where the incoming connections will be redirected to.

### `HTTP_HEALTHCHECK`

Default: `0`

Set to `1` to enable healthcheck with pycurl http requests. This is useful if the target
uses a deployment where the ip of the service gets changed frequently (e.g.
`accounts.google.com`) and you are using [`PRE_RESOLVE`](#pre_resolve)

#### Automatically restarting unhealthy proxies

When you enable the http healthcheck the container marks itself as unhealthy but does
nothing. (see https://github.com/moby/moby/pull/22719)

If you want to restart your proxies automatically, you can use
https://github.com/willfarrell/docker-autoheal.

### `HTTP_HEALTHCHECK_URL`

Default: `http://$TARGET/`

Url to use in [`HTTP_HEALTHCHECK`](#http_healthcheck) if enabled. `$TARGET` gets
replaced inside the url by the configured [`TARGET`](#target).

### `MODE`

Default: `tcp`

Set to `udp` to proxy in UDP mode.

### `MAX_CONNECTIONS`

Default: `100`

Limits the maximum number of accepted connections at once per port.

#### Setting "unlimited" connections

For each port and open connection a subprocess is spawned. Setting a number too high
might make your host system unresponsive and prevent you from logging in to it. So be
very careful with setting this setting to a large number.

The typical linux system can handle up to 32768 so if you need a lot more parallel open
connections make sure to also set the corresponding variables on your host system. See
https://stackoverflow.com/questions/6294133/maximum-pid-in-linux for reference. And
divide this number by at least the number of ports you are running through
docker-whitelist.

#### What happens when the limit is hit?

docker-whitelist basically starts `socat` so the behaviour is the same. In case no more
subprocesses can be forked:

-   UDP mode: You won't see a difference on the connecting side. But no more packets are
    forwarded for new connections until the number of connections for this port is
    reduced.
-   TCP mode: docker-whitelist no longer accepts the connection and your connection will
    wait until the number of connections for this port is reduced. Your connection may
    time out.

### `NAMESERVERS`

Default: `208.67.222.222 8.8.8.8 208.67.220.220 8.8.4.4` to use OpenDNS and Google DNS
resolution servers by default.

Only used when [pre-resolving](#pre-resolve) is enabled.

### `PORT`

Default: `80 443`. If you're proxying HTTP/S services, no need to specify!

The port where this service will listen, and where the [target](#target) service is
expected to be listening on also.

### `PRE_RESOLVE`

Default: `0`

Set to `1` to force using the specified [nameservers](#nameservers) to resolve the
[target](#target) before proxying.

This is especially useful when using a network alias to whitelist an external API.

### `SMTP_HEALTHCHECK`

Default: `0`

Set to `1` to enable healthcheck with pycurl smtp requests. This is useful if the target
uses a deployment where the ip of the service gets changed frequently (e.g.
`smtp.eu.sparkpostmail.com`) and you are using [`PRE_RESOLVE`](#pre_resolve)

#### Automatically restarting unhealthy proxies

see [HTTP_HEALTHCHECK](#http_healthcheck)

### `SMTP_HEALTHCHECK_URL`

Default: `smtp://$TARGET/`

Url to use in [`SMTP_HEALTHCHECK`](#smtp_healthcheck) if enabled. `$TARGET` gets
replaced inside the url by the configured [`TARGET`](#target).

### `SMTP_HEALTHCHECK_COMMAND`

Default: `HELP`

Enables changing the healthcheck command for servers that do not support `HELP` (e.g.
for [MailHog](https://github.com/mailhog/MailHog) you can use `QUIT`)

### `UDP_ANSWERS`

Default: `1`

`1` means the process will wait for an answer from the server before the forked child
process terminates (until this happens the connection counts towards the connection
limit). Set to `0` if no answers are expected from the server, this prevents
subprocesses waiting for an answer indefinitely.

Setting to `0` is recommended if you are using this to connect to a syslog server like
graylog.

### `VERBOSE`

Default: `0`

Set to `1` to log all connections.

## Example

So say you have a production app called `coolapp` that sends and reads emails, and uses
Google Font APIs to render some PDF reports.

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

Now you want to set up a staging environment for your QA team, which includes a fresh
copy of the production database. To avoid the app to send or read emails, you put all
into a safe internal network:

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

Now, it turns out your QA detects font problems. Logic! `app` cannot contact
`fonts.google.com`. Yikes! What to do? 🤷

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

## Development

All the dependencies you need to develop this project (apart from Docker itself) are
managed with [poetry](https://python-poetry.org/).

To set up your development environment, run:

```bash
pip install pipx  # If you don't have pipx installed
pipx install poetry  # Install poetry itself
poetry install  # Install the python dependencies and setup the development environment
```

### Testing

To run the tests locally, add `--prebuild` to autobuild the image before testing:

```sh
poetry run pytest --prebuild
```

By default, the image that the tests use (and optionally prebuild) is named
`test:docker-whitelist`. If you prefer, you can build it separately before testing, and
remove the `--prebuild` flag, to run the tests with that image you built:

```sh
docker image build -t test:docker-whitelist .
poetry run pytest
```

If you want to use a different image, pass the `--image` command line argument with the
name you want:

```sh
# To build it automatically
poetry run pytest --prebuild --image my_custom_image

# To prebuild it separately
docker image build -t my_custom_image .
poetry run pytest --image my_custom_image
```
