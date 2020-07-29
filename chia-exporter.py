#!/usr/bin/python3
"""
Chia Exporter for Prometheus
"""

import datetime
import time
import asyncio
import logging
import argparse
from time import sleep, struct_time, localtime

from prometheus_client import start_http_server
from prometheus_client.core import GaugeMetricFamily, REGISTRY

import sys
# Ensure we have the chia src loaded
sys.path.append('/opt/chia-blockchain')

from src.util.config import load_config
from src.util.default_root import DEFAULT_ROOT_PATH
from src.rpc.full_node_rpc_client import FullNodeRpcClient
from src.rpc.harvester_rpc_client import HarvesterRpcClient

def human_local_time(timestamp):
    time_local = struct_time(localtime(timestamp))
    return time.strftime("%a %b %d %Y %T %Z", time_local)

class ChiaCollector(object):
    def __init__(self, args):
        self.args = args
        self.config = load_config(DEFAULT_ROOT_PATH, "config.yaml")

    def collect(self):
        if self.args.collect_node:
            netspace = asyncio.run(self.get_network_space())
            logging.debug("Received: %dB", netspace)

            yield GaugeMetricFamily(
                'chia_node_netspace_bytes',
                'The Chia Netspace in Bytes',
                value=netspace)

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
                    [plot['filename'], str(plot['plot-seed']), str(plot['plot_public_key']), str(plot['pool_public_key']), str(plot['farmer_public_key']), str(plot['local_sk']), str(plot['size'])],
                    plot['file_size'])
            logging.debug("Got plots %s", plots)
            yield gauges['bytes']

    async def get_plots(self):
        self_hostname = self.config["self_hostname"]
        rpc_port = self.config["harvester"]["rpc_port"]
        harvester_client = await HarvesterRpcClient.create(self_hostname, rpc_port)
        plots = await harvester_client.get_plots()
        harvester_client.close()
        return plots

    # Stolen from src/cmds/netspace.py
    async def get_network_space(self):
        self_hostname = self.config["self_hostname"]
        rpc_port = self.config["full_node"]["rpc_port"]
        client = await FullNodeRpcClient.create(self_hostname, rpc_port)
        blockchain_state = await client.get_blockchain_state()
        newer_block_height = blockchain_state["lca"].data.height
        newer_block_header = await client.get_header_by_height(newer_block_height)
        older_block_height = newer_block_height - 24
        older_block_header = await client.get_header_by_height(older_block_height)
        newer_block_header_hash = str(newer_block_header.get_hash())
        older_block_header_hash = str(older_block_header.get_hash())
        elapsed_time = (
            newer_block_header.data.timestamp - older_block_header.data.timestamp
        )
        newer_block_time_string = human_local_time(
            newer_block_header.data.timestamp
        )
        older_block_time_string = human_local_time(
            older_block_header.data.timestamp
        )
        time_delta = datetime.timedelta(seconds=elapsed_time)
        network_space_bytes = await client.get_network_space(
            newer_block_header_hash, older_block_header_hash
        )
        client.close()
        return network_space_bytes

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
