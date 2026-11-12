# Changelog

All notable changes to saurus-fsspec are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.0] — 2026-11-12

### Added
- `saurus://` fsspec protocol for the SAURUS web resource
- `read_table()` helper for pandas with correct TSV defaults
- Alias table: `master`, `mlst`, `spa`, `sccmec/cge`, `sccmec/rpet`,
  `capsule`, `agr`, `metadata`, `amr`, `vfdb`, `plasmid`, `cc`
- Transparent gzip decompression
- `SAURUS_BASE_URL` and `SAURUS_TIMEOUT` environment variables
- 23 tests covering protocol registration, alias resolution, network
  round-trips, and the `mlst_cc` regression
