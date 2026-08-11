#!/bin/bash
echo "=========================================================="
echo " Starting StockBS Web App ONLY (backend & frontend)"
echo " DB, Collector, and Summarizer will NOT be stopped/restarted"
echo "=========================================================="
podman-compose -f podman-compose.yml up -d --build
