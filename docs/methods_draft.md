## System, Methods, and Usage

Meta2Data is an automated command-line pipeline for large-scale retrieval, processing, and cross-study integration of public 16S rRNA amplicon sequencing data, implemented in Python 3 and Bash as three sequential modules—MetaDL, AmpliconPIP, and ggCOMBO—that require no manual intervention between stages. The modules chain seamlessly from keyword or BioProject accession queries against NCBI SRA, ENA, DDBJ, and CNCB/GSA to a phylogeny-integrated, taxonomy-annotated feature table ready for downstream diversity analysis. AmpliconPIP and ggCOMBO require QIIME2 amplicon distribution 2024.10; MetaDL operates on any Python 3 interpreter, with required Python packages and native binaries (vsearch 2.30.0, fastp 0.24.0) installed automatically on first invocation.

*Table 1. Processes of Meta2Data in operation order.*

| Process (in operation order) | Module | Tool(s) |
|---|---|---|
| Keyword / BioProject ID search | MetaDL | NCBI Entrez, CNCB API |
| Metadata download and standardization | MetaDL | Biopython, requests |
| Sequencing platform detection | AmpliconPIP | NCBI Entrez, CNCB API |
| Raw data download | AmpliconPIP | Aspera / SRA FTP / CNCB |
| Adapter removal | AmpliconPIP | fastp 0.24.0 |
| Primer detection and trimming | AmpliconPIP | entropy_primer_detect.py |
| Illumina / Ion Torrent denoising | AmpliconPIP | DADA2 (QIIME2) |
| Roche 454 OTU clustering | AmpliconPIP | vsearch 2.30.0 (QIIME2) |
| PacBio SMRT CCS denoising | AmpliconPIP | DADA2 denoise-ccs (QIIME2) |
| Feature table and sequence merging | ggCOMBO | QIIME2 feature-table |
| Sequence orientation | ggCOMBO | RESCRIPt (QIIME2) |
| Taxonomy assignment | ggCOMBO | Naïve Bayes classifier (QIIME2) |
| Phylogenetic tree construction | ggCOMBO | SEPP fragment insertion (QIIME2) |
| Tree-based feature filtering | ggCOMBO | QIIME2 fragment-insertion |

**MetaDL.** MetaDL accepts a directory of BioProject ID files (PRJNA, PRJEB, PRJDB, and PRJCA prefixes) or a structured keyword query and retrieves run-level metadata via parallel requests to NCBI Entrez—covering NCBI SRA, ENA, and DDBJ—and the CNCB/GSA API simultaneously, enabling retrieval from four international repositories in a single run. Per-project SRA RunInfo and BioSample attribute tables are merged, column names are normalized to CamelCase via a configurable rename dictionary, and all records are concatenated into a single all_metadata_merged.csv; a JSON checkpoint (download_state.json) records completion status per project, enabling resumption of interrupted runs without redundant re-downloads. Worker parallelism scales from three (no API key) to eight (with NCBI API key).

**AmpliconPIP.** AmpliconPIP processes each BioProject dataset through download, adapter removal, primer trimming, and platform-specific denoising, first resolving the sequencing platform of all pending datasets from NCBI Entrez or CNCB metadata in a single pre-processing batch query to prevent API rate-limit exhaustion. Raw reads are downloaded via Aspera, SRA FTP, or the CNCB portal, and adapter sequences are subsequently removed with fastp 0.24.0 (quality and length filtering disabled, so only technical adapter contamination is eliminated before primer detection). Four sequencing platforms are supported—Illumina, Ion Torrent, Roche 454, and PacBio SMRT—with Oxford Nanopore data explicitly excluded.

**Primer detection and trimming.** Primer sequences are detected and removed by entropy_primer_detect.py, which implements a three-state CDV (Conserved / Degenerate / Variable) position-classification algorithm analogous to per-base sequence content analysis: a 60 × 4 position-wise base frequency matrix is constructed from the first sample; each position is labeled C (dominant-base frequency ≥ 0.80), D (two dominant bases with combined frequency ≥ 0.80 and second-base frequency ≥ 0.10), or V (variable); the longest contiguous [CD]\* prefix from position 0 (10–30 bp, with noise tolerance for up to two consecutive V positions flanked by ≥ 3 non-V positions) defines the candidate boundary, refined by sliding-window IUPAC-compatible identity matching (≥ 85% identity) against a reference set of 9 forward and 13 reverse consensus sequences spanning all V1–V9 hypervariable regions. Mixed-orientation paired-end libraries—identified from bimodal base distributions across the primer region—are corrected per read pair via a single-character base comparison at the optimal split position before trimming.

**Denoising.** Denoising is platform-specific: Illumina datasets use DADA2 (denoise-paired, with automatic fallback to denoise-single if read-pair retention falls below 50%); Ion Torrent datasets use DADA2 denoise-pyro with a 10-bp 5′ trim to account for signal instability at the start of homopolymer cycles; PacBio SMRT CCS datasets (defined as having > 50% of reads exceeding 1400 bp) use DADA2 denoise-ccs with 27F/1492R primers; and Roche 454 datasets follow a vsearch-based pipeline comprising adaptive tail trimming, 97% de novo OTU clustering, and chimera removal. Each successfully processed dataset produces a per-project \*-final-table.qza and \*-final-rep-seqs.qza.

**ggCOMBO.** ggCOMBO merges per-dataset QIIME2 feature tables and representative sequences produced by AmpliconPIP, orients all sequences against the selected taxonomy reference using qiime rescript orient-seqs, and assigns taxonomy via a pre-trained Naïve Bayes classifier (qiime feature-classifier classify-sklearn; default confidence threshold 0.7), followed by phylogenetic tree construction through SEPP fragment insertion into the GreenGenes2 reference phylogeny regardless of the taxonomy database selected. Three taxonomy databases are supported and selectable at runtime via --db-type: GreenGenes2 2024.09 (default), SILVA 138.99, and GSR-DB (a gut-specific reference); all required database files are downloaded automatically with --dl. The final outputs—features successfully placed in the phylogenetic tree retained in merged-table-tree.qza, with classifications stored in merged-taxonomy.qza—are directly compatible with QIIME2 phylogenetic and compositional diversity analyses across merged cross-study datasets.
