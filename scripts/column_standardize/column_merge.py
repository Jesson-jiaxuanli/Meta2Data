#!/usr/bin/env python3
"""
column_merge.py — MetaDL 列名标准化（两档字典 + 数据内部推理）

在 MetaDL 完成下载 + 清洗 + 合并（all_metadata_merged.csv）之后引入，取代旧的
单档字典硬改名（apply_column_rename_from_dict / docs/NCBI_Biosample.json）。

设计（运行时不做交互）：
  1) direct 直接合并档  —— 命中即自动应用（精确 / 字符指纹相等的改名或合并）。
  2) recommend 推荐合并 —— 不交互，只列一张可读表让用户自己看：
       第一层（字典）：recommend 档里，目标 canonical 在本表中共现成员 >=2 的组；
       第二层（数据内部）：对既没命中 direct 也没命中 recommend 字典的列，
                          做列间互比（token 指纹完全相等 + JW 模糊且共享词），得到 >=2 列的组。
     两层候选都写进 merge_recommendations.csv（可读表，逗号分隔）+ merge_groups.txt（可编辑分组模板）。
  3) 用户编辑 merge_groups.txt（每行一组 `目标名/成员1/成员2`，换行=新组），
     再跑 apply 把这些合并落地。

三个对外入口：
  apply_direct(df, dict_path)                 -> df           自动应用 direct 档
  build_recommend_table(df, dict_path, out)   -> (rec_csv, groups_txt)  写推荐表 + 分组模板
  apply_user_groups(df, groups_file)          -> df           按用户分组文件落地合并

字典由同目录 build_two_part_dict.py 生成，默认 biosample_canonical_dict.json。
"""

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

DEFAULT_DICT = Path(__file__).parent / "biosample_canonical_dict.json"

REC_TABLE_NAME = "merge_recommendations.csv"
GROUPS_FILE_NAME = "merge_groups.txt"
JW_FUZZY_THRESHOLD = 0.92  # 数据内部 JW 模糊互比阈值（较严，压误合并）

GROUPS_HEADER = (
    "# 列名合并分组 —— 每行一组要合并的列，用 / 分隔。\n"
    "# 行首的列名是合并后【保留】的名字，其余列的单元格并入它；两边都非空且不同 -> 'a|b'。\n"
    "# 换行 = 新的一组。空行、以 # 开头的行都忽略。\n"
    "# 下面是自动推荐的候选，请【删掉你不想合并的行】，需要时可自行改列名/增删成员。\n"
    "# 编辑好后运行：Meta2Data MetaDL --apply-merges <本文件> -o <同一输出目录>\n"
    "#\n"
    "# 例：temperature/temp/water_temperature\n"
    "#\n"
)


# ─── 文本预处理（与 build_canonical_dict.py / 旧 column_standardizer 保持一致）──────
def normalize(text: str) -> str:
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", str(text))
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def char_fp(text: str) -> str:
    """小写、删除所有非字母数字字符。用作跨格式匹配键。"""
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def token_fp(text: str) -> frozenset:
    return frozenset(normalize(text).split())


# ─── 值指纹层（value fingerprint）：读列的“值”，不只看列名 ──────────────────────
# 动机：只比列名会同时产生
#   · 名字像但值异义 -> 误合（ReadFile1Md5/ReadFile2Md5、Platform.1~7 混平台/型号）
#   · 名字不像但值同义 -> 漏合（Layout↔LibraryLayout、lat_lon↔LatitudeLongitude）
# 这一层给每列算“值画像”，再用【行内一致率 + 填充互补性 + 值集合 Jaccard】判两列该不该合：
# 名字负责“提名”，值负责“定夺”。

NAME_PROPOSE_THR = 0.55       # 名字“提名”阈值（放宽，最终由值定夺）
COOCCUR_AGREE_MERGE = 0.60    # 共现且一致率 >= 此值 -> 视作同一字段的重复列
COOCCUR_MIN_FRAC = 0.15       # 判定“共现”所需的共同有值行占比
TEXT_JACCARD_MERGE = 0.34     # 互补填充的文本列，词表 Jaccard 达此值才判同义
_IDLIKE_KINDS = frozenset({"md5", "hexhash", "accession"})

_RE_MD5 = re.compile(r"^[0-9a-f]{32}$")
_RE_HEX = re.compile(r"^[0-9a-f]{16,}$")
_RE_ACC = re.compile(r"^[a-z]{2,6}\d{4,}$")
_RE_DATE = re.compile(r"^\d{4}[-/]\d{1,2}([-/]\d{1,2})?")
_RE_NUM = re.compile(r"^[+-]?\d+(\.\d+)?$")
# 坐标需带小数（真经纬度如 "32.394 N 119.412 E"），避免 "16s of B10" 被当成 16°S
_RE_COORD = re.compile(r"^[+-]?\d{1,3}\.\d+\s*[nsew]\b", re.I)


def _cell_kind(s: str) -> str:
    """粗判单个值的数据类型。"""
    low = s.strip().lower()
    if not low:
        return ""
    if _RE_MD5.match(low):
        return "md5"
    if _RE_COORD.match(low):
        return "geo_coord"
    if _RE_ACC.match(low):
        return "accession"
    if _RE_DATE.match(low):
        return "date"
    if _RE_NUM.match(low):
        return "numeric"
    if _RE_HEX.match(low):
        return "hexhash"
    return "text"


def value_profile(series, sample_n=600):
    """列的值画像：{kind, vset, card, n, avg_tokens}；全空返回 None。"""
    v = series.dropna().astype(str).str.strip()
    v = v[(v != "") & (v.str.lower() != "nan")]
    if v.empty:
        return None
    n = len(v)
    sample = v.sample(min(n, sample_n), random_state=0) if n > sample_n else v
    kinds = Counter(_cell_kind(x) for x in sample)
    kinds.pop("", None)
    dom_kind = kinds.most_common(1)[0][0] if kinds else "text"
    avg_tokens = float(sample.str.split().map(len).mean())
    if dom_kind == "text" and avg_tokens >= 4:
        dom_kind = "free_text"
    uniq = list(dict.fromkeys(x.lower() for x in sample))[:400]
    return {
        "kind": dom_kind,
        "vset": frozenset(uniq),
        "card": int(v.nunique()),
        "n": n,
        "avg_tokens": round(avg_tokens, 2),
    }


def _norm_series(s):
    return s.astype(str).str.strip().str.lower()


def _jaccard(a: frozenset, b: frozenset) -> float:
    if not a or not b:
        return 0.0
    u = len(a | b)
    return len(a & b) / u if u else 0.0


VALUE_NOMINATE_JACCARD = 0.50  # 值几乎相同的提名门槛（仅文本类，控制误报）


def _value_prenominate(p1, p2) -> bool:
    """值提名：名字不沾边、但值几乎相同的列对也提名（并集的“值”那一路）。
    仅对文本类做（数字/日期/坐标/ID 的值集合重叠是噪声，不足以证明同字段）；
    最终仍由 column_relation 值定夺，这里只决定是否值得跑一次定夺。"""
    if not p1 or not p2 or p1["kind"] != p2["kind"]:
        return False
    if p1["kind"] not in ("text", "free_text"):
        return False
    return _jaccard(p1["vset"], p2["vset"]) >= VALUE_NOMINATE_JACCARD


def column_relation(s1, s2, p1, p2):
    """判两列关系，返回 (verdict, score)。
    verdict: 'merge'（该合）/ 'veto'（别合）/ 'weak'（值证据不足，仅名字提名不够）。
    规则：
      1) 共现（两列在同一批行上都有值）：看行内取值一致率。
         高 -> 同一字段的重复/等价列 -> 'merge'；低 -> 平行的不同字段 -> 'veto'。
      2) 填充互补（几乎不共现，典型=不同来源库各填各行）：
         唯一 ID 类（md5/hash/accession）值帮不上忙 -> 'weak'（交给名字严判）；
         其余同 kind -> 'merge'（跨库同义），kind 不同 -> 'weak'。
    """
    a, b = _norm_series(s1), _norm_series(s2)
    va = a[(a != "") & (a != "nan")]
    vb = b[(b != "") & (b != "nan")]
    common = va.index.intersection(vb.index)
    either = va.index.union(vb.index)
    if len(either) == 0:
        return "weak", 0.0
    if len(common) >= max(5, COOCCUR_MIN_FRAC * len(either)):
        agree = float((a.loc[common] == b.loc[common]).mean())
        if agree >= COOCCUR_AGREE_MERGE:
            return "merge", round(agree, 4)
        return "veto", round(agree, 4)
    # 填充互补（各来源填各行）：只有当值本身携带“字段身份”时才敢合
    if p1 and p2 and p1["kind"] == p2["kind"]:
        k = p1["kind"]
        if k == "geo_coord":
            # 坐标格式很特异，互补即视作同一“经纬度”字段（坐标各不同，不看 Jaccard）
            return "merge", round(max(0.5, _jaccard(p1["vset"], p2["vset"])), 4)
        if k in ("text", "free_text"):
            # 文本需“多数词表重叠”才算同义（单个共享词如 gut 不足以合 isolation_source/tissue）
            j = _jaccard(p1["vset"], p2["vset"])
            return ("merge", round(j, 4)) if j >= TEXT_JACCARD_MERGE else ("weak", round(j, 4))
        # numeric/date/md5/hexhash/accession：值集合帮不上忙，交给名字/字典严判
        return "weak", 0.0
    return "weak", 0.0


def value_aware_peer_groups(df, cols, fill_rates, name_thr=NAME_PROPOSE_THR,
                            protected=None):
    """名字提名 + 值定夺的列聚类。跑在【全部列】上，让未标准化的列去和表内
    已有的标准列（canonical/核心列）做值比对，从而把 Layout↔LibraryLayout、
    LatitudeLongitude↔lat_lon 这类跨库同义对**用值证据**挖进推荐档（不靠硬编码）。

    1) 名字相似度 >= name_thr 或共享词 token 的列对 -> 候选对（提名，阈值放宽）；
       且要求每条边至少含一个非 protected 列（不去合并两个核心 canonical）；
    2) 逐对用 column_relation 定夺：只有 'merge' 才连边，'veto'/'weak' 丢弃；
    3) 连通分量即合并组；代表名优先取 protected(标准/核心)列，否则取填充率最高者。
    返回 groups = [(gid, rep, [(member, value_sim), ...]), ...]。
    """
    from rapidfuzz.distance import JaroWinkler

    protected = set(protected or ())
    cols = [c for c in cols if c in df.columns]
    if len(cols) < 2:
        return []
    profiles = {c: value_profile(df[c]) for c in cols}
    norms = {c: normalize(c) for c in cols}
    n = len(cols)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(n):
        for j in range(i + 1, n):
            a, b = norms[cols[i]], norms[cols[j]]
            if not a or not b:
                continue
            # 两个核心列之间不主动合并（它们是有意区分的标准字段）
            if cols[i] in protected and cols[j] in protected:
                continue
            # 提名并集：名字词面（共享词 或 JW≥阈）∪ 值几乎相同（文本类值集合高重叠）。
            # 任一路提名即可，最终由 column_relation 值定夺。
            shared_tok = bool(set(a.split()) & set(b.split()))
            name_nom = shared_tok or JaroWinkler.similarity(a, b) >= name_thr
            if not name_nom and not _value_prenominate(profiles[cols[i]], profiles[cols[j]]):
                continue  # 名字不沾边、值也不像 -> 不提名
            verdict, _ = column_relation(
                df[cols[i]], df[cols[j]], profiles[cols[i]], profiles[cols[j]])
            if verdict == "merge":
                pi, pj = find(i), find(j)
                if pi != pj:
                    parent[pi] = pj

    buckets = defaultdict(list)
    for i in range(n):
        buckets[find(i)].append(cols[i])

    def _rep_key(c):
        # 优先标准/核心列作代表，其次填充率高者
        return (1 if c in protected else 0, fill_rates.get(c, 0))

    groups = []
    gid = 0
    for members in buckets.values():
        if len(members) < 2:
            continue
        rep = max(members, key=_rep_key)
        scored = []
        for m in members:
            if m == rep:
                continue
            _, sc = column_relation(df[rep], df[m], profiles[rep], profiles[m])
            scored.append((m, round(sc, 4)))
        groups.append((f"V{gid:04d}", rep, scored))
        gid += 1
    return groups


# ─── 两档字典加载 ────────────────────────────────────────────────────────────
def load_two_part_dict(path=DEFAULT_DICT):
    """返回 (direct_fp, recommend_fp, canonical_names, thresholds)。

    direct_fp     : char_fp(variant) -> canonical
    recommend_fp  : char_fp(variant) -> {canonical, method, score, group_id, freq}
    canonical_names : direct 档所有 canonical（用作数据内部新判定的匹配目标）
    thresholds    : {auto_fusion, recommend_min}
    """
    with open(path, encoding="utf-8") as f:
        d = json.load(f)

    direct = d.get("direct", {})
    recommend = d.get("recommend", {})
    meta = d.get("meta", {})

    direct_fp = {}
    for canonical, variants in direct.items():
        for v in variants:
            key = char_fp(v)
            if key and key not in direct_fp:
                direct_fp[key] = canonical

    recommend_fp = {}
    for canonical, entries in recommend.items():
        for e in entries:
            key = char_fp(e["raw"])
            if not key or key in direct_fp or key in recommend_fp:
                continue  # direct 优先，且同 fp 取首个
            recommend_fp[key] = {
                "canonical": canonical,
                "method": e.get("method", ""),
                "score": e.get("score", ""),
                "group_id": e.get("group_id", ""),
                "freq": e.get("freq", ""),
            }

    canonical_names = sorted(direct.keys())
    raw_auto = meta.get("auto_fusion", None)
    thresholds = {
        "auto_fusion": (float(raw_auto) if raw_auto is not None else None),
        "recommend_min": float(meta.get("recommend_min") or 0.70),
    }
    return direct_fp, recommend_fp, canonical_names, thresholds


# ─── 单元格级合并（与 metadata_downloader 的合并语义一致）─────────────────────
def _merge_series(primary, secondary):
    """按行合并两列：优先非空 primary，其次 secondary，都非空且不同则 'a|b'。"""
    out = []
    for p, s in zip(primary, secondary):
        ps = "" if pd.isna(p) else str(p).strip()
        ss = "" if pd.isna(s) else str(s).strip()
        if ps and ss:
            out.append(ps if ps.lower() == ss.lower() else f"{ps}|{ss}")
        else:
            out.append(ps or ss or None)
    return out


def _merge_into(df, target, source):
    """把 source 列并入 target 列（target 不存在则重命名，存在则单元格合并后删源）。

    target 若与某个已存在列仅大小写不同（如 canonical 'sex' vs 已有 'Sex'），并入那个
    已存在列，避免产生仅大小写不同的重复列；采用 canonical 的大小写（与原版一致）。
    """
    if source not in df.columns or source == target:
        return df
    if target not in df.columns:
        existing = {c.lower(): c for c in df.columns}.get(target.lower())
        if existing and existing != source:
            # 已有仅大小写不同的列：把它改名成 canonical，再并入
            df = df.rename(columns={existing: target}) if existing != target else df
    if target in df.columns:
        df[target] = _merge_series(df[target], df[source])
        df = df.drop(columns=[source])
    else:
        df = df.rename(columns={source: target})
    return df


# ─── 入口 1：应用 direct 直接合并档（取代旧字典硬改名）───────────────────────
def apply_direct(df, dict_path=DEFAULT_DICT, protected=None):
    """把命中 direct 档的列改名/合并到其 canonical。清理后完全相等，自动应用。

    - 列的 char_fp 命中 direct_fp 就统一改名/合并到该 canonical（把 'GeoLocName'、
      'geo loc name' 这类格式变体也归到 'geo_loc_name'，实现跨数据集统一）。
    - `protected` 里的列名（如 MetaDL 核心列 Run/Bioproject/...）绝不改名，避免误伤
      下游依赖的字段（例如 HostTaxonomyId 会被字典映射到 host_taxid）。
    - 列名已精确等于 canonical 的跳过（no-op）。
    - 单元格冲突按 _merge_series 处理；源列被并后删除。
    返回新的 DataFrame。
    """
    if df is None or df.empty:
        return df
    protected = set(protected or ())
    direct_fp, _, _, _ = load_two_part_dict(dict_path)
    df = df.copy()
    n_applied = 0
    for col in list(df.columns):
        if col in protected:
            continue
        canonical = direct_fp.get(char_fp(col))
        if not canonical or col == canonical:
            continue  # 未命中，或已经就是标准名
        before = df.columns.tolist()
        df = _merge_into(df, canonical, col)
        if df.columns.tolist() != before:
            n_applied += 1
    if n_applied:
        print(f"  [standardize] direct 直接合并：应用 {n_applied} 列")
    return df


# ─── 入口 2：生成推荐表 + 可编辑分组模板 ─────────────────────────────────────
def build_recommend_table(df, dict_path=DEFAULT_DICT, out_dir=".", protected=None):
    """扫描 df 列，产出 recommend 候选（不改数据），写推荐表 + 分组模板。

    候选来源（两层，都不改数据、只列表供人审）：
      第一层（字典 recommend）：命中 recommend 档、且目标 canonical 在本表【共现成员 >=2】的列
        才提示；只命中 1 个的先不算（自然落入第二层）。
      第二层（值指纹）：跑在【全部列】上（含第一层未共现的单例、完全未命中列），提名并集
        = 名字词面（共享词 ∪ JW≥阈）∪ 值几乎相同（文本类值集合高重叠），再由 column_relation 值定夺。
    返回 (rec_table_path, groups_file_path)。
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rec_path = out_dir / REC_TABLE_NAME
    groups_path = out_dir / GROUPS_FILE_NAME

    if df is None or df.empty:
        _write_empty(rec_path, groups_path)
        return rec_path, groups_path

    protected = set(protected or ())
    direct_fp, recommend_fp, _canonical_names, _thresholds = load_two_part_dict(dict_path)

    n_rows = max(len(df), 1)
    fill_rates = {c: df[c].notna().sum() / n_rows for c in df.columns}

    # rows: 逐条候选（可读表）
    rows = []
    # 第一层：字典 recommend 命中，按 canonical 归组，先收集 -> 再共现过滤
    dict_hits = defaultdict(list)  # canonical -> [(col, entry)]
    for col in df.columns:
        fp = char_fp(col)
        if fp in direct_fp:
            continue  # direct 由 apply_direct 处理，不进推荐
        if fp in recommend_fp:
            e = recommend_fp[fp]
            if char_fp(e["canonical"]) == fp:
                continue  # 仅大小写/格式差异，非语义合并
            dict_hits[e["canonical"]].append((col, e))
        # 未命中/单例列不单独收集：它们本就在 df.columns 里，第二层会覆盖到

    # 共现规则：目标 canonical 在本表出现的成员数 = 命中它的列数 (+1 若 canonical 本身已是列)
    for canonical, hits in dict_hits.items():
        members_present = len(hits) + (1 if canonical in df.columns else 0)
        if members_present < 2:
            continue  # 只有一个成员，按要求不提示（落入第二层 value_peer）
        for col, e in hits:
            rows.append(dict(
                group_id=f"D:{canonical}", target=canonical, member=col,
                source="dict_recommend", method=e.get("method", ""),
                score=e.get("score", ""), value_sim="", freq=e.get("freq", ""),
                fill_rate=f"{fill_rates[col] * 100:.1f}%",
            ))

    # 第二层：统一成一条「提名并集（名字词面 ∪ 值几乎相同）→ 值定夺」。跑在【全部列】上，
    # 让没靠上字典的列（含 dict recommend 单例、完全未命中列）彼此、以及与表内标准列做值比对，
    # 把 Layout↔LibraryLayout、LatitudeLongitude↔lat_lon、以及名字不沾边但值同的对挖出来。
    # （原 fresh_match「列→字典官方名」一路已删：它无对应列可做值定夺，与本层的“值定夺”原则相悖。）
    for gid, rep, scored in value_aware_peer_groups(
            df, list(df.columns), fill_rates, protected=protected):
        for m, vsim in scored:
            if m == rep:
                continue
            rows.append(dict(
                group_id=gid, target=rep, member=m,
                source="value_peer", method="name_propose_value_decide",
                score="", value_sim=vsim, freq="",
                fill_rate=f"{fill_rates[m] * 100:.1f}%",
            ))

    rec_df = pd.DataFrame(rows, columns=[
        "group_id", "target", "member", "source", "method",
        "score", "value_sim", "freq", "fill_rate"])
    if not rec_df.empty:
        src_order = {"dict_recommend": 0, "value_peer": 1}
        rec_df["_o"] = rec_df["source"].map(src_order).fillna(9)
        rec_df = rec_df.sort_values(["_o", "group_id", "member"]).drop(columns="_o")
        rec_df = rec_df.reset_index(drop=True)
    # 逗号 CSV（非 TSV）：Excel 默认按逗号分列，含逗号的字段 pandas 会自动加引号，
    # 保证每个字段落在独立单元格，不会整行挤进一个格子。utf-8-sig 便于 Excel 识别中文。
    rec_df.to_csv(rec_path, index=False, encoding="utf-8-sig")

    _write_groups_template(rec_df, groups_path)

    n_groups = rec_df["group_id"].nunique() if not rec_df.empty else 0
    print(f"  [standardize] 推荐合并：{n_groups} 组 / {len(rec_df)} 条候选")
    print(f"                推荐表 -> {rec_path.name}")
    print(f"                分组模板 -> {groups_path.name}（编辑后 --apply-merges 落地）")
    return rec_path, groups_path


def _write_groups_template(rec_df, groups_path):
    """把推荐候选写成可编辑的分组模板：每行 `目标/成员1/成员2`。"""
    lines = [GROUPS_HEADER]
    if rec_df is not None and not rec_df.empty:
        for gid, sub in rec_df.groupby("group_id", sort=False):
            target = sub["target"].iloc[0]
            members = [target] + [m for m in sub["member"].tolist() if m != target]
            # 去重保序
            seen, ordered = set(), []
            for m in members:
                k = m.lower().strip()
                if k and k not in seen:
                    seen.add(k)
                    ordered.append(m)
            if len(ordered) >= 2:
                lines.append("/".join(ordered) + "\n")
    with open(groups_path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def _write_empty(rec_path, groups_path):
    pd.DataFrame(columns=[
        "group_id", "target", "member", "source", "method",
        "score", "value_sim", "freq", "fill_rate"]
    ).to_csv(rec_path, index=False, encoding="utf-8-sig")
    with open(groups_path, "w", encoding="utf-8") as f:
        f.write(GROUPS_HEADER)


# ─── 入口 3：按用户分组文件落地合并 ──────────────────────────────────────────
def parse_groups_file(groups_file):
    """解析分组文件。每行 `a/b/c`：首列=目标，其余=并入。返回 [(target, [members...])]。"""
    groups = []
    with open(groups_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split("/") if p.strip()]
            if len(parts) < 2:
                continue
            target, members = parts[0], parts[1:]
            groups.append((target, members))
    return groups


def apply_user_groups(df, groups_file):
    """按用户编辑的分组文件把列合并落地，返回新的 DataFrame。"""
    df = df.copy()
    groups = parse_groups_file(groups_file)
    applied = []
    for target, members in groups:
        for src in members:
            if src not in df.columns or src == target:
                continue
            existed = target in df.columns
            df = _merge_into(df, target, src)
            applied.append((src, target, "merged" if existed else "renamed"))
    if applied:
        preview = ", ".join(f"{a}->{b}" for a, b, _ in applied[:8])
        print(f"  [apply-merges] 应用 {len(applied)} 处：{preview}"
              + (" ..." if len(applied) > 8 else ""))
    else:
        print("  [apply-merges] 分组文件里没有可落地的合并")
    return df
