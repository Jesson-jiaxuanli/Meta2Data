"""
build_canonical_dict.py — BioSample 属性列名归一化字典构建 v2

三项核心改进（相比 v1）：
  [A] TF-IDF 余弦替代纯 JW 做候选匹配（text2term, baae119）
  [B] 融合分数 = (TF-IDF cosine + JW) / 2（Goncalves et al. 2019, arXiv 1903.08206）
  [C] Jaccard token 过滤：要求 raw_name 与候选 harmonized_name 至少共享一个词
      消除 "collector name → collection_date" 类假阳性（Bilenko et al. 2003, KDD）

输入：
  outputs/layer1_canonical.csv    NCBI 官方 harmonized_name + synonyms
  outputs/layer2_raw_names.csv    全量 raw_name | harmonized_name | freq

输出：
  outputs/canonical_dict.csv      主字典（type 1/2/3/4）
  outputs/canonical_dict.json     结构化 JSON
  outputs/low_confidence_ref.csv  n-gram 低信度聚类（独立参考，不进主字典）

────────────────────────────────────────────────────────────────────────────────
  Type 1  精确命中      自动合并到官方 harmonized_name，无需用户确认
  Type 2  官方名匹配    TF-IDF+JW 融合推荐官方映射，用户选择是否合并
  Type 3  Peer 组合并   Token 指纹相同归为一组，用户选择组内是否合并
  Type 4  完全没命中    只做格式标准化，不建议合并
  LC ref  低信度参考    n-gram 聚类（独立输出，供深度参考）
────────────────────────────────────────────────────────────────────────────────

方法与文献：
  char_fingerprint (Type 1b)  — 标准 record linkage 预处理（Winkler 1990/2006）
  synonym exact match (Type 2a) — MetaMap/NCBO/text2term 均采用的首优先级匹配
  TF-IDF cosine (Type 2b)     — Goncalves et al. 2024 (baae119, Database)
                                 char (2-4)-gram，sklearn TfidfVectorizer
                                 cos(v_s, v_t) = v_s·v_t / (‖v_s‖‖v_t‖)
  Jaro-Winkler (Type 2b)      — Jaro 1989 (JASA 84:414-420)
                                 Winkler 1990 (ASA Survey Research Methods)
                                 JW(s,t)=Jaro+(ℓ·p·(1-Jaro)), ℓ≤4, p=0.1
  Fusion score (Type 2b)      — (TF-IDF cosine + JW) / 2
                                 Goncalves et al. 2019 (arXiv 1903.08206)
  Jaccard token filter (2b)   — J(A,B)=|A∩B|/|A∪B|, 要求 J>0
                                 Bilenko et al. 2003 (KDD), Jaccard 1912
  token fingerprint (Type 3)  — Jaccard set similarity 的特例（frozenset 完全相等）
                                 Rajaraman & Ullman "Mining of Massive Datasets"
  n-gram TF-IDF (LC ref)      — Damashek 1995 (Science 267:843-848)
                                 同 text2term (baae119) 低信度参考步骤

用法：
  python build_canonical_dict.py
  python build_canonical_dict.py --fusion-threshold 0.72 --jaccard-min 0.0
  python build_canonical_dict.py --limit 3000   # 测试用
"""

import argparse
import csv
import json
import re
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
from rapidfuzz.distance import JaroWinkler, Levenshtein
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

OUT_DIR           = Path(__file__).parent / "outputs"
FUSION_THRESHOLD  = 0.70   # (TF-IDF cosine + JW) / 2 阈值（Type 2b 强档，进 recommend）
JACCARD_MIN       = 0.0    # token Jaccard 下限（> 0 即有共享词）
JW_PEER           = 0.88   # JW 匹配 peer 组代表阈值（Type 3）
NGRAM_SIM         = 0.50   # 低信度 n-gram 余弦相似度阈值
TFIDF_BATCH       = 5_000  # 批量向量化大小（控制内存）

# ── 弱档「降级不丢弃」阈值（未过强档的候选不再落 pool，改进 recommend 供人审）──
# 强档条件（fusion≥FUSION_THRESHOLD 且 j>jaccard_min 且 name_ok）一个字不动，DIRECT 集合
# 因此逐条不变；这里只接管原本被丢进 pool 的 else 分支。
WEAK_SHARED_FLOOR   = 0.65  # 有共享词但未过强档 -> recommend（有词佐证，放宽）
WEAK_NOSHARE_FLOOR  = 0.80  # 无共享词（typo/近形）-> recommend，更严
WEAK_NOSHARE_EDITSIM = 0.70  # 无共享词额外门槛：长度归一编辑相似度 1-lev/max_len（收长 token 拼错）
# 关键：无共享词高分里，typo 与真词（latitude vs altitude，词面分数分不开）靠【频次】区分——
# typo 是罕见拼写（数百次），真字段高频（数十万次）。仅低频者才当 typo，避免 latitude->altitude。
TYPO_FREQ_MAX       = 5000  # 无共享词 typo 档的频次上限（真词如 latitude 35万，typo altitute 813）


# ─── 预处理 ───────────────────────────────────────────────────────────────────

def normalize(text: str) -> str:
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()

def char_fp(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())

def token_fp(text: str) -> frozenset:
    return frozenset(normalize(text).split())

def token_jaccard(norm_a: str, norm_b: str) -> float:
    """
    J(A,B) = |A∩B| / |A∪B|  where A,B are word-token sets.
    Ref: Jaccard (1912); Bilenko et al. KDD 2003.
    """
    A = set(norm_a.split())
    B = set(norm_b.split())
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)


GENERIC_DF_MIN = 15   # token 出现在 >=此数个 canonical 里 = 通用词（区分度低）
NAME_KEEP_FUSION = 0.90  # 仅共享通用词时，融合分需 >=此值才保留（错拼/格式变体逃生阀）


def build_generic_tokens(h_norm_list: list[str], df_min: int = GENERIC_DF_MIN) -> set:
    """数据驱动的通用词表：统计每个 token 在多少个 canonical 里出现，
    高频者（type/name/id/date/host/samp…）视为“通用词”，共享它不足以证明同字段。"""
    df: dict[str, int] = defaultdict(int)
    for hn in set(h_norm_list):
        for t in set(hn.split()):
            df[t] += 1
    return {t for t, c in df.items() if c >= df_min}


def distinctive_name_match(a_norm: str, b_norm: str, fusion: float,
                           generic: set) -> bool:
    """判 raw(a) 与候选 canonical(b) 是否“像同一字段”（token 层面）。

    前提：调用处已保证有共享 token（jaccard>0）。规则：
      - 共享了区分性词（非通用词）           -> 接受
      - 一方 token 是另一方子集（特化/缩写）  -> 接受（temp_c_min ⊆ temp）
      - 仅共享通用词，但融合分极高（错拼/格式）-> 接受（host_heght→host_height）
      - 否则（仅共享通用词、且两边各有区分性词）-> 拒绝
        （host **weight**→host_height、submitter **id**→submitted_sample_id）
    """
    A = set(a_norm.split())
    B = set(b_norm.split())
    shared = A & B
    if not shared:
        return True  # 无共享词的情况交给上游 jaccard 过滤，这里不拦
    if shared - generic:
        return True
    if not (A - B) or not (B - A):
        return True
    return fusion >= NAME_KEEP_FUSION


# ─── 加载 Layer 1 ─────────────────────────────────────────────────────────────

def load_layer1(path: Path):
    """
    返回：
      h_list       : [harmonized_name, ...]
      h_norm_list  : [normalize(h), ...]
      cfp_to_h     : char_fp(h) → h           (Type 1b)
      syn_to_h     : normalize(alias) → h      (Type 2a)
    """
    h_list, h_norm_list = [], []
    cfp_to_h: dict[str, str] = {}
    syn_to_h: dict[str, str] = {}

    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            h = row.get("harmonized_name", "").strip()
            if not h:
                continue
            h_norm = normalize(h)
            h_list.append(h)
            h_norm_list.append(h_norm)

            cfp = char_fp(h)
            if cfp and cfp not in cfp_to_h:
                cfp_to_h[cfp] = h

            aliases: set[str] = {h}
            dn = row.get("display_name", "").strip()
            if dn:
                aliases.add(dn)
            for s in row.get("synonyms", "").split("|"):
                if s.strip():
                    aliases.add(s.strip())
            for alias in aliases:
                a_norm = normalize(alias)
                if a_norm and a_norm not in syn_to_h:
                    syn_to_h[a_norm] = h

    return h_list, h_norm_list, cfp_to_h, syn_to_h


# ─── TF-IDF 矩阵 ──────────────────────────────────────────────────────────────

def build_tfidf(h_norm_list: list[str]):
    """
    用官方 harmonized_name 的规范化形式拟合 TF-IDF 向量化器。
    analyzer='char_wb', ngram_range=(2,4), sublinear_tf=True
    Ref: text2term (baae119, Goncalves et al. 2024)
         Damashek 1995 (Science 267:843-848)
    """
    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(2, 4),
        sublinear_tf=True,
    )
    ref_matrix = vectorizer.fit_transform(h_norm_list)
    return vectorizer, ref_matrix   # ref_matrix shape: (n_ref, vocab)


# ─── 批量匹配官方 canonical ───────────────────────────────────────────────────

def match_to_official_batch(
    queries: list[tuple[str, str, int]],  # (raw, norm, freq)
    h_list: list[str],
    h_norm_list: list[str],
    vectorizer: TfidfVectorizer,
    ref_matrix,
    fusion_threshold: float,
    jaccard_min: float,
    generic_tokens: set,
) -> tuple[list[dict], list[tuple[str, str, int]]]:
    """
    批量计算 fusion = (TF-IDF cosine + JW) / 2。
    Ref: Goncalves et al. 2019 arXiv 1903.08206, Definition 1.

    对每个 query：
      1. TF-IDF cosine → 候选 harmonized_name
      2. JW(norm_query, norm_candidate)
      3. fusion = (cosine + jw) / 2
      4. Jaccard(tokens(query), tokens(candidate)) > jaccard_min → 才接受
    返回 (matched, unmatched_pool)
    """
    matched: list[dict] = []
    pool: list[tuple[str, str, int]] = []

    n = len(queries)
    norms = [norm for _, norm, _ in queries]

    # 批量向量化 & 余弦计算
    tfidf_best_score = np.zeros(n, dtype=np.float32)
    tfidf_best_idx   = np.zeros(n, dtype=np.int32)

    for start in range(0, n, TFIDF_BATCH):
        end = min(start + TFIDF_BATCH, n)
        batch_norms  = norms[start:end]
        query_matrix = vectorizer.transform(batch_norms)
        cos_scores   = cosine_similarity(query_matrix, ref_matrix)   # (batch, n_ref)
        tfidf_best_idx[start:end]   = cos_scores.argmax(axis=1)
        tfidf_best_score[start:end] = cos_scores.max(axis=1)

    # 逐条计算 JW + Jaccard + fusion
    for i, (raw, norm, freq) in enumerate(queries):
        if not norm:
            pool.append((raw, norm, freq))
            continue

        best_idx    = int(tfidf_best_idx[i])
        tfidf_score = float(tfidf_best_score[i])
        best_h      = h_list[best_idx]
        best_h_norm = h_norm_list[best_idx]

        jw_score = JaroWinkler.similarity(norm, best_h_norm)

        # fusion score (Goncalves et al. 2019 式)
        fusion = (tfidf_score + jw_score) / 2.0

        # Jaccard token 过滤 (Bilenko et al. 2003, Jaccard 1912)
        j = token_jaccard(norm, best_h_norm)

        # 区分性 token 门槛：砍掉“仅共享通用词、两边各有区分性词”的误匹配
        # （host weight→host_height、submitter id→submitted_sample_id 等）
        name_ok = distinctive_name_match(norm, best_h_norm, fusion, generic_tokens)

        if fusion >= fusion_threshold and j > jaccard_min and name_ok:
            # 强档（不动）：进 Type2 官方匹配（下游默认归 recommend；synonym/Type1 才进 direct）
            matched.append({
                "raw_name": raw, "normalized": norm,
                "type": 2, "method": "tfidf_jw_fusion",
                "suggested_canonical": best_h,
                "tfidf_score": round(tfidf_score, 4),
                "jw_score":    round(jw_score, 4),
                "score":       round(fusion, 4),
                "jaccard":     round(j, 4),
                "group_id": "", "freq": freq,
            })
        else:
            # 弱档「降级不丢弃」：未过强档的候选不再落 pool，改进 recommend 供人审。
            #   有共享词 -> fusion≥0.65；无共享词(typo/近形) -> fusion≥0.80 且 长度归一编辑相似度≥0.70。
            has_shared = j > jaccard_min
            weak_method = None
            if has_shared and fusion >= WEAK_SHARED_FLOOR:
                weak_method = "fuzzy_review"
            elif (not has_shared) and fusion >= WEAK_NOSHARE_FLOOR and freq <= TYPO_FREQ_MAX:
                # 频次上限挡住高频真词（latitude 35万）冒充 typo；typo 本就罕见
                edit_sim = Levenshtein.normalized_similarity(norm, best_h_norm)
                if edit_sim >= WEAK_NOSHARE_EDITSIM:
                    weak_method = "typo"
            if weak_method:
                matched.append({
                    "raw_name": raw, "normalized": norm,
                    "type": 2, "method": weak_method,
                    "suggested_canonical": best_h,
                    "tfidf_score": round(tfidf_score, 4),
                    "jw_score":    round(jw_score, 4),
                    "score":       round(fusion, 4),
                    "jaccard":     round(j, 4),
                    "group_id": "", "freq": freq,
                })
            else:
                pool.append((raw, norm, freq))

    return matched, pool


# ─── n-gram TF-IDF 低信度聚类 ─────────────────────────────────────────────────

def ngram_cluster(
    items: list[tuple[str, str, int]],
    threshold: float,
) -> list[list[int]]:
    """
    Ref: Damashek 1995 (Science 267:843-848)
         text2term (baae119, Goncalves et al. 2024)
    """
    if len(items) < 2:
        return []
    texts = [norm for _, norm, _ in items]
    try:
        tfidf = TfidfVectorizer(
            analyzer="char_wb", ngram_range=(2, 4), min_df=1
        ).fit_transform(texts)
    except ValueError:
        return []

    sim = cosine_similarity(tfidf)
    n   = len(items)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(n):
        for j in range(i + 1, n):
            if sim[i, j] >= threshold:
                pi, pj = find(i), find(j)
                if pi != pj:
                    parent[pi] = pj

    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)
    return [g for g in groups.values() if len(g) >= 2]


# ─── 构建行 dict ──────────────────────────────────────────────────────────────

def make_row(
    raw: str, norm: str, typ: int, method: str,
    canonical: str, score: float, group_id: str, freq: int,
    tfidf_score: float = 0.0, jw_score: float = 0.0, jaccard: float = 0.0,
) -> dict:
    return {
        "raw_name": raw, "normalized": norm, "type": typ,
        "method": method, "suggested_canonical": canonical,
        "score": score, "tfidf_score": tfidf_score,
        "jw_score": jw_score, "jaccard": jaccard,
        "group_id": group_id, "freq": freq,
    }


# ─── 主流程 ───────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="BioSample 属性列名归一化字典构建 v2")
    ap.add_argument("--fusion-threshold", type=float, default=FUSION_THRESHOLD,
                    help=f"Type 2b fusion=(TF-IDF+JW)/2 阈值（默认 {FUSION_THRESHOLD}）")
    ap.add_argument("--jaccard-min",      type=float, default=JACCARD_MIN,
                    help=f"token Jaccard 下限（默认 {JACCARD_MIN}，>0 则要求有共享词）")
    ap.add_argument("--jw-peer",          type=float, default=JW_PEER,
                    help=f"Type 3 JW vs peer 代表阈值（默认 {JW_PEER}）")
    ap.add_argument("--ngram-sim",        type=float, default=NGRAM_SIM,
                    help=f"低信度 n-gram 余弦阈值（默认 {NGRAM_SIM}）")
    ap.add_argument("--limit",            type=int,   default=None,
                    help="只处理前 N 条 longtail（测试用）")
    args = ap.parse_args()

    l1_path = OUT_DIR / "layer1_canonical.csv"
    l2_path = OUT_DIR / "layer2_raw_names.csv"
    for p in (l1_path, l2_path):
        if not p.exists():
            print(f"[错误] {p} 不存在"); return

    print("=" * 64)
    print("  build_canonical_dict.py  v2")
    print(f"  fusion_threshold={args.fusion_threshold}  jaccard_min={args.jaccard_min}")
    print(f"  jw_peer={args.jw_peer}  ngram_sim={args.ngram_sim}")
    print("=" * 64)

    # ── [1] Layer 1 ──────────────────────────────────────────────────────────
    print("\n[1] 加载 layer1_canonical.csv ...")
    h_list, h_norm_list, cfp_to_h, syn_to_h = load_layer1(l1_path)
    generic_tokens = build_generic_tokens(h_norm_list)
    print(f"  harmonized_names : {len(h_list):,}")
    print(f"  char_fp 表       : {len(cfp_to_h):,}")
    print(f"  synonym 表       : {len(syn_to_h):,}")
    print(f"  通用词表(区分度低): {len(generic_tokens):,}")

    # ── [2] 构建 TF-IDF 矩阵 ─────────────────────────────────────────────────
    print("\n[2] 构建 TF-IDF 矩阵（char 2-4 gram，Goncalves 2024）...")
    t0 = time.time()
    vectorizer, ref_matrix = build_tfidf(h_norm_list)
    print(f"  完成 {time.time()-t0:.2f}s  |  vocab={ref_matrix.shape[1]:,}")

    # ── [3] 加载 Layer 2 ─────────────────────────────────────────────────────
    print("\n[3] 加载 layer2_raw_names.csv ...")
    type1a: list[dict] = []
    longtail: list[tuple[str, int]] = []

    with open(l2_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            raw  = row.get("raw_name", "").strip()
            h    = row.get("harmonized_name", "").strip()
            freq = int(row.get("freq", 1) or 1)
            if not raw:
                continue
            if h:
                type1a.append(make_row(raw, normalize(raw), 1, "ncbi_mapped", h, 1.0, "", freq))
            else:
                longtail.append((raw, freq))

    if args.limit:
        longtail = longtail[:args.limit]
        print(f"  (测试模式：前 {args.limit:,} 条)")
    print(f"  Type 1a NCBI mapped   : {len(type1a):,}")
    print(f"  Longtail 待处理       : {len(longtail):,}")

    # ── [4] Type 1b + 2a ─────────────────────────────────────────────────────
    print(f"\n[4] Type 1b (char_fp) + Type 2a (synonym) ...")
    t0 = time.time()

    type1b: list[dict] = []
    type2a: list[dict] = []
    after_1b_2a: list[tuple[str, str, int]] = []   # (raw, norm, freq)

    for raw, freq in longtail:
        norm = normalize(raw)
        cfp  = char_fp(raw)

        if cfp and cfp in cfp_to_h:
            type1b.append(make_row(raw, norm, 1, "char_fingerprint",
                                   cfp_to_h[cfp], 1.0, "", freq))
            continue

        if norm and norm in syn_to_h:
            type2a.append(make_row(raw, norm, 2, "synonym",
                                   syn_to_h[norm], 1.0, "", freq,
                                   tfidf_score=1.0, jw_score=1.0, jaccard=1.0))
            continue

        after_1b_2a.append((raw, norm, freq))

    print(f"  {time.time()-t0:.1f}s  |  1b={len(type1b):,}  2a={len(type2a):,}  "
          f"remaining={len(after_1b_2a):,}")

    # ── [5] Type 2b — TF-IDF+JW 融合匹配 ────────────────────────────────────
    print(f"\n[5] Type 2b — TF-IDF+JW fusion 匹配（{len(after_1b_2a):,} 条）")
    print(f"     改进 [A][B][C]：TF-IDF cosine + JW 融合 + Jaccard 过滤")
    t0 = time.time()

    type2b_matched, pool_after_2b = match_to_official_batch(
        after_1b_2a, h_list, h_norm_list, vectorizer, ref_matrix,
        args.fusion_threshold, args.jaccard_min, generic_tokens,
    )
    print(f"  {time.time()-t0:.1f}s  |  2b 命中={len(type2b_matched):,}  "
          f"pool={len(pool_after_2b):,}")

    # ── [6] Type 3a — token 指纹 peer 聚类 ───────────────────────────────────
    print(f"\n[6] Type 3a — token 指纹 peer 聚类（{len(pool_after_2b):,} 条）")
    fp_map: dict[frozenset, list[tuple[str, str, int]]] = defaultdict(list)
    for raw, norm, freq in pool_after_2b:
        fp_map[token_fp(raw)].append((raw, norm, freq))

    type3a: list[dict] = []
    type4_pool: list[tuple[str, str, int]] = []
    peer_reps: list[tuple[str, str]] = []   # (rep_raw, group_id)
    peer_gid = 0

    for fp, members in fp_map.items():
        members.sort(key=lambda x: -x[2])
        if len(members) >= 2:
            gid_str = f"P{peer_gid:04d}"
            rep_raw = members[0][0]
            peer_reps.append((rep_raw, gid_str))
            for raw, norm, freq in members:
                type3a.append(make_row(raw, norm, 3, "peer_group",
                                       rep_raw, 1.0, gid_str, freq))
            peer_gid += 1
        else:
            raw, norm, freq = members[0]
            type4_pool.append((raw, norm, freq))

    print(f"  peer 组={peer_gid:,}  成员={len(type3a):,}  pool={len(type4_pool):,}")

    # ── [7] Type 3b — JW 匹配 peer 代表 ─────────────────────────────────────
    type3b: list[dict] = []
    type4_final: list[dict] = []

    if peer_reps and type4_pool:
        print(f"\n[7] Type 3b — JW vs peer 代表（{len(type4_pool):,} 条，"
              f"{len(peer_reps)} 代表）")
        from rapidfuzz import process as rf_process
        rep_norms = [normalize(r) for r, _ in peer_reps]
        rep_gids  = [g for _, g in peer_reps]

        t0 = time.time()
        for raw, norm, freq in type4_pool:
            result = rf_process.extractOne(
                norm, rep_norms,
                scorer=JaroWinkler.similarity,
                score_cutoff=args.jw_peer,
            )
            if result:
                _, score, idx = result
                type3b.append(make_row(raw, norm, 3, "jw_peer",
                                       peer_reps[idx][0], round(score, 4),
                                       rep_gids[idx], freq,
                                       jw_score=round(score, 4)))
            else:
                type4_final.append(make_row(raw, norm, 4, "standalone",
                                            "", 0.0, "", freq))
        print(f"  {time.time()-t0:.1f}s  |  3b={len(type3b):,}  type4={len(type4_final):,}")
    else:
        type4_final = [
            make_row(raw, norm, 4, "standalone", "", 0.0, "", freq)
            for raw, norm, freq in type4_pool
        ]

    # ── [8] 低信度参考：n-gram TF-IDF ────────────────────────────────────────
    print(f"\n[8] 低信度参考 — n-gram TF-IDF（{len(type4_final):,} 条）")
    t0 = time.time()
    lc_items  = [(r["raw_name"], r["normalized"], r["freq"]) for r in type4_final]
    lc_groups = ngram_cluster(lc_items, args.ngram_sim)
    print(f"  {time.time()-t0:.1f}s  |  低信度组={len(lc_groups):,}")

    # ── 汇总 ─────────────────────────────────────────────────────────────────
    type1_all = type1a + type1b
    type2_all = type2a + type2b_matched
    type3_all = type3a + type3b
    type4_all = type4_final

    all_rows = sorted(
        type1_all + type2_all + type3_all + type4_all,
        key=lambda r: (r["type"], -r["freq"]),
    )

    print("\n" + "=" * 64)
    print("  汇总")
    print("=" * 64)
    n_tot = len(longtail) if longtail else 1
    def pct(n): return f"{n/n_tot*100:.1f}%"
    print(f"  Type 1  精确命中           : {len(type1_all):>7,}  ({pct(len(type1_all))})")
    print(f"    1a  NCBI ground truth    : {len(type1a):>7,}")
    print(f"    1b  char_fingerprint     : {len(type1b):>7,}")
    print(f"  Type 2  官方名匹配         : {len(type2_all):>7,}  ({pct(len(type2_all))})")
    print(f"    2a  synonym exact        : {len(type2a):>7,}")
    print(f"    2b  TF-IDF+JW fusion     : {len(type2b_matched):>7,}")
    print(f"  Type 3  Peer 组合并        : {len(type3_all):>7,}  ({pct(len(type3_all))})")
    print(f"    3a  token_fp peer        : {len(type3a):>7,}  ({peer_gid} 组)")
    print(f"    3b  jw_peer              : {len(type3b):>7,}")
    print(f"  Type 4  完全没命中         : {len(type4_all):>7,}  ({pct(len(type4_all))})")
    print(f"  低信度参考组               : {len(lc_groups):>7,}")
    print(f"  总计                       : {len(all_rows):>7,}")

    # ── 写 CSV ───────────────────────────────────────────────────────────────
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fields = ["raw_name", "normalized", "type", "method",
              "suggested_canonical", "score", "tfidf_score", "jw_score",
              "jaccard", "group_id", "freq"]

    out_csv = OUT_DIR / "canonical_dict.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(all_rows)
    print(f"\n-> {out_csv}  ({len(all_rows):,} 行)")

    # ── 写 JSON ──────────────────────────────────────────────────────────────
    peer_groups_json: dict[str, dict] = {}
    for r in type3_all:
        gid = r["group_id"]
        if gid not in peer_groups_json:
            peer_groups_json[gid] = {
                "representative": r["suggested_canonical"],
                "members": [], "total_freq": 0,
            }
        peer_groups_json[gid]["members"].append({
            "raw_name": r["raw_name"], "normalized": r["normalized"],
            "method": r["method"], "score": r["score"], "freq": r["freq"],
        })
        peer_groups_json[gid]["total_freq"] += r["freq"]
    peer_groups_json = dict(
        sorted(peer_groups_json.items(), key=lambda x: -x[1]["total_freq"])
    )

    out_json = OUT_DIR / "canonical_dict.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({
            "metadata": {
                "type1_total": len(type1_all),
                "type1a_ncbi": len(type1a),
                "type1b_char_fp": len(type1b),
                "type2_total": len(type2_all),
                "type2a_synonym": len(type2a),
                "type2b_fusion": len(type2b_matched),
                "type3_total": len(type3_all),
                "type3a_peer_groups": peer_gid,
                "type3a_peer_members": len(type3a),
                "type3b_jw_peer": len(type3b),
                "type4_total": len(type4_all),
                "low_conf_groups": len(lc_groups),
                "params": {
                    "fusion_threshold": args.fusion_threshold,
                    "jaccard_min": args.jaccard_min,
                    "jw_peer": args.jw_peer,
                    "ngram_sim": args.ngram_sim,
                },
            },
            "type1": [
                {"raw_name": r["raw_name"], "normalized": r["normalized"],
                 "canonical": r["suggested_canonical"],
                 "method": r["method"], "freq": r["freq"]}
                for r in type1_all
            ],
            "type2_official": [
                {"raw_name": r["raw_name"], "normalized": r["normalized"],
                 "suggested_canonical": r["suggested_canonical"],
                 "method": r["method"],
                 "score": r["score"],
                 "tfidf_score": r.get("tfidf_score", 0.0),
                 "jw_score":    r.get("jw_score", 0.0),
                 "jaccard":     r.get("jaccard", 0.0),
                 "freq": r["freq"]}
                for r in type2_all
            ],
            "type3_peer_groups": peer_groups_json,
            "type4": [
                {"raw_name": r["raw_name"], "normalized": r["normalized"],
                 "freq": r["freq"]}
                for r in type4_all
            ],
        }, f, ensure_ascii=False, indent=2)
    print(f"-> {out_json}")

    # ── 写低信度参考 ──────────────────────────────────────────────────────────
    if lc_groups:
        out_lc = OUT_DIR / "low_confidence_ref.csv"
        lc_fields = ["group_id", "raw_name", "normalized", "freq"]
        with open(out_lc, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=lc_fields)
            w.writeheader()
            for gi, indices in enumerate(
                sorted(lc_groups, key=lambda g: -sum(lc_items[i][2] for i in g))
            ):
                for idx in sorted(indices, key=lambda x: -lc_items[x][2]):
                    raw_lc, norm_lc, freq_lc = lc_items[idx]
                    w.writerow({"group_id": f"LC{gi:04d}",
                                "raw_name": raw_lc, "normalized": norm_lc,
                                "freq": freq_lc})
        lc_total = sum(len(g) for g in lc_groups)
        print(f"-> {out_lc}  ({lc_total} 条，{len(lc_groups)} 组)")

    # ── 示例 ─────────────────────────────────────────────────────────────────
    print("\n── Type 1b char_fp 示例（前 6）─────────────────────────────")
    for r in type1b[:6]:
        print(f"  {r['raw_name']:<40} → {r['suggested_canonical']}")

    print("\n── Type 2b fusion 示例（前 8，按 score 降序）────────────────")
    for r in sorted(type2b_matched, key=lambda x: -x["score"])[:8]:
        print(f"  {r['raw_name']:<38} → {r['suggested_canonical']:<25} "
              f"fusion={r['score']}  tfidf={r['tfidf_score']}  "
              f"jw={r['jw_score']}  J={r['jaccard']}")

    print("\n── Type 2b 低分示例（前 5，可能误匹配，用户需审查）──────────")
    for r in sorted(type2b_matched, key=lambda x: x["score"])[:5]:
        print(f"  {r['raw_name']:<38} → {r['suggested_canonical']:<25} "
              f"fusion={r['score']}  J={r['jaccard']}")

    print("\n── Type 3 peer 组示例（前 5 组）────────────────────────────")
    shown = 0
    for gid_str, g in peer_groups_json.items():
        if shown >= 5: break
        members = [m["raw_name"] for m in g["members"][:4]]
        extra = f" +{len(g['members'])-4}..." if len(g["members"]) > 4 else ""
        print(f"  {gid_str} (freq={g['total_freq']:,}): {members}{extra}")
        shown += 1

    print("\n── Type 4 高频示例（前 6）───────────────────────────────────")
    for r in type4_all[:6]:
        print(f"  freq={r['freq']:>10,}  {r['raw_name']!r}")


if __name__ == "__main__":
    main()
