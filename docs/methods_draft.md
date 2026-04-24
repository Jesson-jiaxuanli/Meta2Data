## 2 System, Methods, and Usage

Meta2Data is an end-to-end command-line pipeline for the automated retrieval, processing, and cross-study integration of 16S rRNA amplicon sequencing data from public repositories, implemented in Python 3 and Bash and organized as three sequential modules—MetaDL, AmpliconPIP, and ggCOMBO. The pipeline can be deployed on any Linux system with full HPC and server support; AmpliconPIP and ggCOMBO require the QIIME2 amplicon distribution 2024.10 conda environment, while MetaDL operates on any available Python 3 interpreter without additional environment prerequisites. Required native binaries (vsearch 2.30.0 and fastp 0.24.0) and Python dependencies are detected and installed automatically on the first AmpliconPIP or ggCOMBO invocation, requiring no manual package management. The source code is freely available at https://github.com/LinyangSun/Meta2Data.

The pipeline chains three sequential modules to automate a workflow that would otherwise require manual coordination across multiple public-database APIs, platform-specific processing tools, and taxonomy reference databases. Processing steps span metadata retrieval and standardization, sequencing platform detection, raw data download, multi-platform amplicon quality control and denoising, cross-study dataset merging, taxonomy classification, and phylogenetic tree construction, culminating in QIIME2-compatible feature tables and taxonomy files ready for downstream diversity analysis.

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

### 2.1 MetaDL

MetaDL accepts either a directory of plain-text BioProject ID files—supporting PRJNA, PRJEB, PRJDB, and PRJCA prefixes covering NCBI, ENA, DDBJ, and CNCB, respectively—or a structured keyword query combining field, organism, and optional terms, and issues parallel requests to NCBI Entrez and the CNCB/GSA API simultaneously, enabling metadata retrieval from four international repositories within a single run. For each project, SRA RunInfo and BioSample attribute tables are downloaded via Entrez efetch or the CNCB GSA portal, merged on shared BioSample identifiers, and column names are normalized to CamelCase via a configurable rename dictionary loaded from a bundled annotation file (docs/NCBI_Biosample.json); all per-project records are subsequently concatenated into a single all_metadata_merged.csv. This standardized output serves as the direct input for AmpliconPIP, requiring no manual reformatting between pipeline stages.

To support large-scale multi-project runs without data loss upon interruption, MetaDL implements a JSON checkpoint system (checkpoints/download_state.json) that records per-project completion status and enables automatic resumption of failed or interrupted runs. Default worker parallelism scales from three concurrent threads (without an NCBI API key) to eight (with key supplied via -k), and a timestamped execution log is written to logs/metadl_v2_*.log for each run.

### 2.2 AmpliconPIP

AmpliconPIP processes each BioProject dataset listed in the standardized metadata through raw data download, adapter removal, entropy-based primer trimming, and platform-specific denoising, dispatching each dataset to one of four sub-pipelines after resolving the sequencing platform of all pending datasets from NCBI Entrez or CNCB metadata in a single pre-processing batch query—preventing API rate-limit exhaustion during parallel execution. Raw reads are downloaded via Aspera, SRA FTP, or the CNCB portal; adapter sequences are subsequently removed with fastp 0.24.0 with quality and length filtering disabled, so that only technical adapter contamination is eliminated before primer detection. Four sequencing platforms are fully supported—Illumina, Ion Torrent, Roche 454, and PacBio SMRT—with Oxford Nanopore data explicitly excluded.

Primer detection and trimming are performed by entropy_primer_detect.py using a custom three-state CDV (Conserved / Degenerate / Variable) algorithm: a 60 × 4 position-wise base frequency matrix is built from the first sample; positions are labeled C (f₁ ≥ 0.80), D (f₁+f₂ ≥ 0.80, f₂ ≥ 0.10), or V; the longest [CD]\* prefix (10–30 bp) is refined by IUPAC-compatible sliding-window identity matching against 9 forward and 13 reverse consensus sequences spanning V1–V9, with mixed-orientation PE libraries automatically detected and corrected per read pair before trimming.

Denoising is platform-specific: Illumina data use DADA2 (denoise-paired, with automatic PE-to-SE fallback if read-pair retention falls below 50%); Ion Torrent data use DADA2 denoise-pyro with a 10-bp 5′ trim; PacBio SMRT CCS data use DADA2 denoise-ccs with 27F/1492R primers; Roche 454 data use a vsearch-based pipeline of adaptive tail trimming, 97% de novo OTU clustering, and chimera removal. Each completed dataset yields \*-final-table.qza and \*-final-rep-seqs.qza.

### 2.3 ggCOMBO

ggCOMBO merges per-dataset QIIME2 feature tables and representative sequences produced by AmpliconPIP, orients all representative sequences against the selected taxonomy reference with qiime rescript orient-seqs to standardize read directionality across studies, assigns taxonomy via a pre-trained Naïve Bayes classifier (qiime feature-classifier classify-sklearn; default confidence 0.7), and constructs a phylogenetic tree through SEPP fragment insertion into the GreenGenes2 reference phylogeny regardless of the taxonomy database selected. To reduce the computational barrier for large cohort studies, all required database files—including a GSR-DB classifier trained locally against QIIME2 2024.10's scikit-learn version on first invocation—are downloaded and validated automatically with --dl, requiring no manual database preparation by the user.

Three taxonomy databases are supported and selectable at runtime via --db-type: GreenGenes2 2024.09 (default), SILVA 138.99, and GSR-DB (a gut-specific reference). The final outputs—tree-placed features retained in merged-table-tree.qza, with classifications stored in merged-taxonomy.qza—are directly compatible with QIIME2 phylogenetic and compositional diversity analyses across merged cross-study datasets.
