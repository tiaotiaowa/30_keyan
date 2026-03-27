#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
坐标增强数据集生成脚本

功能：在question中的地理实体后添加坐标信息
格式：实体名(经度,纬度)

输入：data/final/splits/*.jsonl
输出：data/final/split_coords/*.jsonl
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime

# 添加UTF-8输出支持
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 路径配置
BASE_DIR = Path(__file__).parent.parent
INPUT_DIR = BASE_DIR / 'data' / 'final' / 'splits'
OUTPUT_DIR = BASE_DIR / 'data' / 'final' / 'split_coords'


def enhance_question_with_coords(record):
    """
    在question中的实体后添加坐标信息

    Args:
        record: 单条数据记录

    Returns:
        增强后的记录
    """
    question = record['question']
    entities = record['entities']

    # 按名称长度降序排列，避免部分匹配问题
    # 例如："北京"不会误替换"北京大学"中的"北京"
    sorted_entities = sorted(entities, key=lambda e: len(e['name']), reverse=True)

    for entity in sorted_entities:
        name = entity['name']
        coords = entity['coords']
        # 格式: 实体名(经度,纬度)
        coord_str = f"{name}({coords[0]},{coords[1]})"
        question = question.replace(name, coord_str)

    # 创建新记录（保持其他字段不变）
    new_record = record.copy()
    new_record['question'] = question

    return new_record


def process_file(input_file, output_file):
    """
    处理单个JSONL文件

    Args:
        input_file: 输入文件路径
        output_file: 输出文件路径

    Returns:
        (记录数, 增强实体数)
    """
    count = 0
    entity_count = 0

    with open(input_file, 'r', encoding='utf-8') as f_in:
        with open(output_file, 'w', encoding='utf-8') as f_out:
            for line in f_in:
                if line.strip():
                    record = json.loads(line)
                    enhanced = enhance_question_with_coords(record)
                    f_out.write(json.dumps(enhanced, ensure_ascii=False) + '\n')
                    count += 1
                    entity_count += len(record.get('entities', []))

    return count, entity_count


def main():
    """主函数"""
    print("=" * 60)
    print("坐标增强数据集生成脚本")
    print("=" * 60)

    # 创建输出目录
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 统计信息
    stats = {
        'start_time': datetime.now().isoformat(),
        'files': [],
        'total_records': 0,
        'total_entities': 0
    }

    # 处理三个文件
    splits = ['train', 'dev', 'test']

    for split in splits:
        input_file = INPUT_DIR / f'{split}.jsonl'
        output_file = OUTPUT_DIR / f'{split}.jsonl'

        if not input_file.exists():
            print(f"⚠️  警告: {input_file} 不存在，跳过")
            continue

        print(f"\n处理 {split}...")
        count, entity_count = process_file(input_file, output_file)

        stats['files'].append({
            'split': split,
            'input': str(input_file),
            'output': str(output_file),
            'records': count,
            'entities': entity_count
        })
        stats['total_records'] += count
        stats['total_entities'] += entity_count

        print(f"  ✓ 记录数: {count}")
        print(f"  ✓ 增强实体数: {entity_count}")

    stats['end_time'] = datetime.now().isoformat()

    # 生成报告
    generate_report(stats)

    print("\n" + "=" * 60)
    print("处理完成!")
    print(f"总记录数: {stats['total_records']}")
    print(f"总增强实体数: {stats['total_entities']}")
    print(f"输出目录: {OUTPUT_DIR}")
    print("=" * 60)


def generate_report(stats):
    """生成转换报告"""
    report_file = OUTPUT_DIR / 'transform_report.md'

    report_content = f"""# 坐标增强数据集转换报告

> **生成时间**: {stats['start_time']}
> **完成时间**: {stats['end_time']}

---

## 一、转换概览

| 数据集 | 记录数 | 增强实体数 |
|--------|--------|-----------|
"""

    for file_info in stats['files']:
        report_content += f"| {file_info['split']} | {file_info['records']} | {file_info['entities']} |\n"

    report_content += f"| **总计** | **{stats['total_records']}** | **{stats['total_entities']}** |\n"

    report_content += """
---

## 二、转换规则

### 坐标格式
- 格式: `实体名(经度,纬度)`
- 示例: `北京(116.41,39.90)`

### 替换策略
- 按实体名称长度降序替换，避免部分匹配问题
- 直接使用 `entities[].coords` 字段中的坐标

### 字段处理
| 字段 | 处理方式 |
|------|---------|
| question | **增强** - 在实体后添加坐标 |
| answer | 保持不变 |
| reasoning_chain | 保持不变 |
| entities | 保持不变 |
| 其他字段 | 保持不变 |

---

## 三、转换示例

**原始数据**:
```json
{{
  "question": "渭南市属于陕西省的行政管辖范围之内吗？",
  "entities": [
    {{"name": "陕西省", "coords": [108.9398, 34.3416]}},
    {{"name": "渭南市", "coords": [109.5099, 34.5024]}}
  ]
}}
```

**增强后**:
```json
{{
  "question": "渭南市(109.5099,34.5024)属于陕西省(108.9398,34.3416)的行政管辖范围之内吗？",
  "entities": [
    {{"name": "陕西省", "coords": [108.9398, 34.3416]}},
    {{"name": "渭南市", "coords": [109.5099, 34.5024]}}
  ]
}}
```

---

## 四、文件列表

| 文件 | 路径 |
|------|------|
"""

    for file_info in stats['files']:
        report_content += f"| {file_info['split']}.jsonl | `data/final/split_coords/{file_info['split']}.jsonl` |\n"

    report_content += f"""
---

*报告生成时间: {stats['end_time']}*
"""

    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report_content)

    print(f"\n✓ 报告已生成: {report_file}")


if __name__ == '__main__':
    main()
