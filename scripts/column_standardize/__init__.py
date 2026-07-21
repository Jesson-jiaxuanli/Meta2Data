"""MetaDL 列名标准化模块（两档字典 + 数据内部推理）。

对外入口见 column_merge：apply_direct / build_recommend_table / apply_user_groups。
"""

from .column_merge import (  # noqa: F401
    apply_direct,
    build_recommend_table,
    apply_user_groups,
    parse_groups_file,
    load_two_part_dict,
    DEFAULT_DICT,
    REC_TABLE_NAME,
    GROUPS_FILE_NAME,
)
