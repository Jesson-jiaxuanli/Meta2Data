# AmpliconPIP · 流程概览

---

## ① 解析元数据

```
metadata.csv
    │
    ▼
┌─────────────────────────────┐
│ Dataset_A │ SRR001, SRR002  │
│ Dataset_B │ SRR003          │
│ Dataset_C │ SRR004, SRR005  │
└─────────────────────────────┘
```

读取 CSV，每个 BioProject 生成独立 SRA 列表。同时批量查询 NCBI API 获取测序平台，结果写入缓存（避免并行时触发限速）。

---

## ② SRA 下载

```
SRR001 ─┐
SRR002 ─┤──→  ori_fastq/
SRR003 ─┘
```

优先 ENA FTP 下载，失败自动回退 NCBI / CNCB，支持断点续传。

---

## ③ 质量控制 & 引物去除

```
raw reads
    │
    ├─[ fastp ]──────────── 去测序接头，过滤低质量、过短 reads
    │
    └─[ 引物检测 & 去除 ]── 识别并切除 16S 引物序列 → clean reads
```

> PacBio 无此步骤：引物由后续 DADA2 denoise-ccs 的 `--p-front` / `--p-adapter` 参数处理。

---

## ④ 去噪 / 聚类

```
 ATCGGTA...  ╮
 ATCGGTA...  │
 GCTATCG...  ├──→  ≡ ASV / OTU 表
 GCTATCG...  │       (数百条代表序列)
 TTCGAAC...  │
 ...          ╯
(数万条 reads)
```

| 平台 | 去噪策略 |
|------|---------|
| Illumina（正常质量） | DADA2 denoise-paired / single → ASV |
| Illumina（质量退化） | vsearch UNOISE3 → ZOTU |
| Ion Torrent | DADA2 denoise-pyro → ASV |
| PacBio | DADA2 denoise-ccs → ASV |
| 454 | vsearch dereplicate → 嵌合体去除 → OTU 聚类 97% → 低频过滤 |

---

## ⑤ 导入 QIIME2 & 输出

```
ASV / OTU 表
    │
    ▼
[ QIIME2 Import ]
    │
    ├──→  {dataset}-rep-seqs.qza
    └──→  {dataset}-table.qza
```

写入 summary.csv，清理中间文件。
