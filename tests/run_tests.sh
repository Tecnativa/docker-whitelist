#!/usr/bin/env bash
set -e
for arg in "$@" ; do
  echo arg $arg
  if [[ "$arg" == "DEBUG" ]] ; then
    DEBUG=1
  else
    TEST_FILTER="$arg"
  fi
done
DEBUG=${DEBUG:-0}
TEST_FILTER=${TEST_FILTER:-}

function cleanup() {
  if [[ $DEBUG == 1 ]]; then
    docker-compose -f tests/test.yaml ps
    docker-compose -f tests/test.yaml exec -T proxy_preresolve /usr/local/bin/healthcheck || true
    docker-compose -f tests/test.yaml exec -T proxy_without_preresolve /usr/local/bin/healthcheck || true
    docker-compose -f tests/test.yaml top
    docker-compose -f tests/test.yaml logs
  fi
  docker-compose -f tests/test.yaml down -v --remove-orphans
}
trap cleanup EXIT

function with_prefix() {
  local prefix
  prefix="$1"
  shift
  "$@" 2>&1 | while read -r line; do
    echo "$prefix" "$line"
  done
  return "${PIPESTATUS[0]}"
}

function run_tests() {
  for service in $(docker-compose -f tests/test.yaml config --services); do
    if [[ ( $service == test_* || ( $DEBUG = 1 && $service == debug_* ) ) && $service == *"$TEST_FILTER"* ]] ; then
      echo "running $service"
      with_prefix "$service:" docker-compose -f tests/test.yaml run --rm "$service"
    fi
  done
}

function change_target_ips() {
  for target in "target" "target_smtp"; do
    #spin up a second target and remove the first target container to give it a new ip (simulates a new deployment of an external cloud service)
    local target_container_id
    target_container_id=$(docker-compose -f tests/test.yaml ps -q "$target")
    if [[ "$target_container_id" != "" ]] ; then
      if [[ $DEBUG == 1 ]] ; then
        docker inspect "$target_container_id" | grep '"IPAddress": "[^"]\+'
      fi
      docker-compose -f tests/test.yaml up -d --scale "$target=2" "$target"
      docker stop "$target_container_id" | xargs echo "stopped ${target}_1"
      docker rm "$target_container_id" | xargs echo "removed ${target}_1"
      if [[ $DEBUG == 1 ]] ; then
        target_container_id=$(docker-compose -f tests/test.yaml ps -q "$target")
        docker inspect "$target_container_id" | grep '"IPAddress": "[^"]\+'
      fi
    fi
  done
  # give docker some time to restart unhealthy containers
  sleep 5
}

with_prefix "build:" docker-compose -f tests/test.yaml build

# make sure all tests pass when target is up
run_tests

# when target changes ip
with_prefix "changing target_ip:" change_target_ips

# all tests still should pass
run_tests
