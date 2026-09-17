# -*- coding: utf-8 -*-
"""
用"真实字段前90%(243个)"重建 coverage_plot 下的 residual_review_90_prefilled.csv,
按频次顺序填充, 并尽量补齐所有列。
可算的列全填; 值类列(residual_values/cand)从 official_dict_values + residual_review_90 携带;
人工判断列(reason)留空(无法臆造)。非破坏: 先备份。
"""
import csv, os, re, json, shutil, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
DICT = r"Y:\小项目\clone_repo\Meta2Data\docs\NCBI_Biosample.json"
REAL = os.path.join(HERE, "realfield_frequencies.csv")
CLS  = os.path.join(HERE, "top243_classification.csv")   # 由 build_category_pie.py 生成
OFFV = r"Y:\ncbi_corpus\official_dict_values.csv"
RR90 = r"Y:\ncbi_corpus\residual_review_90.csv"
OUT  = os.path.join(HERE, "residual_review_90_prefilled.csv")

def fp(s): return re.sub(r"[^a-z0-9]", "", s.lower())

# 字典: fp->canonical, canonical->别名数
d = json.load(open(DICT, encoding="utf-8"))
fp2c, n_alias = {}, {}
for k, al in d.items():
    n_alias[k] = len(al)
    fp2c.setdefault(fp(k), k)
    for a in al:
        fp2c.setdefault(fp(a), k)

# 饼图分类(9类) : field -> category
cat_by_field = {}
for r in csv.DictReader(open(CLS, encoding="utf-8-sig")):
    cat_by_field[fp(r["field"])] = r["category"]

# 官方 canonical 代表值: fp(canonical) -> values(top15)
off_vals = {}
for r in csv.DictReader(open(OFFV, encoding="utf-8-sig")):
    off_vals[fp(r["canonical"])] = r["representative_values(top15)"]

# residual_review_90: fp(name) -> 记录
rr = {}
for r in csv.DictReader(open(RR90, encoding="utf-8-sig")):
    rr[fp(r["residual_name"])] = r

# top-243 真实字段(按频次顺序)
fields = []
for r in csv.DictReader(open(REAL, encoding="utf-8-sig")):
    if int(r["rank"]) > 243:
        break
    fields.append((r["field_repr"], int(r["occurrence_count"]), r["cumulative_pct"]))

UNIV_YES = {"Host", "Sample", "Geography", "Time", "Environment"}

def merge_status(nm):
    f = fp(nm); canon = fp2c.get(f)
    if canon is None:
        return "不在字典", ""
    if fp(canon) == f:
        return ("规范键(其他并入它)" if n_alias.get(canon, 1) > 1 else "独立键(仅自身)"), canon
    return f"合并→ {canon}", canon

header = ["rank", "residual_name", "freq", "cumulative_pct", "type",
          "residual_values(top15)", "cand1_ref", "cand1_values",
          "宏基因组相关", "合并到(据字典)", "饼图分类", "通用(meta-analysis)", "reason"]

out_rows = [header]
n_val, n_cand = 0, 0
for i, (nm, fr, cum) in enumerate(fields, 1):
    f = fp(nm)
    canon = fp2c.get(f)
    cat = cat_by_field.get(f, "")
    ms, canon2 = merge_status(nm)
    rec = rr.get(f)

    # 值(top15): 优先该字段自身评审值, 否则用其 canonical 官方代表值
    if rec and rec.get("residual_values(top15)"):
        vals = rec["residual_values(top15)"]
    else:
        vals = off_vals.get(fp(canon), "") if canon else ""
    if vals:
        n_val += 1

    # 候选: 该字段映射到的字典 canonical 及其官方值
    cand_ref = canon or (rec.get("cand1") if rec else "")
    cand_vals = off_vals.get(fp(canon), "") if canon else (rec.get("cand1_values", "") if rec else "")
    if cand_ref:
        n_cand += 1

    typ = rec.get("type_hint", "") if rec else ""
    meta = "组装/分箱/MAG" if cat == "Assembly" else ""
    univ = "是" if cat in UNIV_YES else "否"

    out_rows.append([i, nm, fr, cum, typ, vals, cand_ref, cand_vals,
                     meta, ms, cat, univ, ""])

# 备份原文件
if os.path.exists(OUT):
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    shutil.copy2(OUT, OUT.replace(".csv", f".bak_{ts}.csv"))

with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
    csv.writer(f).writerows(out_rows)

print("写入:", OUT, " 行数:", len(out_rows) - 1)
print(f"有值(top15)的行: {n_val}/243    有候选 canonical 的行: {n_cand}/243")
from collections import Counter
print("饼图分类分布:", dict(Counter(r[10] for r in out_rows[1:])))
