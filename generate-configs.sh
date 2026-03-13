#!/bin/bash

# Wrapper script to generate local config files from templates
# API keys are read from .env and injected into the generated configs

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Load .env if it exists
if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a
    source "$SCRIPT_DIR/.env"
    set +a
fi

# Run the Python script
python3 "$SCRIPT_DIR/scripts/generate_configs.py" "$@"
