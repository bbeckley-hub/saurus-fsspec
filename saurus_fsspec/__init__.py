"""
saurus_fsspec — fsspec protocol for the SAURUS genomic surveillance database.
"""

import fsspec

from .fs import SaurusFileSystem, ALIASES, DEFAULT_BASE_URL

__version__ = "0.1.0"

__all__ = [
    "SaurusFileSystem",
    "ALIASES",
    "DEFAULT_BASE_URL",
    "read_table",
    "__version__",
]

# Register the implementation.
fsspec.register_implementation(
    "saurus",
    SaurusFileSystem,
    clobber=True,
)


def read_table(name, **kwargs):
    """Read a SAURUS table into a pandas DataFrame with the correct defaults.

    Parameters
    ----------
    name : str
        Alias (``"master"``, ``"mlst"``, ``"metadata"``, ...) or a filename
        relative to the data base URL.
    **kwargs
        Forwarded to ``pandas.read_csv``. ``sep`` defaults to ``"\\t"``.

    Example
    -------
    >>> import saurus_fsspec
    >>> df = saurus_fsspec.read_table("master")
    >>> df.shape
    (134273, 20)
    """
    import pandas as pd
    kwargs.setdefault("sep", "\t")
    kwargs.setdefault("low_memory", False)
    return pd.read_csv(f"saurus://{name}", **kwargs)