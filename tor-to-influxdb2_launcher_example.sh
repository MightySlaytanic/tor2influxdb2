#!/bin/bash

export INFLUX_HOST="INFLUX_IP"
export INFLUX_PORT=8086
export INFLUX_ORGANIZATION="influx_org"
export INFLUX_BUCKET="influx_bucket"
export INFLUX_SERVICE_TAG="influx_service_tag"
export INFLUX_SEND_VERSION_TAG="True"
export INFLUX_TOKEN="influx_token"
export TOR_HOSTS="ip1:port1:password1:tag1,ip2:port2:password2:tag2"
export RUN_EVERY_SECONDS=10
export VERBOSE="True"

python3 ./tor-to-influxdb2.py $*
