
# saurus-fsspec

fsspec backend for streaming the SAURUS *Staphylococcus aureus* genomic
surveillance database into pandas.

Stream the SAURUS master table and individual typing modules directly
from [saurus-db.org](https://saurus-db.org/) without installing the
15 MB SAURUS-CLI data bundle. Uses the standard fsspec protocol
interface, so `saurus://` URLs work anywhere fsspec does: pandas,
dask, pyarrow, and any other consumer of the registry.

[![PyPI](https://img.shields.io/pypi/v/saurus-fsspec.svg)](https://pypi.org/project/saurus-fsspec/)
[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://pypi.org/project/saurus-fsspec/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## The SAURUS ecosystem

SAURUS has three entry points. Each covers a different usage pattern.

| Resource | What it is | When to use |
|---|---|---|
| [saurus-db.org](https://saurus-db.org/) | Interactive web resource with 15 query pages, statistics, trends, and side-by-side comparison | Exploring the data, verifying a lineage, exporting a one-off accession list |
| [saurus-cli](https://github.com/bbeckley-hub/saurus-cli) | Command-line interface with the full dataset bundled inside the wheel | Repeated queries in scripts and pipelines, offline work, version-pinned reproducibility |
| **saurus-fsspec** (this package) | fsspec protocol for the static files that saurus-db.org serves | One-off pandas analyses, CI jobs, notebook sessions where the full bundle is not worth installing |

The three share the same underlying data. A query run through any of
them returns the same accessions. Pick the one that matches how you
are working.

### Choosing between them

If you run one analysis today and may not touch the data again for
weeks, `saurus-fsspec` is the right pick. You `pip install` a small
package and read the table on demand. The 2 MB compressed transfer is
cheaper than a 15 MB wheel plus a 15 MB data bundle.

If you run the same query every week, or work on a pipeline that
should be reproducible in five years, `saurus-cli` is the right pick.
The data is bundled, the version is pinned, and nothing depends on
the site being up.

---

## Install

```bash
pip install saurus-fsspec
```

Dependencies: `fsspec`, `requests`, `pandas`. Nothing else.

---

## Usage

### With the helper (recommended)

```python
import saurus_fsspec

df = saurus_fsspec.read_table("master")
print(df.shape)              # (134273, 20)
print(df["mlst_cc"].value_counts().head())
```

The helper applies the TSV separator automatically, so you never
need to remember `sep="\t"`.

### With pandas directly

```python
import pandas as pd

df = pd.read_csv("saurus://master", sep="\t")
```

### With fsspec directly

```python
import fsspec

with fsspec.open("saurus://mlst", "rt") as f:
    for line in f:
        ...
```

### Available aliases

| Alias | File served | Content |
|---|---|---|
| `master` | `mrsa_all.tsv.gz` | Combined master table (134,273 rows x 20 columns) |
| `mlst` | `mlst_all.tsv.gz` | MLST sequence types |
| `spa` | `spa_all.tsv.gz` | spa types |
| `sccmec` or `sccmec/cge` | `sccmec_cge_all.tsv.gz` | SCCmec calls (CGE caller) |
| `sccmec/rpet` | `sccmec_rpet_all.tsv.gz` | SCCmec calls (RPet caller) |
| `capsule` | `capsule_all.tsv.gz` | Capsule serotypes |
| `agr` | `agr_all.tsv.gz` | agr types |
| `metadata` | `metadata.tsv.gz` | BioSample-derived metadata |
| `amr` | `amr_all.tsv.gz` | AMR gene content |
| `amr_freq` | `amr_gene_freq.tsv.gz` | AMR gene frequencies |
| `vfdb` | `vfdb_all.tsv.gz` | Virulence factor content |
| `vfdb_freq` | `vfdb_gene_freq.tsv.gz` | Virulence factor frequencies |
| `plasmid` | `plasmid_all.tsv.gz` | Plasmid replicon content |
| `plasmid_freq` | `plasmid_gene_freq.tsv.gz` | Plasmid replicon frequencies |
| `cc` | `cc.txt.gz` | ST to CC lookup table |

Any other filename can be passed as a path relative to the base URL.
For example, `saurus://custom_file.tsv.gz` fetches
`https://saurus-db.org/data/custom_file.tsv.gz`.

---

## Common workflows

### Count MRSA genomes by clonal complex

```python
import saurus_fsspec

df = saurus_fsspec.read_table("master", usecols=["mlst_cc", "mrsa_status"])
mrsa_by_cc = (
    df[df["mrsa_status"] == "MRSA"]
    .groupby("mlst_cc")
    .size()
    .sort_values(ascending=False)
    .head(10)
)
print(mrsa_by_cc)
```

### Filter by lineage and geography

```python
import saurus_fsspec

df = saurus_fsspec.read_table("master")
usa300_blood = df[
    (df["mlst_cc"] == "CC8") &
    (df["country"] == "United States") &
    (df["source"] == "blood")
]
print(f"USA300 blood-USA isolates: {len(usa300_blood):,}")
```

### Pull only the MLST table

```python
import saurus_fsspec

mlst = saurus_fsspec.read_table("mlst")
print(f"ST distribution: {mlst['ST'].value_counts().head(5).to_dict()}")
```

---

## How it works

The plugin is a minimal `fsspec.AbstractFileSystem` subclass that:

1. Maps `saurus://` paths to HTTPS URLs under the base URL
2. Downloads the file with `requests`
3. Decompresses on the fly if the file ends in `.gz`
4. Returns a `BytesIO` or `TextIOWrapper` that pandas and fsspec
   consumers can read normally

No server, no database, no authentication layer. The plugin reads the
same static files that saurus-db.org already serves. That design
mirrors the sustainability argument in the SAURUS paper: there is
nothing to maintain after the grant ends, because nothing in the
query path depends on live infrastructure.

### Why not a REST API

A REST API would provide server-side filtering and reduce bandwidth
for repeated queries. It would also reintroduce a server, a database,
an auth layer, and a maintenance budget. The static-site architecture
exists specifically so that nothing in the platform requires ongoing
operations. `saurus-fsspec` gives pandas users the same programmatic
ergonomics without the operational cost.

For workloads that need repeated queries with local filtering, use
[`saurus-cli`](https://github.com/bbeckley-hub/saurus-cli) instead.
The two tools are complementary, not redundant.

---

## Configuration

| Environment variable | Default | Purpose |
|---|---|---|
| `SAURUS_BASE_URL` | `https://saurus-db.org/data/` | Override the data source |
| `SAURUS_TIMEOUT` | `60` | Request timeout in seconds |

Or pass a custom filesystem:

```python
import fsspec
from saurus_fsspec import SaurusFileSystem

fs = SaurusFileSystem(base_url="https://mirror.example.org/saurus/")
with fs.open("master", "rt") as f:
    ...
```

---

## Requirements

- Python 3.9+
- `fsspec >= 2023.1.0`
- `requests >= 2.28.0`
- `pandas >= 1.5.0`

---

## Development

```bash
git clone https://github.com/bbeckley-hub/saurus-fsspec.git
cd saurus-fsspec
pip install -e ".[dev]"

# Offline tests (fast, no network)
pytest -m "not network"

# Network tests (requires internet)
pytest -m "not slow"

# Full suite (includes a 134,273-row read)
pytest
```

---

## Citation

If you use `saurus-fsspec` in your research, please cite the underlying
SAURUS resource:

> Beckley B, Olalekan A, Afeke I, Amarh V. SAURUS: an interactive web
> resource for typing-based genome retrieval in *Staphylococcus aureus*.
> *BMC Genomic Data* [under review]. 2026.

The companion command-line interface:

> Beckley B. SAURUS-CLI: a reproducible command-line interface for
> typing-based genome retrieval in *Staphylococcus aureus*. Zenodo.
> 2026. doi:10.5281/zenodo.24084554

---

## Credits

The fsspec backend was suggested by
[**bgruening**](https://github.com/bgruening) during review of the
SAURUS-CLI Bioconda recipe. His point was that a `saurus://`
filesystem plugin would let pandas users stream the master table
directly, without downloading the full 15 MB data bundle. That
suggestion is what this package implements.

Björn is a long-time maintainer of [Bioconda](https://bioconda.github.io/),
[Galaxy](https://galaxyproject.org/), and [conda-forge](https://conda-forge.org/),
and his feedback on the SAURUS-CLI packaging directly shaped the
current release.

Additional credits:
- [fsspec](https://filesystem-spec.readthedocs.io/) for the filesystem
  abstraction that makes the protocol possible
- [pandas](https://pandas.pydata.org/) for the DataFrame engine
- The [SAURUS web resource](https://saurus-db.org/) for serving the
  static data files this plugin consumes

---

## License

MIT. See [LICENSE](LICENSE).

---

## Links

- SAURUS web resource: <https://saurus-db.org/>
- SAURUS-CLI: <https://github.com/bbeckley-hub/saurus-cli>
- ARGUS initiative: <https://argus-db.org/>
- This package on PyPI: <https://pypi.org/project/saurus-fsspec/>
- This package on GitHub: <https://github.com/bbeckley-hub/saurus-fsspec>
- Issue tracker: <https://github.com/bbeckley-hub/saurus-fsspec/issues>
