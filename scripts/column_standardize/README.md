# column_standardize —— MetaDL 列名标准化模块

在 MetaDL 完成下载 + 清洗 + 合并（`all_metadata_merged.csv`）之后，对列名做两档标准化。
**取代**了旧的单档字典硬改名（`docs/NCBI_Biosample.json` + `apply_column_rename_from_dict`）。

## 两档字典

`biosample_canonical_dict.json`（由 `build_two_part_dict.py` 从 biosample_canonical
主字典生成），内部两部分：

- `direct`    高置信，清理后完全相等 —— 命中即**自动合并**。
- `recommend` 中置信，模糊相似 / peer 组 —— **不自动合并**，只进推荐表。

## 运行时行为（不交互）

MetaDL 末尾自动执行（`metadata_downloader.py: merge_all_results`）：

1. `apply_direct(df)` —— direct 命中的列自动改名/合并到 canonical。
2. `build_recommend_table(df, out)` —— 生成推荐候选，不改数据，写两个文件：
   - `merge_recommendations.tsv` —— 可读推荐表（组、成员、来源、分数、填充率、freq）。
   - `merge_groups.txt` —— 可编辑分组模板，每行一组 `目标/成员1/成员2`。

推荐候选有两层来源：
- **第一层（字典）**：`recommend` 档命中，且目标 canonical 在本表**共现成员 ≥2**（都出现才提示）。
- **第二层（数据内部）**：既没命中 direct 也没命中 recommend 的列，彼此/对官方名再推理：
  模糊挂官方名（TF-IDF char n-gram 余弦 + Jaro-Winkler 融合）、token 指纹完全相等、
  JW 模糊且共享词 token。

## 用户落地（一次）

编辑 `merge_groups.txt`，删掉不想合并的行，然后：

```bash
Meta2Data MetaDL --apply-merges merge_groups.txt -o <同一输出目录>
```

输出 `all_metadata_merged.standardized.csv`。

### 分组文件格式

```
# 每行一组要合并的列，用 / 分隔；行首列名是合并后保留的名字，其余并入它。
# 空行 / 以 # 开头的行忽略。
temperature/temp/water_temperature
lat_lon/latitude_longitude/lat_and_lon
```

单元格合并语义：优先非空目标值，其次成员值；两边都非空且不同 -> `a|b`；源列合并后删除。

## 对外入口（可作库导入）

```python
from column_merge import apply_direct, build_recommend_table, apply_user_groups
```

## 重建字典

```bash
python build_two_part_dict.py     # 需要 biosample_canonical 主字典 canonical_dict.json
```
