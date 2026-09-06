# 字典代码修改记录 (dict_change_log)

- 时间: 2026-09-07 00:35:48
- 唯一被修改文件: `Y:\小项目\clone_repo\Meta2Data\docs\NCBI_Biosample.json`
- 备份: `Y:\小项目\clone_repo\Meta2Data\docs\NCBI_Biosample.json.bak_20260907_003548`
- 格式核对: WARNING: re-serialization differs from disk formatting (content preserved, cosmetic diff possible)
- 键总数: 963 -> 987
- 其它代码/文件: 未改动

## 修改的现有键 (追加同义词, 原有内容保留)

- `geographic location`: 追加 ['geographic location (region and locality)']
  - 现值: ['geographic location country and or sea', 'geographic locations', 'geographic location (country and/or sea)', 'geographic location (locality)', 'geographic location (country and/or sea region)', 'geographic location', 'geographic location (country and/or sea,region)', 'geographic location (country:region,area)', 'geolocname', 'geo_loc_name', 'geographical location', 'geographic location (country)', 'geographical location (country:region, location)', 'country', 'geographic origin', 'geo loc name', 'geographic location (country and/or sea, region)', 'geographic location (region and locality)']
- `derived from`: 追加 ['sample derived from']
  - 现值: ['derived from', 'derived_from', 'sample derived from']
- `local-scale environmental context`: 追加 ['local environmental context']
  - 现值: ['env local range', 'environment feature', 'local-scale environmental context', 'env feature', 'feature', 'environment (feature)', 'env_local_scale', 'env local scale', 'local scale environmental context', 'local environmental context']
- `metagenome source`: 追加 ['metagenomic source']
  - 现值: ['metagenome_source', 'metagenome source', 'metagenomic source']
- `race`: 追加 ['host_race']
  - 现值: ['race', 'host_race']
- `serotype`: 追加 ['serotype (required for a seropositive sample)']
  - 现值: ['serotype', 'serotype (required for a seropositive sample)']
- `host anatomical part`: 追加 ['anatomical_part']
  - 现值: ['host_anatomical_part', 'host anatomical part', 'anatomical_part']
- `elevation`: 追加 ['geographic location (elevation)']
  - 现值: ['elev', 'elevation', 'geographic location (elevation)']
- `GISAID accession`: 追加 ['GISAID Accession ID']
  - 现值: ['gisaid accession', 'gisaid_accession', 'GISAID accession', 'GISAID Accession ID']

## 新增的键

- `longitude`: ['longitude', 'geographic location (longitude)']
- `latitude`: ['latitude', 'geographic location (latitude)']
- `INSDC last update`: ['INSDC last update', 'ENA-LAST-UPDATE', 'ENA last update']
- `INSDC first public`: ['INSDC first public', 'ENA first public', 'ENA-FIRST-PUBLIC']
- `assembly software`: ['assembly software']
- `binning software`: ['binning software']
- `binning parameters`: ['binning parameters']
- `completeness score`: ['completeness score']
- `completeness software`: ['completeness software']
- `assembly quality`: ['assembly quality']
- `contamination score`: ['contamination score']
- `taxonomic identity marker`: ['taxonomic identity marker']
- `sequencing method`: ['sequencing method']
- `diagnostic_pcr_protocol_1`: ['diagnostic_pcr_protocol_1']
- `diagnostic_pcr_protocol_2`: ['diagnostic_pcr_protocol_2']
- `diagnostic_pcr_protocol_3`: ['diagnostic_pcr_protocol_3']
- `diagnostic_gene_name_3`: ['diagnostic_gene_name_3']
- `diagnostic_pcr_Ct_value_3`: ['diagnostic_pcr_Ct_value_3']
- `taxonomic classification`: ['taxonomic classification']
- `MAG coverage software`: ['MAG coverage software']
- `number of contigs`: ['number of contigs']
- `sequence_type`: ['sequence_type']
- `chip antibody`: ['chip antibody']
- `target gene`: ['target gene']

## 未改动校验
- 原有 963 键中, 9 个被追加同义词, 其余 954 个逐字未变


---

# 追加 (all-residual) — 2026-09-07 00:49:26

- 唯一被修改文件: `Y:\小项目\clone_repo\Meta2Data\docs\NCBI_Biosample.json`
- 备份(改动前, 987键): `Y:\小项目\clone_repo\Meta2Data\docs\NCBI_Biosample.json.bak_20260907_004839`
- 键总数: 987 -> 1044
- 全部为新增键(裸键, 值=[自身]); 无现有键被改动, 无删除

新增键:
- `INSDC center name`: ['INSDC center name']
- `Submitter Id`: ['Submitter Id']
- `ENA-CHECKLIST`: ['ENA-CHECKLIST']
- `INSDC status`: ['INSDC status']
- `External Id`: ['External Id']
- `scientific_name`: ['scientific_name']
- `INSDC center alias`: ['INSDC center alias']
- `collecting institution`: ['collecting institution']
- `broker name`: ['broker name']
- `collector name`: ['collector name']
- `common name`: ['common name']
- `lineage/clade name`: ['lineage/clade name']
- `diagnostic_pcr_Ct_value_1`: ['diagnostic_pcr_Ct_value_1']
- `diagnostic_gene_name_1`: ['diagnostic_gene_name_1']
- `replicate`: ['replicate']
- `diagnostic_gene_name_2`: ['diagnostic_gene_name_2']
- `diagnostic_pcr_Ct_value_2`: ['diagnostic_pcr_Ct_value_2']
- `virus identifier`: ['virus identifier']
- `definition for seropositive sample`: ['definition for seropositive sample']
- `GUNC clade separation score`: ['GUNC clade separation score']
- `GUNC contamination score`: ['GUNC contamination score']
- `GUNC reference representation score`: ['GUNC reference representation score']
- `GUNC version`: ['GUNC version']
- `SPIRE genome cluster`: ['SPIRE genome cluster']
- `SPIRE genome id`: ['SPIRE genome id']
- `contig N50`: ['contig N50']
- `derived from assembly`: ['derived from assembly']
- `linked to SPIRE sample`: ['linked to SPIRE sample']
- `linked to SPIRE study`: ['linked to SPIRE study']
- `linked to analysis project`: ['linked to analysis project']
- `taxonomic classification software`: ['taxonomic classification software']
- `brain region`: ['brain region']
- `ArrayExpress-SPECIES`: ['ArrayExpress-SPECIES']
- `gap_parent_phs`: ['gap_parent_phs']
- `Sampling Strategy`: ['Sampling Strategy']
- `receipt date`: ['receipt date']
- `metagenomic`: ['metagenomic']
- `subject id`: ['subject id']
- `environmental-sample`: ['environmental-sample']
- `individual`: ['individual']
- `organism`: ['organism']
- `cemba_id`: ['cemba_id']
- `collection_timestamp`: ['collection_timestamp']
- `time`: ['time']
- `physical_specimen_location`: ['physical_specimen_location']
- `dna_extracted`: ['dna_extracted']
- `physical_specimen_remaining`: ['physical_specimen_remaining']
- `habitat`: ['habitat']
- `batch`: ['batch']
- `identifier_affiliation`: ['identifier_affiliation']
- `tolid`: ['tolid']
- `GAL`: ['GAL']
- `GAL_sample_id`: ['GAL_sample_id']
- `tmp`: ['tmp']
- `specimen_id`: ['specimen_id']
- `potential_contaminant`: ['potential_contaminant']
- `sample_id`: ['sample_id']
