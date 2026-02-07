"""Configuration module for Gobble.

Loads application configuration from a local JSON file. The configuration
includes API keys, feature flags, and other runtime settings.

Attributes:
    CONFIG: Dictionary containing all configuration values loaded from
        config/local.json.
"""

import json

with open("config/local.json") as file:
    CONFIG = json.load(file)
