#!/bin/bash
echo "=========================================================="
echo " Stopping StockBS Web App ONLY (backend & frontend)"
echo " DB, Collector, and Summarizer will remain running"
echo "=========================================================="
podman-compose -f podman-compose.yml down
