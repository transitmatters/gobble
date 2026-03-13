#!/bin/bash
set -e

# Docker entrypoint script for Gobble
# This script handles any pre-startup configuration

# Default config path (can be overridden via environment variable)
CONFIG_PATH="${GOBBLE_CONFIG_PATH:-config/local.json}"

# Verify config file exists
if [ ! -f "$CONFIG_PATH" ]; then
    echo "ERROR: Config file not found at $CONFIG_PATH"
    echo "Please mount your config file or set GOBBLE_CONFIG_PATH environment variable"
    exit 1
fi

echo "Starting Gobble with config: $CONFIG_PATH"
echo "Service: ${DD_SERVICE:-gobble}"
echo "Environment: ${DD_ENV:-dev}"

# Ensure data directory exists with proper permissions
mkdir -p /app/data/trip_states

# Pass control to Python application via uv (uses the virtual environment)
exec uv run python -u src/gobble.py
