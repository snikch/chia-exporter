#!/usr/bin/python3
"""
Chia Exporter for Prometheus
"""

from time import sleep
import logging
import subprocess
import argparse
import re

from prometheus_client import start_http_server
from prometheus_client.core import GaugeMetricFamily, REGISTRY


class ChiaCollector(object):
    def __init__(self, args):
        self.args = args

    def collect(self):
        if self.args.collectNode:
            netspace = subprocess.run(["chia", "netspace"], stdout=subprocess.PIPE, text=True)
            if "Connection Failure" in netspace.stdout:
                # Connection Failure: "Connection error. Check if full node is running at None"
                logging.info("Failed to get netspace: %s", netspace.stdout)
                return
            matches = re.findall(r'\d+\.\d+TiB', netspace.stdout)
            if len(matches) < 1:
                logging.info("Failed to get netspace match: %s", netspace.stdout)
                return
            tib = float(matches[0].strip('TiB'))
            gib = tib * 1024
            mib = gib * 1024
            kib = mib * 1024
            b = kib * 1024
            logging.debug("Received: %dTiB %dB", tib, b)

            yield GaugeMetricFamily(
                'chia_node_netspace_bytes',
                'The Chia Netspace in Bytes',
                value=int(b))

def main(args):
    logging.getLogger().setLevel(20)
    logging.info("prometheus-chia-exporter started on port %d", args.port)
    start_http_server(args.port)
    REGISTRY.register(ChiaCollector(args))
    while True:
        sleep(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--collector.node", dest='collectNode', type=bool, default=True)
    parser.add_argument("--collector.farmer", dest='collectFarmer', type=bool, default=False)
    parser.add_argument("--collector.harvester", dest='collectHarvester', type=bool, default=False)
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    try:
        main(args)
    except KeyboardInterrupt:
        print("\n")
        logging.info("Shutting down")
