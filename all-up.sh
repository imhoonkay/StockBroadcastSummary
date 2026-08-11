#!/bin/bash
echo "=========================================================="
echo " Starting ALL StockBS Services (DB, Collector, Summarizer, Backend, Frontend)"
echo "=========================================================="
podman-compose -f podman-compose-all.yml up -d --build
