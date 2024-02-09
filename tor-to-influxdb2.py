#!/usr/bin/python3
import sys
import json
import argparse
from datetime import datetime
from time import sleep
from os import getenv
from os.path import realpath, dirname
from signal import signal, SIGTERM

import stem
import stem.connection
from stem.control import Controller

from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client.client.exceptions import InfluxDBError

PROGRAM_DIR = dirname(realpath(__file__))
HEALTHCHECK_FILE = f"{PROGRAM_DIR}/healthcheck"
HEALTHCHECK_FAILED = "FAILED"
HEALTHCHECK_OK = "OK"

INFLUX_HOST = getenv("INFLUX_HOST")
INFLUX_PORT = getenv("INFLUX_PORT")
INFLUX_ORGANIZATION = getenv("INFLUX_ORGANIZATION")
INFLUX_BUCKET = getenv("INFLUX_BUCKET")
INFLUX_TOKEN = getenv("INFLUX_TOKEN")
INFLUX_SERVICE_TAG = getenv("INFLUX_SERVICE_TAG")
INFLUX_SEND_VERSION_TAG = getenv("INFLUX_SEND_VERSION_TAG")
TOR_HOSTS = getenv("TOR_HOSTS")
RUN_EVERY_SECONDS = int(getenv("RUN_EVERY_SECONDS"))
VERBOSE = getenv("VERBOSE")

DEBUG = 0
SEND_VERSION_TAG = False


def sigterm_handler(signum, frame):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] SIGTERM received, shutting down..", file=sys.stderr)
    sys.exit(0)


def set_failed_flag():
    with open(HEALTHCHECK_FILE, "w") as healthcheck_file:
        healthcheck_file.write(HEALTHCHECK_FAILED)


def set_ok_flag():
    with open(HEALTHCHECK_FILE, "w") as healthcheck_file:
        healthcheck_file.write(HEALTHCHECK_OK)


if __name__ == '__main__':
    signal(SIGTERM, sigterm_handler)

    if VERBOSE.lower() == "true":
        DEBUG = 1

    if INFLUX_SEND_VERSION_TAG.lower() == "true":
        SEND_VERSION_TAG = True
    
    TOR_HOSTS_DICT = {}

    for index, entry in enumerate(TOR_HOSTS.split(",")):
        try:
            host, port, password, name = entry.split(":")
        except ValueError as e:
            print(e, file=sys.stderr)
            print(f"Wrong TOR_HOSTS entry <{entry}>!", file=sys.stderr)
            sys.exit(1)

        TOR_HOSTS_DICT.update({ index : { "host": host, "name": name, "password": password, "port": port } })

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting...")
    print("\nTOR_HOSTS definition:\n")
    print(json.dumps(TOR_HOSTS_DICT, indent=4))

    if DEBUG:        
        print(f"\nHealthcheck file => {HEALTHCHECK_FILE}")

    parser = argparse.ArgumentParser(usage="Tor Stats to influxdb2 uploader")

    parser.add_argument(
        "-t",
        "--test",
        help="Just print the results without uploading to influxdb2",
        action="store_true"
    )

    args = parser.parse_args()

    last_healthcheck_failed = False
    set_ok_flag()

    while True:
        start_time = datetime.now()
        failure = False

        for index in TOR_HOSTS_DICT.keys():
            host = TOR_HOSTS_DICT[index]["host"]
            host_name = TOR_HOSTS_DICT[index]["name"]
            host_password = TOR_HOSTS_DICT[index]["password"]
            try:
                host_port = int(TOR_HOSTS_DICT[index]["port"])
            except ValueError as e:
                failure = True
                print(e, file=sys.stderr)
                print(f"Wrong port <{TOR_HOSTS_DICT[index]['port']}> specified for host {host}!", file=sys.stderr)
                continue

            if DEBUG:
                print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Collecting data for host {host}:{host_port}({host_name})...")

            try:
                controller = Controller.from_port(address=host, port=host_port)
            except stem.SocketError as e:
                failure = True
                print(e, file=sys.stderr)
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] SocketError: Could not connect to {host}:{host_port}({host_name})",file=sys.stderr)
                continue
            except Exception as e:
                failure = True
                print(e, file=sys.stderr)
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Connection Error: Could not connect to {host}:{host_port}({host_name})",file=sys.stderr)
                continue

            try:
                controller.authenticate(password=host_password)
            except stem.connection.AuthenticationFailure as e:
                failure = True
                controller.close()
                print(e, file=sys.stderr)
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] AuthenticationFailure: Could not connect to {host}:{host_port}({host_name})",file=sys.stderr)
                continue
            except Exception as e:
                failure = True
                controller.close()
                print(e, file=sys.stderr)
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Authentication Error: Could not connect to {host}:{host_port}({host_name})",file=sys.stderr)
                continue

            try:
                tor_version = str(controller.get_version())
                active_circuits = int(len(controller.get_circuits()))
                active_streams = int(len(controller.get_streams()))
                read_bytes = int(controller.get_info("traffic/read"))
                written_bytes = int(controller.get_info("traffic/written"))
                ntor_req = int(controller.get_info("stats/ntor/requested"))
                ntor_ass = int(controller.get_info("stats/ntor/assigned"))
                tap_req = int(controller.get_info("stats/tap/requested"))
                tap_ass = int(controller.get_info("stats/tap/assigned"))
            except ValueError as e:
                failure = True
                print(e, file=sys.stderr)
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error parsing data for {host}:{host_port}({host_name})",file=sys.stderr)
                continue
            finally:
                controller.close()
            
                #TimeStarted="1970-01-01 00:00:00" CountrySummary=us=216,de=144,in=96,id=56,ru=40,fr=32,nl=32,ca=24,gb=24,it=24,pk=24,ua=24,fi=16,jp=16,sg=16,vn=16,??=8,ao=8,at=8,au=8,bd=8,bg=8,bi=8,bo=8,br=8,bw=8,ch=8,ci=8,co=8,cu=8,cz=8,dk=8,ec=8,ee=8,eg=8,es=8,et=8,gh=8,gr=8,gy=8,hu=8,ie=8,il=8,ir=8,jo=8,ke=8,kr=8,kw=8,kz=8,li=8,lk=8,lt=8,lu=8,lv=8,ma=8,md=8,mm=8,mx=8,my=8,ng=8,no=8,np=8,nz=8,pe=8,ph=8,pl=8,ps=8,ro=8,rs=8,sc=8,sd=8,se=8,sn=8,th=8,tn=8,tr=8,ve=8,za=8,zw=8 IPVersions=v4=904,v6=0
                #clients_seen = controller.get_info('status/clients-seen')

            tags_dict = { "host": host_name }
            if SEND_VERSION_TAG:
                tags_dict.update({ "version": tor_version })
            if INFLUX_SERVICE_TAG:
                tags_dict.update({ "service": INFLUX_SERVICE_TAG})

            traffic_fields = {
                        "read": read_bytes, 
                        "written": written_bytes
            }

            connections_fields = {
                        "circuits_active": active_circuits, 
                        "streams_active": active_streams
            }

            handshakes_fields = {
                        "ntor_requested": ntor_req, 
                        "ntor_assigned": ntor_ass,
                        "tap_requested": tap_req, 
                        "tap_assigned": tap_ass
            }

            if args.test:
                print(f"\nStats for host {host}:{host_port}({host_name}): ")
                print("\nTags:")
                print(json.dumps(tags_dict, indent=4))
                print("\nTraffic measurement:")
                print(json.dumps(traffic_fields, indent=4))
                print("\nConnections measurement:")
                print(json.dumps(connections_fields, indent=4))
                print("\nHandshakes measurement:")
                print(json.dumps(handshakes_fields, indent=4))

            else:
                try:
                    if DEBUG:
                        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Uploading data for host {host}({host_name})...")
                    client = InfluxDBClient(url=f"{INFLUX_HOST}:{INFLUX_PORT}", token=INFLUX_TOKEN, org=INFLUX_ORGANIZATION)
                    write_api = client.write_api(write_options=SYNCHRONOUS)

                    write_api.write(
                        INFLUX_BUCKET, 
                        INFLUX_ORGANIZATION, 
                        [
                            {
                                "measurement": "traffic", 
                                "tags": tags_dict, 
                                "fields": traffic_fields
                            },
                            {
                                "measurement": "connections", 
                                "tags": tags_dict, 
                                "fields": connections_fields
                            },
                            {
                                "measurement": "handshakes", 
                                "tags": tags_dict, 
                                "fields": handshakes_fields
                            }
                        ]
                    )
                except TimeoutError as e:
                    failure = True
                    print(e,file=sys.stderr)
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] TimeoutError: Could not upload data to {INFLUX_HOST}:{INFLUX_PORT} for {host}:{host_port}({host_name})",file=sys.stderr)
                    continue
                except InfluxDBError as e:
                    failure = True
                    print(e,file=sys.stderr)
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] InfluxDBError: Could not upload data to {INFLUX_HOST}:{INFLUX_PORT} for {host}:{host_port}({host_name})",file=sys.stderr)
                    continue
                except Exception as e:
                    failure = True
                    print(e, file=sys.stderr)
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Connection Error: Could not upload data to {INFLUX_HOST}:{INFLUX_PORT} for {host}:{host_port}({host_name})",file=sys.stderr)
                    continue
                finally:
                    client.close()
        
        # Health check management
        if failure:
            if not last_healthcheck_failed:
                # previous cycle was successfull, so we must set the failed flag
                set_failed_flag()
                last_healthcheck_failed = True
        else:
            if last_healthcheck_failed:
                # Everything ok, clear the flag
                set_ok_flag()
                last_healthcheck_failed = False

        # Sleep for the amount of time specified by RUN_EVERY_SECONDS minus the time elapsed for the above computations
        stop_time = datetime.now()
        delta_seconds = int((stop_time - start_time).total_seconds())
        
        if delta_seconds < RUN_EVERY_SECONDS:
            sleep(RUN_EVERY_SECONDS - delta_seconds)

