#!/usr/bin/python3
"""
Chia Exporter for Prometheus
"""

from time import sleep
import logging
import subprocess
import configargparse
import re

from prometheus_client import start_http_server
from prometheus_client.core import GaugeMetricFamily, REGISTRY


class ChiaCollector(object):
    def collect(self):
        # Connection Failure: "Connection error. Check if full node is running at None"
        netspace = subprocess.run(["chia", "netspace"], stdout=subprocess.PIPE, text=True)
        if "Connection Failure" in netspace.stdout:
            return
        matches = re.findall(r'\d+\.\d+TB', netspace.stdout)
        if len(matches) < 1:
            return
        yield GaugeMetricFamily(
            'chia_node_netspace_terabytes',
            value=matches[0].strip('TB'))

def main():
    logging.getLogger().setLevel(20)
    logging.info("prometheus-chia-exporter started on port %d", args.port)
    start_http_server(args.port)
    REGISTRY.register(ChiaCollector())
    while True:
        sleep(1)


if __name__ == '__main__':
    global args
    parser = configargparse.ArgumentParser()
    parser.add_argument("--collector.node", type=bool, default=True)
    parser.add_argument("--collector.farmer", type=bool, default=False)
    parser.add_argument("--collector.harvester", type=bool, default=False)
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    try:
        main()
    except KeyboardInterrupt:
        print("\n") # Most terminals print a Ctrl+C message as well. Looks ugly with our log.
        logging.info("Ctrl+C, bye!")
