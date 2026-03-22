#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
删除 final_1_v6.jsonl 中的多余字段

根据 GeoKD-SR-数据字段标准详解-V1.0.md 规范：
- 必需字段（10个）: id, spatial_relation_type, question, answer, difficulty, difficulty_score, reasoning_chain, entities, spatial_tokens, entity_to_token
- 条件字段（2个）: topology_subtype, split
- 可选字段（1个）: prompt_id

多余字段（需要删除）:
- _validation_errors: 之前校验时添加的调试字段
"""

import json
from pathlib import Path
from collections import Counter
import argparse
from datetime import datetime


# 规范定义的标准字段
STANDARD_FIELDS = {
    # 必需字段（10个）
    'id', 'spatial_relation_type', 'question', 'answer',
    'difficulty', 'difficulty_score', 'reasoning_chain',
    'entities', 'spatial_tokens', 'entity_to_token',
    # 条件字段（2个）
    'topology_subtype',  # 仅topological类型需要
    'split',              # 数据集划分（可选添加）
    # 可选字段（1个）
    'prompt_id'
}

# 明确需要删除的多余字段
FIELDS_TO_REMOVE = {
    '_validation_errors',
    '_fixed',
    '_issues',
    '_errors'
}


def clean_record(record: dict) -> tuple:
    """
    清理单条记录，移除多余字段

    Returns:
        tuple: (清理后的记录, 被移除的字段列表)
    """
    removed_fields = []
    cleaned = {}

    for key, value in record.items():
        if key in FIELDS_TO_REMOVE:
            removed_fields.append(key)
        else:
            cleaned[key] = value

    return cleaned, removed_fields


def clean_dataset(input_file: str, output_file: str) -> dict:
    """
    清理整个数据集

    Returns:
        dict: 统计信息
    """
    stats = {
        'total_records': 0,
        'cleaned_records': 0,
        'records_with_extra_fields': 0,
        'removed_fields_count': Counter(),
        'all_fields': set()
    }

    print(f"开始清理: {input_file}")

    # 读取并清理数据
    with open(input_file, 'r', encoding='utf-8') as f:
        records = []
        for line in f:
            if line.strip():
                record = json.loads(line)
                stats['total_records'] += 1

                # 记录所有字段
                stats['all_fields'].update(record.keys())

                # 清理记录
                cleaned, removed = clean_record(record)
                records.append(cleaned)

                if removed:
                    stats['records_with_extra_fields'] += 1
                    for field in removed:
                        stats['removed_fields_count'][field] += 1

                if (stats['total_records']) % 2000 == 0:
                    print(f"处理进度: {stats['total_records']}")

    # 写入清理后的数据
    print(f"\n写入清理后数据: {output_file}")
    with open(output_file, 'w', encoding='utf-8') as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')

    stats['cleaned_records'] = len(records)

    return stats


def generate_report(stats: dict, input_file: str, output_file: str) -> str:
    """生成清理报告"""
    report = f"""# GeoKD-SR 数据字段清理报告

> **清理时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
> **输入文件**: {input_file}
> **输出文件**: {output_file}

---

## 一、清理统计

| 指标 | 值 |
|------|-----|
| **总记录数** | {stats['total_records']:,} |
| **清理后记录数** | {stats['cleaned_records']:,} |
| **含多余字段的记录** | {stats['records_with_extra_fields']:,} |

---

## 二、移除的字段

| 字段名 | 影响记录数 | 说明 |
|--------|-----------|------|
"""

    for field, count in sorted(stats['removed_fields_count'].items(), key=lambda x: -x[1]):
        report += f"| `{field}` | {count:,} | 非标准字段 |\n"

    if not stats['removed_fields_count']:
        report += "| 无 | 0 | 数据已是标准格式 |\n"

    report += f"""
---

## 三、保留的字段

以下字段符合规范 `GeoKD-SR-数据字段标准详解-V1.0.md`：

| 类型 | 字段 |
|------|------|
| **必需字段** | id, spatial_relation_type, question, answer, difficulty, difficulty_score, reasoning_chain, entities, spatial_tokens, entity_to_token |
| **条件字段** | topology_subtype (仅topological类型) |
| **可选字段** | prompt_id |

---

## 四、数据中实际存在的字段

```
{', '.join(sorted(stats['all_fields'] - FIELDS_TO_REMOVE))}
```

---

*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""

    return report


def main():
    parser = argparse.ArgumentParser(description='删除JSONL文件中的多余字段')
    parser.add_argument('--input', '-i', required=True, help='输入JSONL文件路径')
    parser.add_argument('--output', '-o', default=None, help='输出JSONL文件路径')
    parser.add_argument('--report', '-r', default=None, help='报告输出路径')

    args = parser.parse_args()

    # 设置默认输出路径
    input_path = Path(args.input)
    if args.output is None:
        args.output = str(input_path.parent / f"{input_path.stem}_cleaned.jsonl")
    if args.report is None:
        args.report = str(input_path.parent.parent / 'reports' / f"{input_path.stem}_clean_report.md")

    # 确保输出目录存在
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)

    # 执行清理
    stats = clean_dataset(args.input, args.output)

    # 生成报告
    report = generate_report(stats, args.input, args.output)
    with open(args.report, 'w', encoding='utf-8') as f:
        f.write(report)

    # 打印摘要
    print("\n" + "="*50)
    print("清理完成!")
    print(f"  总记录数: {stats['total_records']:,}")
    print(f"  含多余字段的记录: {stats['records_with_extra_fields']:,}")
    print(f"\n移除的字段:")
    for field, count in stats['removed_fields_count'].items():
        print(f"  - {field}: {count:,} 条")
    print(f"\n输出文件:")
    print(f"  清理后数据: {args.output}")
    print(f"  清理报告: {args.report}")
    print("="*50)


if __name__ == '__main__':
    main()
