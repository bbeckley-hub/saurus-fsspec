"""
saurus_fsspec.fs — fsspec backend for the SAURUS web resource.

Streams the SAURUS typing tables directly from
https://saurus-db.org/data/ into pandas or any fsspec consumer.

Usage:
    import pandas as pd
    df = pd.read_csv("saurus://mlst")

    import fsspec
    with fsspec.open("saurus://metadata", "rt") as f:
        for line in f:
            ...
"""

from __future__ import annotations

import gzip
import io
import os
from typing import Optional

import fsspec
import requests

__all__ = ["SaurusFileSystem"]

# The data files are served from the /data/ path on the site.
DEFAULT_BASE_URL = "https://saurus-db.org/data/"

# Environment variable overrides for mirrors or testing.
ENV_BASE_URL = "SAURUS_BASE_URL"
ENV_TIMEOUT = "SAURUS_TIMEOUT"
DEFAULT_TIMEOUT = 60

# Friendly aliases that map to the filenames served at the base URL.
# All of these files are confirmed to exist in docs/data/.
ALIASES = {
    # Individual typing modules (available now)
    "mlst":         "mlst_all.tsv.gz",
    "spa":          "spa_all.tsv.gz",
    "sccmec":       "sccmec_cge_all.tsv.gz",
    "sccmec/cge":   "sccmec_cge_all.tsv.gz",
    "sccmec/rpet":  "sccmec_rpet_all.tsv.gz",
    "capsule":      "capsule_all.tsv.gz",
    "agr":          "agr_all.tsv.gz",
    "metadata":     "metadata.tsv.gz",
    "amr":          "amr_all.tsv.gz",
    "amr_freq":     "amr_gene_freq.tsv.gz",
    "vfdb":         "vfdb_all.tsv.gz",
    "vfdb_freq":    "vfdb_gene_freq.tsv.gz",
    "plasmid":      "plasmid_all.tsv.gz",
    "plasmid_freq": "plasmid_gene_freq.tsv.gz",
    "cc":           "cc.txt.gz",
    "master":       "mrsa_all.tsv.gz",
}


class SaurusFileSystem(fsspec.AbstractFileSystem):
    """Read-only fsspec backend for the SAURUS genomic surveillance database.

    Paths are resolved relative to ``base_url`` (default:
    ``https://saurus-db.org/data/``). The alias table maps friendly
    names such as ``mlst`` and ``metadata`` to the flat filenames
    served by the site.
    """

    protocol = "saurus"
    root_marker = ""

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
        session: Optional[requests.Session] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        base = base_url or os.environ.get(ENV_BASE_URL) or DEFAULT_BASE_URL
        if not base.endswith("/"):
            base += "/"
        self.base_url = base
        self.timeout = float(
            timeout or os.environ.get(ENV_TIMEOUT) or DEFAULT_TIMEOUT
        )
        self.session = session or requests.Session()

    # ------------------------------------------------------------------
    # Core read path
    # ------------------------------------------------------------------

    def _open(self, path, mode="rb", **kwargs):
        if mode not in ("rb", "rt", "r"):
            raise NotImplementedError(
                f"SaurusFileSystem is read-only; got mode={mode!r}"
            )

        url = self._resolve(path)

        try:
            resp = self.session.get(url, timeout=self.timeout)
            resp.raise_for_status()
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                raise FileNotFoundError(
                    f"sarus://{path} not found at {url}. "
                    f"Available aliases: {', '.join(sorted(ALIASES))}"
                ) from None
            raise ConnectionError(f"Failed to fetch {url}: {exc}") from exc
        except requests.RequestException as exc:
            raise ConnectionError(f"Failed to fetch {url}: {exc}") from exc

        content = resp.content

        # The site serves gzipped files. Decompress transparently so that
        # pandas and other consumers see plain text regardless of the URL
        # extension.
        if path.endswith(".gz") or url.endswith(".gz"):
            content = gzip.decompress(content)

        buffer = io.BytesIO(content)

        if "t" in mode:
            return io.TextIOWrapper(buffer, encoding="utf-8", errors="replace")
        return buffer

    def cat_file(self, path, start=None, end=None, **kwargs):
        with self._open(path, "rb") as f:
            data = f.read()
        if start is not None or end is not None:
            data = data[start:end]
        return data

    def info(self, path, **kwargs):
        url = self._resolve(path)
        try:
            head = self.session.head(url, timeout=self.timeout, allow_redirects=True)
            head.raise_for_status()
        except requests.RequestException as exc:
            raise FileNotFoundError(
                f"sarus://{path} not found at {url}: {exc}"
            ) from exc
        size = int(head.headers.get("Content-Length", 0) or 0)
        return {
            "name": path,
            "size": size,
            "type": "file",
            "url": url,
        }

    def exists(self, path, **kwargs):
        try:
            self.info(path)
            return True
        except FileNotFoundError:
            return False

    def ls(self, path="", detail=True, **kwargs):
        """List the known alias table."""
        names = sorted(name for name in ALIASES if "/" not in name)
        if detail:
            return [{"name": name, "type": "file", "size": 0} for name in names]
        return names

    # ------------------------------------------------------------------
    # Protocol handling
    # ------------------------------------------------------------------

    @classmethod
    def _strip_protocol(cls, path):
        if path.startswith("saurus://"):
            return path[len("saurus://"):].lstrip("/")
        return path

    def _resolve(self, path):
        path = self._strip_protocol(str(path)).lstrip("/")
        if path in ALIASES:
            path = ALIASES[path]
        return self.base_url + path
