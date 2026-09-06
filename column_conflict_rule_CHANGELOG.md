# 列名冲突规则 · 改动日志 (module1 / MetaDL)

**日期**: 2026-09-07
**范围**: 仅 `scripts/metadata_downloader.py` 的列名归一化（module1 产出结果前）；其它模块、其它函数一律不动。

---

## 一、规则（新增的这条）

当**同一个 canonical 的 ≥2 个同义列在一个数据集里同时出现**时，不再全部改成同一个官方名
（旧代码会造成重复列名或静默跳过），而是**只让一列占用官方列名，其余列保持独立**：

1. **主名优先**：若其中有一列名 == 字典主名（canonical key）→ 它占用官方名；
2. **频次兜底**：若没有任何一列匹配主名 → 取在 NCBI 语料出现频次最高的一列占用官方名
   （频次查 `docs/alias_freq.csv`）；
3. **落败列**：保持原始列名、原样独立保留，不改名、不丢弃、不合并值。

只出现 1 个同义列时 → 照常直接改名（行为不变）。
不在字典里的列 → 原样保留（行为不变）。

---

## 二、改了什么（最小化，全部在 `scripts/metadata_downloader.py`）

1. **新增两个全局**（紧邻 `COLUMN_RENAME_JSON_PATH` 之后）：
   ```python
   COLUMN_FREQ = None
   COLUMN_FREQ_CSV_PATH = Path(__file__).parent.parent / "docs" / "alias_freq.csv"
   ```
2. **新增 `load_column_freq()`**（在 `load_column_rename_dict()` 之后）：读 `docs/alias_freq.csv`
   成 `{char_fp: 频次}`，带全局缓存，失败仅告警不报错。
3. **新增 `_write_merge_log()`**（在 `apply_column_rename_from_dict` 之前）：把每次冲突合并决策
   追加到运行目录的 `column_merge_log.csv`。
4. **重写 `apply_column_rename_from_dict()`**：由"逐列改名（目标已存在就跳过）"改为
   "按 canonical 分组 → 组内选一列占官方名（主名优先→频次兜底）→ 落败列独立"。

**未改动**：`clean_and_standardize_columns`、`apply_camelcase_normalization`、`standardize_columns`
的调用顺序、`merge_all_results`、`PRIORITY_COLUMNS`/`CORE_COLUMNS`、字典文件内容。

## 三、新增文件

- `docs/alias_freq.csv`：`char_fp,freq` 两列，覆盖字典全部别名（1771 条 char_fp，1251 条有频次）。
  由 `Y:\ncbi_corpus\_gen_alias_freq.py` 从 `attribute_name_freq.csv`（语料 attribute_name 频次，
  同 char_fp 取最大不累加）+ 当前字典（987 canonical）生成。
  **注**：日后往字典新增别名时，应同步把该别名的 char_fp+频次补进本文件，否则频次兜底按 0 处理。

## 四、修掉的旧问题

- **重复列名 bug**：旧代码里多列映射到同一未存在的 canonical（如 3 个同义列）→ `df.rename` 生成
  多个同名列。新代码只让一列占名，杜绝重复列。
- **静默跳过**：旧代码"目标列已存在就跳过"，导致同义列不被处理且无记录。新代码显式选胜出列并记 log。

## 五、运行时日志

冲突合并发生时，在**运行目录**追加 `column_merge_log.csv`：
`time, canonical, winner_kept_official_name, reason(main_name/frequency), losers_kept_independent`。

## 六、验证（`Y:\ncbi_corpus\_test_rule.py`）

- `py_compile` 通过。
- 主名优先：`geographic location`+`geo_loc_name`+`country` → 主名占位，其余独立。
- 频次兜底：`country`+`geo_loc_name` → `geo_loc_name`(24M) 占 `geographic location`，`country` 独立。
- 单列改名、非字典列保留：行为不变。
- 四场景均**无重复列**。

## 七、回滚

把 `apply_column_rename_from_dict` 恢复成 4 行 rename 版本、删掉 `load_column_freq`/`_write_merge_log`
/两个全局、删 `docs/alias_freq.csv` 即可。规则与旧行为互斥、无其它耦合。
