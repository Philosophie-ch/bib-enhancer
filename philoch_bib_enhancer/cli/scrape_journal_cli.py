"""
Unified CLI entry point for journal scraping.

This CLI dispatches to different adapter implementations based on the
--gateway parameter (or SCRAPE_JOURNAL_DEFAULT_GATEWAY environment variable).
"""

import os
import sys
import argparse
from dotenv import load_dotenv

from aletk.utils import get_logger

# Load .env file at module import
load_dotenv()

lgr = get_logger(__file__)


# ============================================================================
# Gateway Registry
# ============================================================================

AVAILABLE_GATEWAYS = {
    "crossref": "philoch_bib_enhancer.cli.crossref_journal_scraping_cli",
}


def get_default_gateway() -> str:
    """Get default gateway from environment variable."""
    return os.getenv("SCRAPE_JOURNAL_DEFAULT_GATEWAY", "crossref")


def get_gateway_module(gateway_name: str) -> str:
    """
    Get the module path for a gateway.

    :param gateway_name: Name of the gateway (e.g., 'crossref')
    :return: Module path
    :raises ValueError: If gateway is not found
    """
    if gateway_name not in AVAILABLE_GATEWAYS:
        available = ", ".join(AVAILABLE_GATEWAYS.keys())
        raise ValueError(f"Unknown gateway '{gateway_name}'. " f"Available gateways: {available}")

    return AVAILABLE_GATEWAYS[gateway_name]


def dispatch_to_gateway(gateway_name: str, args: list[str]) -> None:
    """
    Dynamically import and call the appropriate gateway CLI.

    :param gateway_name: Name of the gateway to use
    :param args: Command line arguments to pass to the gateway
    """
    module_path = get_gateway_module(gateway_name)

    lgr.info(f"Dispatching to gateway: {gateway_name} ({module_path})")

    # Dynamically import the gateway module
    import importlib

    module = importlib.import_module(module_path)

    # Call the cli() function from the gateway module
    if not hasattr(module, "cli"):
        raise AttributeError(f"Gateway module '{module_path}' does not have a 'cli()' function")

    # Temporarily replace sys.argv so the gateway CLI can parse args
    original_argv = sys.argv
    try:
        # Gateway CLI will parse these args
        sys.argv = ["scrape-journal"] + args
        module.cli()
    finally:
        sys.argv = original_argv


# ============================================================================
# Main CLI Entry Point
# ============================================================================


def cli() -> None:
    """
    Main unified CLI entry point.

    Parses the --gateway argument and dispatches to the appropriate
    adapter-specific CLI implementation.
    """
    # Use parse_known_args to allow gateway-specific arguments to pass through
    parser = argparse.ArgumentParser(
        description="Scrape journal articles using various data source adapters.",
        add_help=False,  # Disable default help to pass through to gateway
    )

    default_gateway = get_default_gateway()
    available_gateways = ", ".join(AVAILABLE_GATEWAYS.keys())

    parser.add_argument(
        "--gateway",
        "-g",
        type=str,
        default=default_gateway,
        help=f"Data source gateway to use. Available: {available_gateways}. "
        f"Default: {default_gateway} (from SCRAPE_JOURNAL_DEFAULT_GATEWAY env var)",
    )

    # Parse only the gateway argument, leave the rest for the gateway CLI
    args, remaining_args = parser.parse_known_args()

    # Special case: if --help is in remaining_args, show help for selected gateway
    if "--help" in remaining_args or "-h" in remaining_args:
        lgr.info(f"Showing help for gateway: {args.gateway}")
        print(f"\n=== Journal Scraping CLI (using '{args.gateway}' gateway) ===\n")

    # Dispatch to the appropriate gateway
    try:
        dispatch_to_gateway(args.gateway, remaining_args)
    except ValueError as e:
        lgr.error(str(e))
        sys.exit(1)
    except Exception as e:
        lgr.error(f"Error running gateway '{args.gateway}': {e}")
        raise


if __name__ == "__main__":
    cli()
