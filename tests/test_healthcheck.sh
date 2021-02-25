#!/usr/bin/env bash
set -e

docker-compose -f tests/test.yaml build proxy_preresolve
docker-compose -f tests/test.yaml up -d proxy_preresolve
docker-compose -f tests/test.yaml exec proxy_preresolve /usr/local/bin/healthcheck
docker-compose -f tests/test.yaml stop target
# healthcheck should fail if target is stopped
! docker-compose -f tests/test.yaml exec proxy_preresolve /usr/local/bin/healthcheck
