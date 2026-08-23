#!/bin/bash
# purge.sh - Purge cache entries for a specific path

if [ -z "$1" ]; then
    echo "Usage: $0 /path/to/asset"
    exit 1
fi

PATH_TO_PURGE="$1"
echo "Purging asset: $PATH_TO_PURGE"

curl -i -X POST http://localhost:7000/api/v1/purge \
     -H "Content-Type: application/json" \
     -d "{\"urls\": [\"$PATH_TO_PURGE\"]}"
echo ""
