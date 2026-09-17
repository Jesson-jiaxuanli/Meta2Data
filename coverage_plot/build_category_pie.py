# -*- coding: utf-8 -*-
"""
饼图: 真实字段前 90%(243 / 102,166) 按单词语义分类
------------------------------------------------
- 行 = 语料真实字段的前 243 个(累计覆盖 90% 出现量), 来自 realfield_frequencies.csv
- 每个字段用 char_fp 映射到字典 canonical, 再归入 9 个单词分类
- 9 类(每个一个词): Admin / Host / Sample / Geography / Time / Environment /
  Sequencing / Assembly / Diagnostic
- 无表头; 全英文; 中心 = TOP90%; 配色沿用直方图色系
输出: category_pie.png + top243_classification.csv
"""
import csv, os, re, json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams["axes.unicode_minus"] = False

HERE = os.path.dirname(os.path.abspath(__file__))
DICT = r"Y:\小项目\clone_repo\Meta2Data\docs\NCBI_Biosample.json"
REAL = os.path.join(HERE, "realfield_frequencies.csv")
TOPN = 243  # rank<=243 累计覆盖 90%

# 9 个单词分类: 标签 + 颜色
CATS = {
    "admin":  ("Admin",       "#2c7fb8"),
    "host":   ("Host",        "#d95f0e"),
    "sample": ("Sample",      "#fd8d3c"),
    "geo":    ("Geography",   "#08519c"),
    "time":   ("Time",        "#6baed6"),
    "env":    ("Environment", "#31a354"),
    "seq":    ("Sequencing",  "#b30000"),
    "asm":    ("Assembly",    "#ffe08a"),
    "diag":   ("Diagnostic",  "#807dba"),
}

# --- canonical -> 粗分类(host/source/spenv/assay/admin) ---
CATEGORY = {
    "geographic location": "spenv", "collection date": "spenv",
    "latitude and longitude": "spenv", "longitude": "spenv", "latitude": "spenv",
    "depth": "spenv", "elevation": "spenv", "environmental medium": "spenv",
    "broad-scale environmental context": "spenv",
    "local-scale environmental context": "spenv",
    "host": "host", "sex": "host", "host disease": "host", "age": "host",
    "is tumor": "host", "host subject id": "host", "host health state": "host",
    "host common name": "host", "host sex": "host", "host age": "host",
    "race": "host", "development stage": "host", "subject is affected": "host",
    "histological type": "host", "study disease": "host",
    "isolation source": "source", "tissue": "source", "isolate": "source",
    "strain": "source", "analyte type": "source", "source name": "source",
    "sample capture status": "source", "sample type": "source",
    "cell type": "source", "cultivar": "source", "ecotype": "source",
    "genotype": "source", "derived from": "source", "metagenome source": "source",
    "lineage/clade name": "source", "scientific_name": "source",
    "common name": "source", "treatment": "source",
    "purpose of sequencing": "assay", "assembly software": "assay",
    "binning software": "assay", "binning parameters": "assay",
    "completeness score": "assay", "completeness software": "assay",
    "assembly quality": "assay", "contamination score": "assay",
    "taxonomic identity marker": "assay", "molecular data type": "assay",
    "sequencing method": "assay", "investigation type": "assay",
    "diagnostic_pcr_protocol_1": "assay", "diagnostic_pcr_Ct_value_1": "assay",
    "diagnostic_gene_name_1": "assay", "diagnostic_pcr_protocol_2": "assay",
    "replicate": "assay",
    "INSDC first public": "admin", "INSDC last update": "admin",
    "sample name": "admin", "INSDC center name": "admin", "Submitter Id": "admin",
    "ENA-CHECKLIST": "admin", "INSDC status": "admin", "study name": "admin",
    "gap accession": "admin", "gap sample id": "admin", "gap subject id": "admin",
    "biospecimen repository": "admin", "submitter handle": "admin",
    "submitted sample id": "admin", "submitted subject id": "admin",
    "biospecimen repository sample id": "admin", "study design": "admin",
    "gap consent code": "admin", "gap consent short name": "admin",
    "External Id": "admin", "collected by": "admin", "INSDC center alias": "admin",
    "collecting institution": "admin", "broker name": "admin",
    "collector name": "admin", "project name": "admin",
    "biomaterial provider": "admin", "collection method": "admin",
    "collection device": "admin", "sequenced by": "admin",
}
EXTRA = {
    "virus identifier": "source", "serotype": "source", "brain region": "host",
    "habitat": "spenv", "individual": "host", "organism": "source",
    "race": "host", "target gene": "assay", "sequence_type": "assay",
    "chip antibody": "assay", "GISAID accession": "admin",
    "gap_parent_phs": "admin", "Sampling Strategy": "assay",
    "receipt date": "admin", "subject id": "host", "environmental-sample": "source",
    "cemba_id": "admin", "collection_timestamp": "spenv", "time": "spenv",
    "physical_specimen_location": "admin", "dna_extracted": "assay",
    "physical_specimen_remaining": "admin", "batch": "admin", "tolid": "admin",
    "GAL": "admin", "GAL_sample_id": "admin", "tmp": "admin",
    "specimen_id": "admin", "potential_contaminant": "assay", "sample_id": "admin",
    "identifier_affiliation": "admin", "metagenome source": "source",
    "host anatomical part": "source", "definition for seropositive sample": "host",
    "ArrayExpress-SPECIES": "source", "scientific_name": "source",
    "diagnostic_pcr_protocol_3": "assay", "diagnostic_gene_name_2": "assay",
    "diagnostic_gene_name_3": "assay", "diagnostic_pcr_Ct_value_2": "assay",
    "diagnostic_pcr_Ct_value_3": "assay",
    "taxonomic classification": "assay", "MAG coverage software": "assay",
    "number of contigs": "assay", "GUNC clade separation score": "assay",
    "GUNC contamination score": "assay", "GUNC reference representation score": "assay",
    "GUNC version": "assay", "SPIRE genome cluster": "assay",
    "SPIRE genome id": "assay", "contig N50": "assay",
    "derived from assembly": "assay", "linked to SPIRE sample": "assay",
    "linked to SPIRE study": "assay", "linked to analysis project": "assay",
    "taxonomic classification software": "assay",
    "metagenomic": "source",
}
EXTRA2 = {
    "collection method": "admin", "breed": "source",
    "source material identifiers": "admin", "cell line": "source",
    "serovar": "source", "GISAID virus name": "source",
    "isolation and growth condition": "assay", "source type": "source",
    "purpose of sampling": "assay", "isolate name alias": "source",
    "sample collection device or method": "admin", "disease": "host",
    "specimen voucher": "admin", "sample size": "source",
    "reference for biomaterial": "admin", "sample material processing": "assay",
    "identified by": "admin", "host description": "host", "phenotype": "host",
    "host tissue sampled": "source", "number of replicons": "assay",
    "temperature": "spenv", "altitude": "spenv", "relationship to oxygen": "source",
    "population": "host", "host taxonomy ID": "host", "ethnicity": "host",
    "body product": "source", "life stage": "host", "host body product": "source",
    "wastewater sample duration": "spenv", "wastewater sample matrix": "source",
    "wastewater sample type": "source", "wastewater population": "host",
    "food product origin geographic location": "spenv",
    "wastewater surveillance target 1": "assay",
    "wastewater surveillance target 1 known present": "assay",
    "timepoint": "spenv", "description": "admin", "ploidy": "assay",
    "environmental package": "admin", "host life stage": "host",
    "culture collection": "admin", "purpose of wastewater sampling": "assay",
    "host genotype": "host", "disease stage": "host",
}
COARSE = {**CATEGORY, **EXTRA, **EXTRA2}

# --- 把 spenv 细分 geo/time/env, assay 细分 seq/asm/diag ---
GEO = {"geographic location", "latitude and longitude", "longitude", "latitude",
       "depth", "elevation", "altitude", "food product origin geographic location"}
TIME = {"collection date", "timepoint", "collection_timestamp", "time",
        "wastewater sample duration"}
ASM = {"assembly software", "binning software", "binning parameters",
       "completeness score", "completeness software", "assembly quality",
       "contamination score", "taxonomic identity marker", "taxonomic classification",
       "MAG coverage software", "number of contigs", "GUNC clade separation score",
       "GUNC contamination score", "GUNC reference representation score", "GUNC version",
       "SPIRE genome cluster", "SPIRE genome id", "contig N50", "derived from assembly",
       "linked to SPIRE sample", "linked to SPIRE study", "linked to analysis project",
       "taxonomic classification software", "number of replicons", "ploidy"}
DIAG = {"diagnostic_pcr_protocol_1", "diagnostic_pcr_protocol_2", "diagnostic_pcr_protocol_3",
        "diagnostic_pcr_Ct_value_1", "diagnostic_pcr_Ct_value_2", "diagnostic_pcr_Ct_value_3",
        "diagnostic_gene_name_1", "diagnostic_gene_name_2", "diagnostic_gene_name_3",
        "wastewater surveillance target 1", "wastewater surveillance target 1 known present"}

# --- 字典 char_fp -> canonical ---
def fp(s): return re.sub(r"[^a-z0-9]", "", s.lower())

# 用 char_fp 归一 canonical, 避开尾空格/大小写差异
COARSE_FP = {fp(k): v for k, v in COARSE.items()}
GEO_FP = {fp(x) for x in GEO}
TIME_FP = {fp(x) for x in TIME}
ASM_FP = {fp(x) for x in ASM}
DIAG_FP = {fp(x) for x in DIAG}

def refine(canon, coarse):
    cf = fp(canon)
    if coarse == "spenv":
        return "geo" if cf in GEO_FP else "time" if cf in TIME_FP else "env"
    if coarse == "assay":
        return "asm" if cf in ASM_FP else "diag" if cf in DIAG_FP else "seq"
    if coarse == "source":
        return "sample"
    return coarse  # host / admin
d = json.load(open(DICT, encoding="utf-8"))
fp2c = {}
for k, al in d.items():
    fp2c.setdefault(fp(k), k)
    for a in al:
        fp2c.setdefault(fp(a), k)

# --- top-243 真实字段 ---
rows = []
with open(REAL, encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if int(r["rank"]) > TOPN:
            break
        rows.append((r["field_repr"], int(r["occurrence_count"])))

cat_sum = {k: 0 for k in CATS}
cat_cnt = {k: 0 for k in CATS}
unmapped = []
class_rows = []
for nm, fr in rows:
    canon = fp2c.get(fp(nm))
    coarse = COARSE_FP.get(fp(canon)) if canon else None
    if coarse is None:
        unmapped.append((nm, canon, fr))
        cat = "sample"
    else:
        cat = refine(canon, coarse)
    cat_sum[cat] += fr
    cat_cnt[cat] += 1
    class_rows.append((nm, canon, fr, cat))

if unmapped:
    print("!! unmapped (%d):" % len(unmapped))
    for nm, c, fr in unmapped:
        print("   ", nm, "| canon=", c, "| freq=", fr)

total = sum(cat_sum.values())
with open(os.path.join(HERE, "top243_classification.csv"), "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["field", "dict_canonical", "occurrence_count", "category"])
    for nm, c, fr, cat in class_rows:
        w.writerow([nm, c, fr, CATS[cat][0]])

# --- 饼图 ---
order = sorted(CATS, key=lambda k: cat_sum[k], reverse=True)
sizes = [cat_sum[k] for k in order]
colors = [CATS[k][1] for k in order]
labels = [f"{CATS[k][0]}  ({cat_sum[k]/1e6:.0f}M, {cat_cnt[k]} fields)" for k in order]

fig, ax = plt.subplots(figsize=(11, 7.2))
wedges, _t, autotexts = ax.pie(
    sizes, colors=colors, startangle=90, counterclock=False,
    autopct=lambda p: f"{p:.1f}%" if p >= 2 else "", pctdistance=0.75,
    wedgeprops=dict(width=0.55, edgecolor="white", linewidth=2),
    textprops=dict(fontsize=11, fontweight="bold"))

def _lum(h):
    r, g, b = int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255
for t, c in zip(autotexts, colors):
    t.set_color("black" if _lum(c) > 0.6 else "white")

ax.legend(wedges, labels, loc="center left", bbox_to_anchor=(0.98, 0.5),
          fontsize=11, frameon=False, labelspacing=1.2)
ax.text(0, 0, "TOP90%", ha="center", va="center", fontsize=22,
        fontweight="bold", color="#b30000")
ax.set_aspect("equal")
fig.tight_layout()
fig.savefig(os.path.join(HERE, "category_pie.png"), dpi=160, bbox_inches="tight")

print("total=%.0fM" % (total/1e6))
for k in order:
    print(f"  {CATS[k][0]:12s} {cat_cnt[k]:3d} fields  {cat_sum[k]/1e6:7.1f}M  {cat_sum[k]/total*100:5.1f}%")
