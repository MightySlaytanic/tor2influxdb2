# Changelog

* **1.3**: upgraded Python base image to 3.9.5-alpine
* **1.4**: upgraded Python base image to 3.10.0rc1-alpine
* **1.4.1**: upgraded Python base image to 3.10.0-alpine
* **1.4.2**: upgraded Python base image to 3.10.2-alpine3.15
* **1.4.3**: upgraded Python base image to 3.11.0a6-alpine3.15


# Sources

You can find Dockerfile and tor-to-influxdb2.py sources on GitHub:
https://github.com/MightySlaytanic/tor2influxdb2

# Docker Hub Image

https://hub.docker.com/repository/docker/giannicostanzi/tor2influxdb2

# Base Image

The base image is the official *python:3.9.4-alpine* (*python-3.9.4* for image 1.0) on top of which we install *influxdb_client* and *stem* (via *pip*).

# Environment Variables

| Variable | Values |Default|
|-------------|-----------|-----------|
| INFLUX_HOST|IP, DNS or Docker Container/Service name of InfluxDB2 Server |IP_OR_NAME *// must be changed //*|
| INFLUX_PORT|Port on which InfluxDB2 server is listening, usually 8086 |PORT *// must be changed //*|
| INFLUX_ORGANIZATION| Organization set in InfluxDB2 |ORGANIZATION *// must be changed //*|
| INFLUX_BUCKET | Bucket on InfluxDB2 server where measurements will be stored |BUCKET *// must be changed //*|
| INFLUX_TOKEN | InfluxDB2 access token to write data on *INFLUX_BUCKET* |TOKEN *// must be changed //*|
| INFLUX_SERVICE_TAG | Name assigned to the *service* tag assigned to every record sent to InfluxDB2 (leave it set to nothing to avoid sending a service tag along with the measurements| tor
| INFLUX_SEND_VERSION_TAG | Determines if a *version* tag is sent along with measurements (true or false)| true
| TOR_HOSTS | Comma separated list of Tor hosts definition, each of which is written in format *IP_OR_NAME:PORT:PASSWORD:HOST_TAG*"|ip1:port1:password1:name1,ip2:port2:password2:name2 *// must be changed //*|
| RUN_EVERY_SECONDS | Tor polling time | 10
| VERBOSE | Increase logging output (not so verbose BTW) |false

*TOR_HOSTS*: this variable can be set for example to *192.168.0.1:9051:rpi2,raspberry.home:9051:rpi3* which in turn configures the container to poll every *RUN_EVERY_SECONDS* the following Tor servers:
* 192.168.0.1 which listens with http GUI on Tor Control port 9051/TCP and using rpi2 as *host* tag attached to the data sent to InfluxDB2
* raspberry.home (DNS name) which listens on Tor Control Port 9051/TCP and using rpi3 as *host* tag

*WARNINGS*:
* In order to be able to talk with Tor on Control port (by default 9051/TCP) you have to make it listen on *0.0.0.0:9051* instead of the default *127.0.0.1:9051* within *torrc*: **it is not reccomended to make it listen to a non loopback address** so make it at your own risks and in a controlled environment (allow only the polling host to talk with that port via iptables or other firewalls).

```bash
#From /etc/tor/torrc

#The port on which Tor will listen for local connections from Tor
#controller applications, as documented in control-spec.txt.

ControlPort 0.0.0.0:9051
```

* You have to specify the Password to use to talk with Tor Control socket via Docker Environment Variable TOR_HOSTS, so remember that it will be known by anyone who has access to your Docker Environment and can do a *docker inspect* to see containers' environment variables

You can specify *-t* option which will be passed to **/tor-to-influxdb2.py** within the container to output all the values obtained from Tor servers to screen, without uploading nothing to the influxdb server. Remember to specify *-t* also as *docker run* option in order to see the output immediately (otherwise it will be printed on output buffer flush)

```bash
docker run -t --rm \
-e INFLUX_HOST="influxdb_server_ip" \
-e INFLUX_PORT="8086" \
-e INFLUX_ORGANIZATION="org-name" \
-e INFLUX_BUCKET="bucket-name" \
-e INFLUX_TOKEN="influx_token" \
-e INFLUX_SERVICE_TAG="tor" \
-e INFLUX_SEND_VERSION_TAG="true" \ 
-e VERBOSE="true" \
-e TOR_HOSTS="ip1:port1:password1:tag_name1,ip2:port2:password2:tag_name2" \
tor2influxdb2 -t
```

If you remove the *-t* option passed to the container, collected data will be uploaded to influxdb bucket in three measurements, *traffic*, *connections* and *handshakes*. The following is an example of a non-debug run:

```bash
docker run -d  --name="tor2influxdb2-stats" \
-e INFLUX_HOST="192.168.0.1" \
-e INFLUX_PORT="8086" \
-e INFLUX_ORGANIZATION="org-name" \
-e INFLUX_BUCKET="bucket-name" \
-e INFLUX_TOKEN="XXXXXXXXXX_INFLUX_TOKEN_XXXXXXXXXX" \
-e TOR_HOSTS="192.168.0.2:9051:mypassw0rd:rpi3,192.168.0.3:9051:Passw0rd:rpi4" \
-e RUN_EVERY_SECONDS="10" \
-e INFLUX_SEND_VERSION_TAG="true \ 
-e INFLUX_SERVICE_TAG="tor" \
tor2influxdb2
```

These are the *fields* uploaded for *traffic* measurement (I'll show the influxdb query used to view them all):

```flux
from(bucket: "tor-bucket")
|> range(start: v.timeRangeStart, stop: v.timeRangeStop)
|> filter(fn: (r) => r["_measurement"] == "traffic")
|> filter(fn: (r) => 
	r["_field"] == "read" 
	or r["_field"] == "written")
```

*Note*: read and written values are expressed in bytes

These are the *fields* uploaded for *connections* measurement:

```flux
from(bucket: "tor-bucket")
|> range(start: v.timeRangeStart, stop: v.timeRangeStop)
|> filter(fn: (r) => r["_measurement"] == "connections")
|> filter(fn: (r) => 
	r["_field"] == "circuits_active" 
	or r["_field"] == "streams_active")
```

These are the *fields* uploaded for *handshakes* measurement:

```flux
from(bucket: "tor-bucket")
|> range(start: v.timeRangeStart, stop: v.timeRangeStop)
|> filter(fn: (r) => r["_measurement"] == "handshakes")
|> filter(fn: (r) => 
	r["_field"] == "ntor_assigned" 
	or r["_field"] == "ntor_requested"  
	or r["_field"] == "tap_assigned" 
	or r["_field"] == "tap_requested")
```

Each record has also a tag named *host* that contains the names passed in *TOR_HOSTS* environment variable, a *service* tag named as the *INFLUX_SERVICE_TAG* environment variable (unless it is set to "", in which case the service tag is not appended to the records) and a *version* tag with the current Tor version running on the target system, but only if INFLUX_SEND_VERSION_TAG is set to *true*, unless that tag is not appended to the records. 

# Tor Control Requests

The following are the requests we send to the Tor Controller (it's a snippet of code from *tor-to-influxdb2.py* executed by the container):

```python
tor_version = str(controller.get_version())
active_circuits = int(len(controller.get_circuits()))
active_streams = int(len(controller.get_streams()))
read_bytes = int(controller.get_info("traffic/read"))
written_bytes = int(controller.get_info("traffic/written"))
ntor_req = int(controller.get_info("stats/ntor/requested"))
ntor_ass = int(controller.get_info("stats/ntor/assigned"))
tap_req = int(controller.get_info("stats/tap/requested"))
tap_ass = int(controller.get_info("stats/tap/assigned")
```

More info about these values on the Tor *control-spec.txt* document:
https://github.com/torproject/torspec/blob/master/control-spec.txt

# Healthchecks

I've implemented an healthcheck that sets the container to unhealthy as long as there is at least one Tor server that can't be queried or if there are problems uploading stats to influxdb2 server. The container becomes healthy in about 30 seconds if everything is fine and if there is a problem it produces an unhealthy status within 90 seconds.

If the container is unhealthy (you can see its status via docker ps command) you can check the logs with docker logs CONTAINER_ID

Note: if you have problems with the healthcheck not changing to unhealthy when it should (you see errors in the logs, for example) have a look at the health check reported by docker inspect CONTAINER_ID if matches the following one:

```yaml
"Healthcheck": {
  "Test": [
    "CMD-SHELL",
    "grep OK /healthcheck || exit 1"
  ],
  "Interval": 30000000000,
  "Timeout": 3000000000,
  "Retries": 3
}
```

I'm using Watchtower container to update my containers automatically and I've seen that even if the image is updated, the new container still uses the old HEALTHCHECK. If it happens, just stop and remove the container and re-create it.
