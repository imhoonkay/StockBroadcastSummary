#!/bin/bash
echo "=========================================================="
echo " Starting ALL StockBS Services with Podman"
echo "=========================================================="

# Export .env environment variables
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

podman-compose -f podman-compose-all.yml up -d --build

