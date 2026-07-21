"""
build_two_part_dict.py — 从 v2 主字典 canonical_dict.json 生成【两档】同义词字典

产出一个字典文件，内部分成两部分：

  direct     （直接合并档，高置信，默认自动应用）
    - type1                          精确 / 字符指纹命中官方 harmonized_name
    - type2_official  method=synonym 官方同义词精确命中
    （direct 只收"清理后完全相等"的项，不含模糊相似度）

  recommend  （推荐合并档，中置信，需用户逐条确认）
    - type2_official  fusion >= recommend_min  TF-IDF+JW 融合（模糊相似，一律逐条确认）
    - type3_peer_groups                        token/JW peer 聚类（代表名作 canonical）

  （type4 standalone 不进字典，只做格式标准化）

输出格式（一个 JSON 文件，两个部分）：

  {
    "meta":   { ...统计与阈值... },
    "direct": { "<canonical>": ["<canonical>", "<variant1>", ...], ... },
    "recommend": {
        "<canonical>": [
          {"raw": "...", "method": "tfidf_jw_fusion|peer_group|jw_peer",
           "score": 0.78, "group_id": "P0007", "freq": 123},
          ...
        ], ...
    }
  }

用法：
  python build_two_part_dict.py
  python build_two_part_dict.py --auto-fusion 0.85 --recommend-min 0.70 --dry-run
"""

import argparse
import json
import re
from pathlib import Path

SRC_JSON = Path(__file__).parent / "outputs" / "canonical_dict.json"
# 写在本 v2 目录 outputs 下，供同目录的 column_standardizer.py 读取
OUT_JSON = Path(__file__).parent / "outputs" / "biosample_canonical_dict.json"
# 官方属性表：harmonized_name -> display_name。canonical 用 display_name（原版
# Meta2Data 的自然语言命名），camelcase 后即原版列名格式（geo_loc_name ->
# "geographic location" -> GeographicLocation）。无 display_name 时回退 harmonized。
L1_CSV = Path(__file__).parent / "outputs" / "layer1_canonical.csv"

AUTO_FUSION = None    # fusion>=此分进 direct；None=全部进 recommend（fusion 为模糊相似，非"清理后相等"）
RECOMMEND_MIN = 0.70  # recommend 融合分下限


def load_display_map(path: Path) -> dict:
    """harmonized_name -> display_name（原版 Meta2Data 用的自然语言列名）。

    canonical 改用 display_name，末端 apply_camelcase_normalization 会把它转成原版
    的 CamelCase 列名。缺 display_name 的回退为 harmonized 本身（由调用方处理）。
    """
    import csv as _csv
    m: dict[str, str] = {}
    if not path.exists():
        print(f"[警告] {path} 不存在，canonical 将回退为 harmonized_name（snake）")
        return m
    with open(path, encoding="utf-8") as f:
        for row in _csv.DictReader(f):
            h = (row.get("harmonized_name") or "").strip()
            dn = (row.get("display_name") or "").strip()
            if h and dn:
                m[h] = dn
    return m


def is_too_short(raw: str) -> bool:
    """normalize 后 <=3 字符且无空格的极短词（g、otu 等），跳过避免误命中。"""
    norm = re.sub(r"[^a-z0-9]+", " ", raw.lower()).strip()
    return len(norm) <= 3 and " " not in norm


def add_direct(direct, seen, canonical, raw):
    """把 raw 作为 canonical 的一个变体加入 direct（大小写去重，canonical 自身作首元素）。"""
    if canonical not in direct:
        direct[canonical] = [canonical]
        seen[canonical] = {canonical.lower().strip()}
    key = raw.lower().strip()
    if key and key not in seen[canonical]:
        direct[canonical].append(raw)
        seen[canonical].add(key)
        return True
    return False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--auto-fusion", type=float, default=AUTO_FUSION,
                    help="fusion>=此分数才进 direct 直接合并（逃生阀，默认关闭）；"
                         "默认不设，fusion 全部进 recommend 逐条确认")
    ap.add_argument("--recommend-min", type=float, default=RECOMMEND_MIN,
                    help=f"recommend 融合分下限（默认 {RECOMMEND_MIN}）")
    ap.add_argument("--out", type=Path, default=OUT_JSON, help="输出路径")
    ap.add_argument("--dry-run", action="store_true", help="只打印统计，不写文件")
    args = ap.parse_args()

    if not SRC_JSON.exists():
        print(f"[错误] {SRC_JSON} 不存在，请先运行 build_canonical_dict.py")
        return

    with open(SRC_JSON, encoding="utf-8") as f:
        d = json.load(f)

    disp_map = load_display_map(L1_CSV)

    def to_display(h: str) -> str:
        """harmonized -> display_name（原版格式）；缺失回退 harmonized。"""
        return disp_map.get(h, h)

    direct: dict[str, list[str]] = {}
    seen: dict[str, set[str]] = {}
    recommend: dict[str, list[dict]] = {}

    n_type1 = n_syn = n_fusion_direct = n_skip_short = 0
    n_fusion_rec = n_peer_rows = n_peer_groups = 0

    # ── direct: Type 1（精确 / 字符指纹）─────────────────────────────────────
    for r in d.get("type1", []):
        raw = r["raw_name"].strip()
        harmonized = r["canonical"].strip()
        if not raw or not harmonized:
            continue
        canonical = to_display(harmonized)
        # 保留 harmonized(snake) 也作为变体，使字面为 snake 的列仍能命中
        if canonical != harmonized:
            add_direct(direct, seen, canonical, harmonized)
        if add_direct(direct, seen, canonical, raw):
            n_type1 += 1

    # ── Type 2 官方名匹配：synonym / fusion 分档 ──────────────────────────────
    for r in d.get("type2_official", []):
        raw = r["raw_name"].strip()
        harmonized = r["suggested_canonical"].strip()
        method = r["method"]
        score = float(r.get("score", 0.0))
        if not raw or not harmonized:
            continue
        canonical = to_display(harmonized)

        if method == "synonym":
            if is_too_short(raw):
                n_skip_short += 1
                continue
            if canonical != harmonized:
                add_direct(direct, seen, canonical, harmonized)
            if add_direct(direct, seen, canonical, raw):
                n_syn += 1

        elif method == "tfidf_jw_fusion":
            if is_too_short(raw):
                n_skip_short += 1
                continue
            # fusion 是 (TF-IDF+JW)/2 模糊相似度，非"清理后相等"，默认一律进 recommend。
            # 仅当显式指定 --auto-fusion 阈值时，高分才进 direct（逃生阀）。
            if args.auto_fusion is not None and score >= args.auto_fusion:
                if canonical != harmonized:
                    add_direct(direct, seen, canonical, harmonized)
                if add_direct(direct, seen, canonical, raw):
                    n_fusion_direct += 1
            elif score >= args.recommend_min:
                recommend.setdefault(canonical, []).append({
                    "raw": raw, "method": "tfidf_jw_fusion",
                    "score": round(score, 4), "group_id": "",
                    "freq": int(r.get("freq", 0) or 0),
                })
                n_fusion_rec += 1

        elif method in ("fuzzy_review", "typo"):
            # 弱档「降级不丢弃」：build_canonical_dict 已按 0.65/0.80 floor 筛过，
            # 一律进 recommend（绝不进 direct），由运行时值定夺 + 人审。
            if is_too_short(raw):
                n_skip_short += 1
                continue
            recommend.setdefault(canonical, []).append({
                "raw": raw, "method": method,
                "score": round(score, 4), "group_id": "",
                "freq": int(r.get("freq", 0) or 0),
            })
            n_fusion_rec += 1

    # ── recommend: Type 3 peer 组（代表名作 canonical，同组 group_id 一致）────
    for gid, g in d.get("type3_peer_groups", {}).items():
        rep = (g.get("representative") or "").strip()
        members = g.get("members", [])
        if not rep or len(members) < 2:
            continue
        rep = to_display(rep)  # representative 若为 harmonized 也换成 display（原版格式）
        n_peer_groups += 1
        bucket = recommend.setdefault(rep, [])
        for m in members:
            raw = (m.get("raw_name") or "").strip()
            if not raw or raw.lower().strip() == rep.lower().strip():
                continue  # 代表自身不作为变体条目
            bucket.append({
                "raw": raw, "method": m.get("method", "peer_group"),
                "score": round(float(m.get("score", 0.0)), 4),
                "group_id": gid, "freq": int(m.get("freq", 0) or 0),
            })
            n_peer_rows += 1

    # 去掉 recommend 中已被 direct 收录的变体（direct 优先）
    direct_keys = {v.lower().strip() for vs in direct.values() for v in vs}
    for canonical in list(recommend):
        kept = [e for e in recommend[canonical]
                if e["raw"].lower().strip() not in direct_keys]
        if kept:
            recommend[canonical] = kept
        else:
            del recommend[canonical]

    n_direct_keys = len(direct)
    n_direct_variants = sum(len(v) for v in direct.values())
    n_rec_keys = len(recommend)
    n_rec_variants = sum(len(v) for v in recommend.values())

    out = {
        "meta": {
            "source": str(SRC_JSON),
            "canonical_naming": "display_name",  # 原版 Meta2Data 自然语言名（camelcase 后=原版列名）
            "display_map_size": len(disp_map),
            "auto_fusion": args.auto_fusion,
            "recommend_min": args.recommend_min,
            "direct_type1": n_type1,
            "direct_synonym": n_syn,
            "direct_fusion": n_fusion_direct,
            "direct_keys": n_direct_keys,
            "direct_variants": n_direct_variants,
            "recommend_fusion_mid": n_fusion_rec,
            "recommend_peer_groups": n_peer_groups,
            "recommend_peer_rows": n_peer_rows,
            "recommend_keys": n_rec_keys,
            "recommend_variants": n_rec_variants,
            "skipped_short": n_skip_short,
        },
        "direct": direct,
        "recommend": recommend,
    }

    print("=" * 64)
    print("  build_two_part_dict.py")
    print("=" * 64)
    print("  [direct 直接合并档]")
    print(f"    Type1 精确/指纹      : {n_type1:>7,}")
    print(f"    Type2 synonym        : {n_syn:>7,}")
    if n_fusion_direct:
        print(f"    Type2 fusion>={args.auto_fusion} : {n_fusion_direct:>7,}  (--auto-fusion 逃生阀)")
    print(f"    canonical 键         : {n_direct_keys:>7,}")
    print(f"    变体总数             : {n_direct_variants:>7,}")
    print("  [recommend 推荐合并档]")
    print(f"    Type2 fusion>={args.recommend_min}    : {n_fusion_rec:>7,}")
    print(f"    Type3 peer 组        : {n_peer_groups:>7,} 组（{n_peer_rows:,} 条）")
    print(f"    canonical 键         : {n_rec_keys:>7,}")
    print(f"    变体总数             : {n_rec_variants:>7,}")
    print(f"  极短词跳过             : {n_skip_short:>7,}")

    if args.dry_run:
        print("\n[dry-run] 未写文件")
        return

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n[写出] -> {args.out}")


if __name__ == "__main__":
    main()
