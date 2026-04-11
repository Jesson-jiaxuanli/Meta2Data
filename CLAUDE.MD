# Meta2Data - Bioinformatics Pipeline

Bioinformatics tool for automated amplicon sequencing data processing from NCBI databases. Downloads, processes, and analyzes metagenomic data via CLI.

## ⚠️ IMPORTANT: Setup Environment First

**Run these commands immediately after reading this file:**

```bash
source ~/anaconda3/etc/profile.d/conda.sh
conda activate Meta2Data

```

This ensures you have the correct environment configured for all Meta2Data operations.

## Project Structure

```
bin/                    # CLI entry points (Meta2Data, MetaDL, MetaProcessingRun.sh)
scripts/               # Platform-specific pipelines (Amplicon_454/Illumina/Pacbio_*.sh)
test/                  # Test files and data
```

## Main Subcommands

- **MetaDL** - NCBI metadata search and download
- **AmpliconPIP** - Download and process amplicon sequencing (main pipeline)
- **Evaluate** - Summarize processing results
- **ShortreadsPIP** - (TBD)

## Quick Start

```bash
conda activate Meta2Data
./bin/Meta2Data AmpliconPIP -m metadata.csv -o output_dir -t 8
```

## AmpliconPIP Parameters

**Required:**
- `-m, --metadata` - Input CSV file

**Optional:**
- `-o, --output` - Output directory (default: metadata file directory)
- `-t, --threads` - CPU threads (default: 4)
- `--skip-download` - Skip SRA download step
- `--keep-tmp` - Keep temporary files
- `--col-*` - Custom CSV column names (e.g., `--col-bioproject`, `--col-platform`, `--col-sra`, `--col-biosample`, `--col-forward`, `--col-reverse`, `--col-region`)

**Example:**
```bash
Meta2Data AmpliconPIP -m data.csv -t 8 --col-bioproject "ProjectID" --col-platform "Platform"
```

## Processing Pipeline

Workflow: SRA download → Quality control → Platform-specific processing → Qiime2 import → Cleanup

**Platform-specific steps:**
- **454**: Chimera removal, cluster denovo, post-clustering low-freq OTU filter
- **Illumina**: Denoising with Deblur
- **PacBio**: Denoising with DADA2

## Environment Setup

**Platform:** Linux only (x86_64 or aarch64).

Meta2Data layers itself on top of a user-provided QIIME2 2024.10 amplicon
environment. It does NOT ship its own env.yml or manage the QIIME2 install.

**Three-step install:**

```bash
# 1. Install QIIME2 2024.10 amplicon following QIIME2's official instructions,
#    then activate it.
conda activate qiime2-amplicon-2024.10

# 2. Install Meta2Data (pulls in biopython via pip — safe on top of QIIME2).
pip install -e .

# 3. Download the two native binaries QIIME2 does not ship (vsearch, fastp).
bash scripts/install_binaries.sh
```

`install_binaries.sh` pulls prebuilt Linux static binaries from upstream
releases (no compilation, no conda), drops them into `<repo>/vendor/bin/`,
and is idempotent — re-run it anytime without side effects. The Meta2Data
entry scripts auto-prepend `<repo>/vendor/bin` to `PATH` at startup, so you
never have to touch your shell config. See `bash scripts/install_binaries.sh
--help` for `--prefix` and `--force` overrides.

**Software used at runtime:**
- QIIME2 2024.10 amplicon distribution (provides `qiime` plugins, pandas,
  numpy, requests, biom-format, cutadapt, and its own vsearch for plugin use)
- `vsearch` 2.30.0 — installed by `install_binaries.sh`; used directly by the
  DegradedQ pipeline (UNOISE3, uchime3, usearch_global)
- `fastp` 0.24.0 — installed by `install_binaries.sh`; adapter removal and
  quality filtering for all Illumina / 454 / Ion Torrent / PacBio inputs
- `biopython` — installed as a pip dependency of Meta2Data; used for NCBI
  Entrez queries
- `wget`, `unzip`, `tar`, `gzip`, `md5sum` — expected to be present on any
  standard Linux distribution



## Development

**Shell Script Standards:**
- Shebang: `#!/bin/bash`
- Error handling: `set -e`
- Parameter validation upfront
- Help messages use heredocs

**Common Patterns:**
- Argument parsing: while loops with case statements
- Directory resolution: `$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)`
- Script calls: Absolute paths via `${SCRIPTS}/script_name.sh`

**Add New Subcommand:**
1. Create `bin/Meta2Data-SubcommandName`
2. Add case entry in `bin/Meta2Data` dispatcher
3. Create processing script in `scripts/` if needed

**Key Files:**
- `bin/Meta2Data` - CLI dispatcher
- `bin/MetaDL` - Metadata download handler
- `bin/MetaProcessingRun.sh` - Processing orchestration
- `scripts/Function_Import.sh` - Shared functions

## Notes

- Preserve scientific accuracy in bioinformatics operations
- Maintain shell script best practices (quoting, error handling)
- Follow existing naming conventions
- Scripts are modular and pipeline-oriented
- Output directories created automatically
- **IMPORTANT**: Debug and test only in `Meta2Data` conda for consistency
