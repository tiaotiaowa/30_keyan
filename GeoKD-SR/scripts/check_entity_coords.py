#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查并修复实体坐标问题
从entity_database_expanded.json中查找实体坐标并验证新数据
"""

import json
from pathlib import Path

# 加载实体数据库
entity_db_path = Path("D:/30_keyan/GeoKD-SR/data/prompts/entity_database_expanded.json")
with open(entity_db_path, 'r', encoding='utf-8') as f:
    entity_db = json.load(f)

entity_db = json.load(f)

print(f"加载了 {len(entity_db)} 个实体")

# 源文件列表
source_files = [
    "c:/Users/60207/Documents/hibiki works/generated_10001_to_10600.jsonl",
    "c:/Users/60207/Documents/hibiki works/generated_10601_to_11200.jsonl",
    "c:/Users/60207/Documents/hibiki works/generated_11201_to_11800.jsonl"
]

# 检查每个文件
for source_file in source_files:
    print(f"\n检查文件: {source_file}")
    with open(source_file, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                print(f"  行 {line_num}: JSON解析错误")
                continue

            # 检查entities字段
            entities = data.get('entities', [])
            if not entities:
                print(f"  行 {line_num}: 缺少entities字段")
                continue

            # 检查每个实体的坐标
            entity_issues = []
            for entity in entities:
                entity_name = entity.get('name', '')
                coords = entity.get('coords', [])

                # 检查坐标是否有效
                if coords:
                    # 检查是否为(0, 0) 或者有效的坐标格式
                    if coords == [0, 0] or (isinstance(coords, list) and len(coords) == 2 and coords[0] != 0 and coords[1] != 0:
                        entity_issues.append(f"行 {line_num}, 实体 '{entity_name}': 卺标(0,0)坐标")
                    else:
                        # 检查实体是否在数据库中
                    if entity_name in entity_db:
                        db_coords = entity_db[entity_name]
                        if not db_coords or db_coords == [0, 0]:
                            entity_issues.append(f"行 {line_num}, 实体 '{entity_name}': 数据库中坐标也是(0,0)")
                        else:
                            entity_issues.append(f"行 {line_num}, 实体 '{entity_name}': 不在数据库中")
            if entity_issues:
                print(f"  行 {line_num}: 发现 {len(entity_issues)} 个坐标问题:")
                for issue in entity_issues:
                    print(f"    - 实体: {issue['entity_name']}")
                    print(f"    - 壨标: {issue['coords']}")
                    print(f"    - 在数据库中: {issue['in_db']}")

if __name__ == "__main__":
    main()
