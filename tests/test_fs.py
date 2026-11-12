"""
tests/test_fs.py — pytest suite for saurus-fsspec.

Offline tests run without network access. Network tests require a live
connection to saurus-db.org and are marked with @pytest.mark.network.

    pytest -m "not network"     # offline only
    pytest -m "not slow"        # default, skips full-table reads
    pytest                      # everything
"""

import pytest


# ---------------------------------------------------------------------------
# Offline tests
# ---------------------------------------------------------------------------

def test_import():
    """Public API is importable and exposes the expected names."""
    from saurus_fsspec import SaurusFileSystem, ALIASES, __version__, read_table
    assert __version__
    assert "master" in ALIASES
    assert "mlst" in ALIASES
    assert "metadata" in ALIASES
    assert callable(read_table)


def test_protocol_registered():
    """saurus:// resolves to a SaurusFileSystem instance."""
    import fsspec
    from saurus_fsspec import SaurusFileSystem
    fs = fsspec.filesystem("saurus")
    assert isinstance(fs, SaurusFileSystem)


def test_strip_protocol():
    """_strip_protocol removes the saurus:// prefix from any input form."""
    from saurus_fsspec import SaurusFileSystem
    assert SaurusFileSystem._strip_protocol("saurus://master") == "master"
    assert SaurusFileSystem._strip_protocol("saurus://metadata.tsv.gz") == "metadata.tsv.gz"
    assert SaurusFileSystem._strip_protocol("master") == "master"
    assert SaurusFileSystem._strip_protocol("saurus://sccmec/cge") == "sccmec/cge"


def test_alias_resolution():
    """Aliases and relative paths resolve to full HTTPS URLs."""
    from saurus_fsspec import SaurusFileSystem
    fs = SaurusFileSystem(base_url="https://example.org/data/")
    assert fs._resolve("master") == "https://example.org/data/mrsa_all.tsv.gz"
    assert fs._resolve("mlst") == "https://example.org/data/mlst_all.tsv.gz"
    assert fs._resolve("sccmec/rpet") == "https://example.org/data/sccmec_rpet_all.tsv.gz"
    assert fs._resolve("custom.tsv") == "https://example.org/data/custom.tsv"


def test_base_url_trailing_slash_added():
    """A base_url without a trailing slash is normalised on construction."""
    from saurus_fsspec import SaurusFileSystem
    fs = SaurusFileSystem(base_url="https://example.org/data")
    assert fs.base_url == "https://example.org/data/"


def test_custom_base_url_env(monkeypatch):
    """SAURUS_BASE_URL overrides the default base URL."""
    from saurus_fsspec import SaurusFileSystem
    SaurusFileSystem.clear_instance_cache()
    monkeypatch.setenv("SAURUS_BASE_URL", "https://mirror.example.org/")
    fs = SaurusFileSystem()
    assert fs.base_url == "https://mirror.example.org/"


def test_custom_timeout_env(monkeypatch):
    """SAURUS_TIMEOUT overrides the default request timeout."""
    from saurus_fsspec import SaurusFileSystem
    SaurusFileSystem.clear_instance_cache()
    monkeypatch.setenv("SAURUS_TIMEOUT", "15")
    fs = SaurusFileSystem()
    assert fs.timeout == 15.0


def test_read_only():
    """Write modes raise NotImplementedError."""
    import fsspec
    fs = fsspec.filesystem("saurus")
    with pytest.raises(NotImplementedError):
        fs._open("mlst", "wb")


def test_ls_lists_aliases():
    """ls() returns the known alias names."""
    import fsspec
    fs = fsspec.filesystem("saurus")
    names = fs.ls(detail=False)
    assert "master" in names
    assert "mlst" in names
    assert "metadata" in names


# ---------------------------------------------------------------------------
# Network tests
# ---------------------------------------------------------------------------

@pytest.mark.network
def test_open_mlst_text():
    """Text-mode reading via fsspec.open returns tab-separated rows."""
    import fsspec
    with fsspec.open("saurus://mlst", "rt") as f:
        header = f.readline().strip()
    assert header
    assert "accession" in header.lower()
    assert "\t" in header


@pytest.mark.network
def test_open_metadata_text():
    """Text-mode reading of the metadata file returns a valid header."""
    import fsspec
    with fsspec.open("saurus://metadata", "rt") as f:
        header = f.readline().strip()
    assert "accession" in header.lower()


@pytest.mark.network
def test_info_mlst():
    """info() returns a file record with a size and HTTPS URL."""
    import fsspec
    fs = fsspec.filesystem("saurus")
    info = fs.info("mlst")
    assert info["type"] == "file"
    assert info["size"] > 0
    assert info["url"].startswith("https://")


@pytest.mark.network
def test_exists():
    """exists() distinguishes real aliases from missing paths."""
    import fsspec
    fs = fsspec.filesystem("saurus")
    assert fs.exists("mlst")
    assert fs.exists("master")
    assert not fs.exists("this_does_not_exist_xyz")


@pytest.mark.network
def test_file_not_found():
    """A missing path raises FileNotFoundError."""
    import fsspec
    fs = fsspec.filesystem("saurus")
    with pytest.raises(FileNotFoundError):
        fs.open("this_does_not_exist_xyz", "rb")


@pytest.mark.network
def test_read_table_mlst():
    """read_table('mlst') returns a DataFrame with MLST columns."""
    import saurus_fsspec
    df = saurus_fsspec.read_table("mlst", nrows=5)
    assert len(df) == 5
    assert "accession" in df.columns
    assert "ST" in df.columns


@pytest.mark.network
def test_read_table_spa():
    """read_table('spa') returns a DataFrame with spa_Type."""
    import saurus_fsspec
    df = saurus_fsspec.read_table("spa", nrows=5)
    assert len(df) == 5
    assert "spa_Type" in df.columns


@pytest.mark.network
def test_read_table_metadata():
    """read_table('metadata') returns a DataFrame with country."""
    import saurus_fsspec
    df = saurus_fsspec.read_table("metadata", nrows=5)
    assert len(df) == 5
    assert "country" in df.columns


@pytest.mark.network
def test_read_table_agr():
    """read_table('agr') returns a DataFrame with agr_Type (capital T)."""
    import saurus_fsspec
    df = saurus_fsspec.read_table("agr", nrows=5)
    assert len(df) == 5
    assert "agr_Type" in df.columns


@pytest.mark.network
def test_read_table_master_shape():
    """The master table has 20 columns including all key modules."""
    import saurus_fsspec
    df = saurus_fsspec.read_table("master", nrows=5)
    assert df.shape == (5, 20)
    expected = {
        "accession", "mlst_st", "mlst_cc", "spa_type",
        "sccmec_cge", "sccmec_rpet", "agr_type", "capsule_type",
        "country", "source", "host", "year", "mrsa_status",
    }
    assert expected.issubset(df.columns)


@pytest.mark.network
def test_master_cc_populated():
    """The master table carries the full ST to CC assignment.

    Guards against the earlier bug where mrsa_all.tsv.gz shipped with an
    empty mlst_cc column. If this fails, rerun the ST to CC fill on
    mrsa_all.tsv and redeploy to docs/data/.
    """
    import saurus_fsspec
    df = saurus_fsspec.read_table("master")

    assert len(df) == 134_273
    assert int(df["mlst_cc"].notna().sum()) == 115_133
    assert int((df["mlst_cc"] == "CC5").sum()) == 25_991
    assert int((df["mlst_cc"] == "CC8").sum()) == 29_135


@pytest.mark.network
def test_master_matches_cli():
    """The CLI and the fsspec plugin report identical CC counts."""
    import subprocess
    import saurus_fsspec

    df = saurus_fsspec.read_table("master")
    fs_cc5 = int((df["mlst_cc"] == "CC5").sum())
    fs_cc8 = int((df["mlst_cc"] == "CC8").sum())

    try:
        cli_cc5 = int(
            subprocess.check_output(["saurus", "--cc", "5", "--count", "-q"])
            .decode().strip().replace(",", "")
        )
        cli_cc8 = int(
            subprocess.check_output(["saurus", "--cc", "8", "--count", "-q"])
            .decode().strip().replace(",", "")
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        pytest.skip("saurus CLI not installed")

    assert cli_cc5 == fs_cc5
    assert cli_cc8 == fs_cc8


@pytest.mark.network
def test_pandas_read_master_direct():
    """Raw pandas access with sep='\\t' works without the helper."""
    import pandas as pd
    df = pd.read_csv("saurus://master", sep="\t", nrows=3)
    assert df.shape == (3, 20)
    assert "accession" in df.columns


# ---------------------------------------------------------------------------
# Slow tests
# ---------------------------------------------------------------------------

@pytest.mark.network
@pytest.mark.slow
def test_master_full_read():
    """Read the full master table (134,273 rows, ~5 s)."""
    import saurus_fsspec
    df = saurus_fsspec.read_table("master")
    assert len(df) == 134_273
    assert df.shape[1] == 20