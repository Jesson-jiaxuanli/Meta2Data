# Module 2 · AmpliconPIP

## ☑ Step 1 — Platform Detection & Distribution

```
metadata.csv → Parse Datasets & SRA IDs → Platform Detection (NCBI/CNCB batch API)
                                                        │
              ┌─────────────────┬──────────────────┬───┴──────────────────┐
              │                 │                  │                      │
           Illumina           PacBio           Ion Torrent               454
              │                 │                  │                      │
              ▼                 ▼                  ▼                      ▼
          SRA Download      SRA Download       SRA Download          SRA Download
              │                 │                  │                      │
              ▼                 ▼                  ▼                      ▼
       fastp QC            fastp QC           fastp QC              fastp QC
    (adapter + trim)   (adapter + trim)   (adapter + trim)      (adapter + trim)
              │                 │                  │                      │
              ▼                 ▼                  ▼                      ▼
       Quality Check       DADA2              DirectDerep          Deduplication
     (score diversity)    Denoise            (vsearch)             (vsearch)
              │                 │                  │                      │
              ▼                 ▼                  ▼                      ▼
       DADA2 Denoise      Extract Reads      UNOISE3 Denoise       Chimera Removal
    *(DegradedQ→UNOISE3)  (primer region)    (vsearch)             (vsearch uchime3)
                                                   │                      │
                                                   ▼                      ▼
                                            Map Reads→ZOTUs         Cluster OTUs
                                                                   (vsearch cluster)
                                                                          │
                                                                          ▼
                                                                   Filter Low-Freq
                                                                   OTUs (< 0.005%)
              │                 │                  │                      │
              └─────────────────┴──────────────────┴──────────────────────┘
                                                │
                                                ▼
                                    Make Qiime2 Manifest
                                                │
                                                ▼
                                    Import FASTQ → QZA
                                                │
                                                ▼
                              {dataset}-final-rep-seqs.qza  +  table.qza
                                                │
                                                ▼
                                          Cleanup tmp/
```

---

## 总体步骤概括

| # | 步骤 | 说明 |
|---|------|------|
| 1 | 解析元数据 | 从 CSV 提取 Dataset ID 和 SRA 列表 |
| 2 | 平台检测 | 批量查询 NCBI/CNCB API，缓存结果，分发至四条子流程 |
| 3 | SRA 下载 | 优先 ENA FTP，失败回退 NCBI/CNCB，支持断点续传 |
| 4 | 质量控制 | fastp 去接头 + 过滤 (<50 bp reads 丢弃) |
| 5 | 平台特异去噪 | **Illumina/PacBio**: DADA2；**Ion Torrent**: UNOISE3；**454**: OTU聚类 + 嵌合体去除 |
| 6 | Qiime2 导入 | 生成 Manifest → import → 质量过滤 QZA |
| 7 | 输出 & 清理 | 保存 rep-seqs.qza / table.qza，删除中间文件 |

> **平台差异核心：** 去噪策略不同。Illumina/PacBio 用 DADA2 生成 ASV；Ion Torrent 因质量分值退化走 vsearch UNOISE3 生成 ZOTU；454 走传统 OTU 聚类流程（去重→去嵌合体→聚类→低频过滤）。
