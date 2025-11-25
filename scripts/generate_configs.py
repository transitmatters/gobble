#!/usr/bin/env python3
"""
Generate local config files from templates, injecting API keys from environment variables.

This script reads template JSON files from config/template/ and generates
local versions in config/ with API keys populated from .env variables.

Agencies with api_key_method="none" are not modified (api_key remains null).

Usage:
    python3 scripts/generate_configs.py
    python3 scripts/generate_configs.py --template template_marta_bus.json
    python3 scripts/generate_configs.py --output-dir ./local_configs
"""

import json
import os
import sys
import argparse
from pathlib import Path
from typing import Dict, Any, Optional
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def load_env_file(env_file: str = ".env") -> Dict[str, str]:
    """Load environment variables from .env file."""
    env_vars = {}
    if not os.path.exists(env_file):
        logger.warning(f"No {env_file} file found, will use environment variables only")
        return env_vars

    with open(env_file, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                env_vars[key.strip()] = value.strip()

    return env_vars


def get_agency_name_from_template(template_path: Path) -> Optional[str]:
    """Extract agency name from template JSON file."""
    try:
        with open(template_path, "r") as f:
            data = json.load(f)
            return data.get("agency")
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Failed to extract agency from {template_path}: {e}")
        return None


def get_api_key_var_name(agency: str) -> str:
    """Convert agency name to API key environment variable name."""
    return f"{agency.upper()}_API_KEY"


def inject_api_key(
    config: Dict[str, Any], env_vars: Dict[str, str], agency: str
) -> None:
    """
    Inject API key into config if the agency requires one.

    Only injects if api_key_method is not "none".
    """
    gtfs_rt = config.get("gtfs_rt", {})

    # Skip if api_key_method is "none" (no API key required)
    if gtfs_rt.get("api_key_method") == "none":
        logger.debug(f"Skipping API key injection for {agency} (api_key_method=none)")
        return

    # Get the API key from environment
    api_key_var = get_api_key_var_name(agency)
    api_key = env_vars.get(api_key_var) or os.getenv(api_key_var)

    if api_key:
        config["gtfs_rt"]["api_key"] = api_key
        logger.info(f"Injected API key for {agency}")
    else:
        logger.warning(
            f"No API key found for {agency} (expected env var: {api_key_var})"
        )


def generate_config(
    template_path: Path, output_path: Path, env_vars: Dict[str, str]
) -> bool:
    """
    Generate a config file from a template with API keys injected.

    Returns True if successful, False otherwise.
    """
    try:
        # Load template
        with open(template_path, "r") as f:
            config = json.load(f)

        # Extract agency name
        agency = config.get("agency")
        if not agency:
            logger.error(f"Template {template_path.name} has no 'agency' field")
            return False

        # Inject API key if needed
        inject_api_key(config, env_vars, agency)

        # Write output file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(config, f, indent=2)

        logger.info(f"Generated {output_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to generate config from {template_path}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Generate local config files from templates with API keys injected"
    )
    parser.add_argument(
        "--template",
        help="Specific template file to process (e.g., template_marta_bus.json)",
    )
    parser.add_argument(
        "--output-dir",
        default="config/local",
        help="Output directory for generated configs (default: config/local)",
    )
    parser.add_argument(
        "--env-file", default=".env", help="Path to .env file (default: .env)"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Load environment variables
    env_vars = load_env_file(args.env_file)
    # Also merge in actual environment variables
    env_vars.update(os.environ)

    # Find template directory
    template_dir = Path("config/template")
    if not template_dir.exists():
        logger.error(f"Template directory not found: {template_dir}")
        return 1

    output_dir = Path(args.output_dir)

    # Process templates
    if args.template:
        # Process specific template
        template_path = template_dir / args.template
        if not template_path.exists():
            logger.error(f"Template not found: {template_path}")
            return 1

        output_path = output_dir / args.template.replace("template_", "").replace(
            ".json", ".json"
        )
        success = generate_config(template_path, output_path, env_vars)
        return 0 if success else 1
    else:
        # Process all templates
        templates = sorted(template_dir.glob("template_*.json"))
        if not templates:
            logger.error(f"No templates found in {template_dir}")
            return 1

        logger.info(f"Found {len(templates)} templates")

        success_count = 0
        for template_path in templates:
            # Output filename: remove 'template_' prefix, keep .json extension
            output_filename = template_path.name.replace("template_", "")
            output_path = output_dir / output_filename

            if generate_config(template_path, output_path, env_vars):
                success_count += 1

        logger.info(f"Successfully generated {success_count}/{len(templates)} configs")
        return 0 if success_count == len(templates) else 1


if __name__ == "__main__":
    sys.exit(main())
