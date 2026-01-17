"""
BeebeBib Gateway - Gateway for extracting bibliographic data from Nelson Beebe's BibTeX collections.

Nelson H. F. Beebe maintains extensive BibTeX bibliographies at:
https://ftp.math.utah.edu/pub/tex/bib/

This gateway downloads and parses these .bib files into BibItem objects.
"""

from philoch_bib_enhancer.adapters.beebebib.beebebib_gateway import (
    BeebebibGatewayConfig,
    configure,
    get_bibitems_from_bib_name,
    get_bibitems_from_bib_url,
    get_bibitems_from_local_bib,
    download_bib_file,
)

__all__ = [
    "BeebebibGatewayConfig",
    "configure",
    "get_bibitems_from_bib_name",
    "get_bibitems_from_bib_url",
    "get_bibitems_from_local_bib",
    "download_bib_file",
]
