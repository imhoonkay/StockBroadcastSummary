#!/bin/bash
echo "=========================================================="
echo " Stopping ALL StockBS Services (DB, Collector, Summarizer, Backend, Frontend)"
echo "=========================================================="
podman-compose -f podman-compose-all.yml down
