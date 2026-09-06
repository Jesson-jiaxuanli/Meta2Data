# 字典合并记录 (dict_merge_log)

- 时间: 2026-09-07 00:35:48
- 字典: `Y:\小项目\clone_repo\Meta2Data\docs\NCBI_Biosample.json`
- 备份: `NCBI_Biosample.json.bak_20260907_003548`
- 键数: 963 -> 987 (+24)

## A. 显式合并 (source -> 规范键)

| 来源词 | 规范键(target) | 动作 |
|---|---|---|
| `geographic location (region and locality)` | `geographic location` | alias added |
| `sample derived from` | `derived from` | alias added |
| `local environmental context` | `local-scale environmental context` | alias added |
| `metagenomic source` | `metagenome source` | alias added |
| `host_race` | `race` | alias added |
| `serotype (required for a seropositive sample)` | `serotype` | alias added |
| `anatomical_part` | `host anatomical part` | alias added |
| `geographic location (elevation)` | `elevation` | alias added |
| `GISAID Accession ID` | `GISAID accession` | alias added |
| `longitude` | `longitude` | created key + alias |
| `geographic location (longitude)` | `longitude` | created key + alias |
| `latitude` | `latitude` | created key + alias |
| `geographic location (latitude)` | `latitude` | created key + alias |
| `INSDC last update` | `INSDC last update` | created key + alias |
| `ENA-LAST-UPDATE` | `INSDC last update` | created key + alias |
| `ENA last update` | `INSDC last update` | created key + alias |
| `INSDC first public` | `INSDC first public` | created key + alias |
| `ENA first public` | `INSDC first public` | created key + alias |
| `ENA-FIRST-PUBLIC` | `INSDC first public` | created key + alias |

## B. NEW 独立裸键 (同义词仅含自身)

| 新键 | freq来源 |
|---|---|
| `assembly software` | residual_review_CORRECTED verdict=NEW |
| `binning software` | residual_review_CORRECTED verdict=NEW |
| `binning parameters` | residual_review_CORRECTED verdict=NEW |
| `completeness score` | residual_review_CORRECTED verdict=NEW |
| `completeness software` | residual_review_CORRECTED verdict=NEW |
| `assembly quality` | residual_review_CORRECTED verdict=NEW |
| `contamination score` | residual_review_CORRECTED verdict=NEW |
| `taxonomic identity marker` | residual_review_CORRECTED verdict=NEW |
| `sequencing method` | residual_review_CORRECTED verdict=NEW |
| `diagnostic_pcr_protocol_1` | residual_review_CORRECTED verdict=NEW |
| `diagnostic_pcr_protocol_2` | residual_review_CORRECTED verdict=NEW |
| `diagnostic_pcr_protocol_3` | residual_review_CORRECTED verdict=NEW |
| `diagnostic_gene_name_3` | residual_review_CORRECTED verdict=NEW |
| `diagnostic_pcr_Ct_value_3` | residual_review_CORRECTED verdict=NEW |
| `taxonomic classification` | residual_review_CORRECTED verdict=NEW |
| `MAG coverage software` | residual_review_CORRECTED verdict=NEW |
| `number of contigs` | residual_review_CORRECTED verdict=NEW |
| `sequence_type` | residual_review_CORRECTED verdict=NEW |
| `chip antibody` | residual_review_CORRECTED verdict=NEW |
| `target gene` | residual_review_CORRECTED verdict=NEW |

## 本轮未处理 (需另行定夺)
- ORG 6 (organism 类, organism 非属性字典字段) — 不入字典
- DISCARD 32 (平台/管理元数据) — 丢弃
- GROUP_NEW 6 (机构名簇 INSDC center name/alias, collecting institution, broker name, identifier_affiliation, GAL) — 彼此为不同字段, 待单独决定


---

# 追加 (all-residual): 把 90 profiled 全部列名写进字典 — 2026-09-07 00:49:26

- 备份(改动前, 987键): `NCBI_Biosample.json.bak_20260907_004839`
- 键数: 987 -> 1044 (+57)
- 策略: 用户指令“所有列名都写进去”, 不按 verdict/簇过滤; 每个未在字典的列名作独立裸键(同义词仅含自身)

## 新增裸键 (57)

| 列名 | freq | 原verdict |
|---|---|---|
| `INSDC center name` | 14431765 | GROUP_NEW |
| `Submitter Id` | 14376720 | MAP |
| `ENA-CHECKLIST` | 14295165 | DISCARD |
| `INSDC status` | 13776097 | DISCARD |
| `External Id` | 10368571 | DISCARD |
| `scientific_name` | 8972534 | ORG |
| `INSDC center alias` | 6865361 | GROUP_NEW |
| `collecting institution` | 5693164 | GROUP_NEW |
| `broker name` | 5546151 | GROUP_NEW |
| `collector name` | 4461306 | MAP |
| `common name` | 3906571 | ORG |
| `lineage/clade name` | 2037602 | MAP |
| `diagnostic_pcr_Ct_value_1` | 2036582 | MAP |
| `diagnostic_gene_name_1` | 1689613 | MAP |
| `replicate` | 1548070 | MAP |
| `diagnostic_gene_name_2` | 1511786 | MAP |
| `diagnostic_pcr_Ct_value_2` | 1511762 | MAP |
| `virus identifier` | 1443435 | MAP |
| `definition for seropositive sample` | 1264371 | DISCARD |
| `GUNC clade separation score` | 1019328 | DISCARD |
| `GUNC contamination score` | 1019328 | DISCARD |
| `GUNC reference representation score` | 1019328 | DISCARD |
| `GUNC version` | 1019328 | DISCARD |
| `SPIRE genome cluster` | 1019328 | DISCARD |
| `SPIRE genome id` | 1019328 | DISCARD |
| `contig N50` | 1019328 | DISCARD |
| `derived from assembly` | 1019328 | DISCARD |
| `linked to SPIRE sample` | 1019328 | DISCARD |
| `linked to SPIRE study` | 1019328 | DISCARD |
| `linked to analysis project` | 1019328 | DISCARD |
| `taxonomic classification software` | 1019328 | DISCARD |
| `brain region` | 986070 | MAP |
| `ArrayExpress-SPECIES` | 948611 | ORG |
| `gap_parent_phs` | 870993 | MAP |
| `Sampling Strategy` | 687063 | MAP |
| `receipt date` | 644768 | DISCARD |
| `metagenomic` | 547195 | DISCARD |
| `subject id` | 539615 | MAP |
| `environmental-sample` | 533517 | DISCARD |
| `individual` | 406097 | MAP |
| `organism` | 348731 | ORG |
| `cemba_id` | 320568 | DISCARD |
| `collection_timestamp` | 296874 | MAP |
| `time` | 291247 | MAP |
| `physical_specimen_location` | 288551 | MAP |
| `dna_extracted` | 282384 | DISCARD |
| `physical_specimen_remaining` | 281433 | DISCARD |
| `habitat` | 251171 | MAP |
| `batch` | 247563 | DISCARD |
| `identifier_affiliation` | 233664 | GROUP_NEW |
| `tolid` | 233383 | DISCARD |
| `GAL` | 232540 | GROUP_NEW |
| `GAL_sample_id` | 231745 | MAP |
| `tmp` | 224194 | DISCARD |
| `specimen_id` | 201544 | MAP |
| `potential_contaminant` | 201410 | DISCARD |
| `sample_id` | 199686 | MAP |

## 同 char_fp 已由代表键覆盖, 未重复建键 (4)

- `SUBJECT_ID`  (指纹同 `subject id`)
- `scientific name`  (指纹同 `scientific_name`)
- `ArrayExpress-Species`  (指纹同 `ArrayExpress-SPECIES`)
- `Replicate`  (指纹同 `replicate`)

## 已在字典, 跳过 (39)

- `INSDC last update` (DISCARD)
- `INSDC first public` (DISCARD)
- `ENA first public` (DISCARD)
- `geographic location (region and locality)` (MAP)
- `ENA-LAST-UPDATE` (DISCARD)
- `ENA-FIRST-PUBLIC` (DISCARD)
- `ENA last update` (DISCARD)
- `geographic location (longitude)` (MAP)
- `geographic location (latitude)` (MAP)
- `sample derived from` (MAP)
- `local environmental context` (MAP)
- `metagenomic source` (MAP)
- `assembly software` (NEW)
- `binning software` (NEW)
- `binning parameters` (NEW)
- `completeness score` (NEW)
- `completeness software` (NEW)
- `assembly quality` (NEW)
- `contamination score` (NEW)
- `taxonomic identity marker` (NEW)
- `sequencing method` (NEW)
- `diagnostic_pcr_protocol_1` (NEW)
- `host_race` (MAP)
- `diagnostic_pcr_protocol_2` (NEW)
- `diagnostic_pcr_protocol_3` (NEW)
- `diagnostic_gene_name_3` (NEW)
- `diagnostic_pcr_Ct_value_3` (NEW)
- `serotype (required for a seropositive sample)` (MAP)
- `taxonomic classification` (NEW)
- `MAG coverage software` (NEW)
- `number of contigs` (NEW)
- `longitude` (MAP)
- `latitude` (MAP)
- `GISAID Accession ID` (MAP)
- `geographic location (elevation)` (MAP)
- `anatomical_part` (MAP)
- `sequence_type` (NEW)
- `chip antibody` (NEW)
- `target gene` (NEW)
