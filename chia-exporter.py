#!/usr/bin/python3
"""
Chia Exporter for Prometheus
"""

from time import sleep
import asyncio
import logging
import subprocess
import argparse
import re

from prometheus_client import start_http_server
from prometheus_client.core import GaugeMetricFamily, REGISTRY

import sys
# Ensure we have the chia src loaded
sys.path.append('/opt/chia-blockchain')

from src.util.config import load_config
from src.util.default_root import DEFAULT_ROOT_PATH
from src.rpc.harvester_rpc_client import HarvesterRpcClient


class ChiaCollector(object):
    def __init__(self, args):
        self.args = args

    def collect(self):
        if self.args.collect_node:
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
        if self.args.collect_harvester:
            plots = asyncio.run(self.get_plots())
            gauges = {
                'bytes': GaugeMetricFamily(
                    'chia_harvester_plot_bytes',
                    'Plots being harvested',
                    labels=['filename', 'plot_seed', 'plot_pk', 'pool_pk', 'farmer_pk', 'local_sk', 'size'])
            }
            for plot in plots['plots']:
                gauges['bytes'].add_metric(
                    [plot['filename'], plot['plot-seed'], plot['plot_public_key'], plot['pool_public_key'], plot['farmer_public_key'], plot['local_sk'], str(plot['size'])],
                    plot['file_size'])
            logging.debug("Got plots %s", plots)
            yield gauges['bytes']

    async def get_plots(self):
        config = load_config(DEFAULT_ROOT_PATH, "config.yaml")
        self_hostname = config["self_hostname"]
        rpc_port = config["harvester"]["rpc_port"]
        harvester_client = await HarvesterRpcClient.create(self_hostname, rpc_port)
        plots = await harvester_client.get_plots()
        return plots

def main(args):
    logging.getLogger().setLevel(20)
    logging.info("prometheus-chia-exporter started on port %d", args.port)
    start_http_server(args.port)
    REGISTRY.register(ChiaCollector(args))
    while True:
        sleep(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--collector.node", dest='collect_node', type=bool, default=True)
    parser.add_argument("--collector.farmer", dest='collect_farmer', type=bool, default=False)
    parser.add_argument("--collector.harvester", dest='collect_harvester', type=bool, default=False)
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    try:
        main(args)
    except KeyboardInterrupt:
        print("\n")
        logging.info("Shutting down")
