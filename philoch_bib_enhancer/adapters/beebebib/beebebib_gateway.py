"""
BeebebibGateway - Gateway for extracting bibliographic data from Nelson Beebe's BibTeX collections.

Nelson H. F. Beebe maintains extensive BibTeX bibliographies at:
https://ftp.math.utah.edu/pub/tex/bib/

This gateway follows the functional core / imperative shell pattern:
- Configuration is passed as a NamedTuple
- Gateway functions accept config as first parameter
- configure() binds all gateway functions to a config using partial application

Available bibliographies include (partial list):
- dialectica.bib - Dialectica journal
- synthese.bib - Synthese journal
- philsci.bib - Philosophy of Science
- philstud.bib - Philosophical Studies
- mindphil.bib - Mind & Philosophy journals
- And many more...

See full list at: https://ftp.math.utah.edu/pub/tex/bib/
"""

from functools import partial
import inspect
import sys
import urllib.request
import urllib.error
from pathlib import Path
from types import SimpleNamespace
from typing import NamedTuple, Generator

from aletk.utils import get_logger

from philoch_bib_enhancer.adapters.raw_text.raw_text_converter import convert_raw_text_to_bibitem
from philoch_bib_enhancer.adapters.raw_text.extractors.extract_bibtex import parse_bib_file
from philoch_bib_enhancer.domain.parsing_result import ParsedResult
from philoch_bib_sdk.logic.models import BibItem


lgr = get_logger(__name__)

# Default BeebeBib FTP base URL
BEEBEBIB_BASE_URL = "https://ftp.math.utah.edu/pub/tex/bib"


class BeebebibGatewayConfig(NamedTuple):
    """
    Configuration for the BeebeBib Gateway.

    Attributes:
        base_url: Base URL for BeebeBib FTP (default: https://ftp.math.utah.edu/pub/tex/bib)
        cache_dir: Local directory to cache downloaded .bib files (default: None = no caching)
        timeout: HTTP request timeout in seconds (default: 60)
    """

    base_url: str = BEEBEBIB_BASE_URL
    cache_dir: Path | None = None
    timeout: int = 60


class BeebebibError(Exception):
    """Exception raised for BeebeBib gateway errors."""


# --- Gateway functions ---


def download_bib_file(
    config: BeebebibGatewayConfig,
    bib_name: str,
    output_path: Path | None = None,
) -> Path:
    """
    Download a .bib file from BeebeBib FTP.

    Args:
        config: Gateway configuration
        bib_name: Name of the bibliography (e.g., "dialectica" or "dialectica.bib")
        output_path: Where to save the file. If None, uses cache_dir or temp location.

    Returns:
        Path to the downloaded file

    Raises:
        BeebebibError: If download fails
    """
    # Normalize bib_name
    if not bib_name.endswith(".bib"):
        bib_name = f"{bib_name}.bib"

    url = f"{config.base_url}/{bib_name}"

    # Determine output path
    if output_path is None:
        if config.cache_dir:
            config.cache_dir.mkdir(parents=True, exist_ok=True)
            output_path = config.cache_dir / bib_name
        else:
            # Use current directory
            output_path = Path(bib_name)

    lgr.info(f"Downloading {url} to {output_path}")

    try:
        urllib.request.urlretrieve(url, output_path)
        lgr.info(f"Downloaded {bib_name} ({output_path.stat().st_size:,} bytes)")
        return output_path
    except urllib.error.URLError as e:
        raise BeebebibError(f"Failed to download {url}: {e}") from e
    except Exception as e:
        raise BeebebibError(f"Unexpected error downloading {url}: {e}") from e


def get_bibitems_from_local_bib(
    config: BeebebibGatewayConfig,
    bib_path: Path,
) -> Generator[ParsedResult[BibItem], None, None]:
    """
    Parse a local .bib file and yield BibItems.

    Args:
        config: Gateway configuration (used for consistency, not currently needed)
        bib_path: Path to the local .bib file

    Yields:
        ParsedResult[BibItem] for each entry (either success or error)
    """
    lgr.info(f"Parsing local BibTeX file: {bib_path}")

    try:
        raw_bibitems = parse_bib_file(str(bib_path))
        lgr.info(f"Found {len(raw_bibitems)} entries in {bib_path.name}")
    except Exception as e:
        yield {
            "parsing_status": "error",
            "message": f"Failed to parse BibTeX file: {e}",
            "context": str(bib_path),
        }
        return

    for raw_bibitem in raw_bibitems:
        yield convert_raw_text_to_bibitem(raw_bibitem)


def get_bibitems_from_bib_url(
    config: BeebebibGatewayConfig,
    url: str,
    cache_as: str | None = None,
) -> Generator[ParsedResult[BibItem], None, None]:
    """
    Download a .bib file from any URL and yield BibItems.

    Args:
        config: Gateway configuration
        url: Full URL to the .bib file
        cache_as: Optional name to cache the file as (e.g., "dialectica.bib")

    Yields:
        ParsedResult[BibItem] for each entry (either success or error)
    """
    # Determine cache path
    if cache_as and config.cache_dir:
        output_path = config.cache_dir / cache_as
    else:
        # Extract filename from URL
        filename = url.split("/")[-1]
        if config.cache_dir:
            output_path = config.cache_dir / filename
        else:
            output_path = Path(filename)

    lgr.info(f"Downloading {url}")

    try:
        urllib.request.urlretrieve(url, output_path)
        lgr.info(f"Downloaded to {output_path} ({output_path.stat().st_size:,} bytes)")
    except urllib.error.URLError as e:
        yield {
            "parsing_status": "error",
            "message": f"Failed to download {url}: {e}",
            "context": url,
        }
        return
    except Exception as e:
        yield {
            "parsing_status": "error",
            "message": f"Unexpected error downloading {url}: {e}",
            "context": url,
        }
        return

    # Parse the downloaded file
    yield from get_bibitems_from_local_bib(config, output_path)


def get_bibitems_from_bib_name(
    config: BeebebibGatewayConfig,
    bib_name: str,
) -> Generator[ParsedResult[BibItem], None, None]:
    """
    Download a .bib file from BeebeBib by name and yield BibItems.

    This is the main entry point for processing BeebeBib bibliographies.

    Args:
        config: Gateway configuration with base_url
        bib_name: Name of the bibliography (e.g., "dialectica" or "dialectica.bib")

    Yields:
        ParsedResult[BibItem] for each entry (either success or error)

    Example:
        >>> config = BeebebibGatewayConfig(cache_dir=Path("./cache"))
        >>> gateway = configure(config)
        >>> for result in gateway.get_bibitems_from_bib_name("dialectica"):
        ...     if result["parsing_status"] == "success":
        ...         print(result["out"].title)
    """
    # Normalize bib_name
    if not bib_name.endswith(".bib"):
        bib_name = f"{bib_name}.bib"

    url = f"{config.base_url}/{bib_name}"

    yield from get_bibitems_from_bib_url(config, url, cache_as=bib_name)


# --- Auto-configure ---


def configure(config: BeebebibGatewayConfig) -> SimpleNamespace:
    """
    Return a namespace with all gateway functions bound to `config`.

    This uses functools.partial to bind the config parameter to all gateway functions,
    following the same pattern as other gateways in the codebase.

    Example:
        >>> config = BeebebibGatewayConfig(cache_dir=Path("./data/beebebib"))
        >>> gateway = configure(config)
        >>> results = list(gateway.get_bibitems_from_bib_name("dialectica"))
        >>> print(f"Got {len(results)} entries")
    """
    current_module = sys.modules[__name__]
    bound_funcs = {}

    for name, obj in inspect.getmembers(current_module, inspect.isfunction):
        if name == "configure":
            continue

        sig = inspect.signature(obj)
        params = list(sig.parameters.values())
        if not params or params[0].name != "config":
            continue  # only wrap funcs with config as first param

        bound_funcs[name] = partial(obj, config)

    return SimpleNamespace(**bound_funcs)
