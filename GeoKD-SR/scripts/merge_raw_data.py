#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GeoKD-SR 原始数据合并脚本

功能：
1. 读取 hibiki works 目录下所有 generated_*.jsonl 文件
2. 合并为单一文件
3. 按 id 去重
4. 验证格式一致性
5. 输出合并统计信息

使用方法：
    python scripts/merge_raw_data.py --input "C:/Users/60207/Documents/hibiki works/" --output data/geosr_chain/raw_merged.jsonl
"""

import json
import argparse
import os
import glob
from pathlib import Path
from typing import Dict, List, Any, Set
from collections import Counter, defaultdict
from datetime import datetime


def load_jsonl(file_path: str) -> List[Dict[str, Any]]:
    """加载JSONL文件"""
    records = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as e:
                    print(f"  警告: {file_path}:{line_num} JSON解析失败: {e}")
    return records


def save_jsonl(records: List[Dict[str, Any]], output_path: str) -> None:
    """保存为JSONL文件"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')


def get_entity_pair_key(entities: List[Dict]) -> str:
    """获取实体对唯一标识"""
    if not entities or len(entities) < 2:
        return ""
    names = sorted([e.get('name', '') for e in entities[:2]])
    return f"{names[0]}|{names[1]}"


def merge_raw_data(input_dir: str, output_path: str) -> Dict[str, Any]:
    """
    合并原始数据

    Args:
        input_dir: 输入目录路径
        output_path: 输出文件路径

    Returns:
        统计信息字典
    """
    input_path = Path(input_dir)

    # 查找所有generated_*.jsonl文件
    pattern = str(input_path / "generated_*.jsonl")
    files = sorted(glob.glob(pattern))

    if not files:
        print(f"错误: 在 {input_dir} 中未找到 generated_*.jsonl 文件")
        return {}

    print(f"找到 {len(files)} 个文件:")
    for f in files:
        print(f"  - {os.path.basename(f)}")

    # 合并数据
    all_records = []
    file_stats = {}

    for file_path in files:
        print(f"\n读取: {os.path.basename(file_path)}")
        records = load_jsonl(file_path)
        file_stats[os.path.basename(file_path)] = len(records)
        all_records.extend(records)
        print(f"  加载 {len(records)} 条记录")

    print(f"\n总计加载: {len(all_records)} 条记录")

    # 按ID去重
    seen_ids: Set[str] = set()
    unique_records = []
    duplicates = 0

    for record in all_records:
        record_id = record.get('id', '')
        if record_id and record_id not in seen_ids:
            seen_ids.add(record_id)
            unique_records.append(record)
        else:
            duplicates += 1

    print(f"去重后: {len(unique_records)} 条记录 (移除 {duplicates} 条重复)")

    # 统计分布
    spatial_dist = Counter(r.get('spatial_relation_type', 'unknown') for r in unique_records)
    difficulty_dist = Counter(r.get('difficulty', 'unknown') for r in unique_records)
    topology_subtypes = Counter(
        r.get('topology_subtype', 'none')
        for r in unique_records
        if r.get('spatial_relation_type') == 'topological'
    )

    # 统计实体对
    entity_pairs = Counter(get_entity_pair_key(r.get('entities', [])) for r in unique_records)

    # 检查字段完整性
    required_fields = [
        'id', 'spatial_relation_type', 'topology_subtype', 'question', 'answer',
        'reasoning_chain', 'entities', 'spatial_tokens', 'difficulty',
        'difficulty_score', 'prompt_id'
    ]

    field_missing = defaultdict(int)
    for record in unique_records:
        for field in required_fields:
            if field not in record:
                field_missing[field] += 1

    # 检查entities中的坐标
    records_with_coords = 0
    records_without_coords = 0
    for record in unique_records:
        entities = record.get('entities', [])
        has_coords = any('coords' in e and e['coords'] for e in entities)
        if has_coords:
            records_with_coords += 1
        else:
            records_without_coords += 1

    # 保存合并后的数据
    print(f"\n保存到: {output_path}")
    save_jsonl(unique_records, output_path)

    # 生成统计报告
    stats = {
        'total_files': len(files),
        'total_records_loaded': len(all_records),
        'unique_records': len(unique_records),
        'duplicates_removed': duplicates,
        'file_stats': file_stats,
        'spatial_distribution': dict(spatial_dist),
        'difficulty_distribution': dict(difficulty_dist),
        'topology_subtype_distribution': dict(topology_subtypes),
        'unique_entity_pairs': len(entity_pairs),
        'entity_pair_coverage': dict(entity_pairs.most_common(10)),
        'field_missing': dict(field_missing),
        'records_with_coords': records_with_coords,
        'records_without_coords': records_without_coords,
    }

    return stats


def print_stats(stats: Dict[str, Any]) -> None:
    """打印统计信息"""
    print("\n" + "="*60)
    print("合并统计报告")
    print("="*60)

    print(f"\n【基本信息】")
    print(f"  总文件数: {stats.get('total_files', 0)}")
    print(f"  加载记录数: {stats.get('total_records_loaded', 0)}")
    print(f"  去重后记录数: {stats.get('unique_records', 0)}")
    print(f"  移除重复: {stats.get('duplicates_removed', 0)}")

    print(f"\n【空间关系类型分布】")
    for k, v in sorted(stats.get('spatial_distribution', {}).items()):
        pct = v / stats.get('unique_records', 1) * 100
        print(f"  {k}: {v} ({pct:.1f}%)")

    print(f"\n【难度分布】")
    for k, v in sorted(stats.get('difficulty_distribution', {}).items()):
        pct = v / stats.get('unique_records', 1) * 100
        print(f"  {k}: {v} ({pct:.1f}%)")

    print(f"\n【拓扑子类型分布】(仅topological)")
    for k, v in sorted(stats.get('topology_subtype_distribution', {}).items()):
        print(f"  {k}: {v}")

    print(f"\n【实体对统计】")
    print(f"  唯一实体对数: {stats.get('unique_entity_pairs', 0)}")
    print(f"  有坐标记录: {stats.get('records_with_coords', 0)}")
    print(f"  无坐标记录: {stats.get('records_without_coords', 0)}")

    if stats.get('field_missing'):
        print(f"\n【字段缺失】")
        for field, count in stats.get('field_missing', {}).items():
            print(f"  {field}: {count} 条记录缺失")


def main():
    parser = argparse.ArgumentParser(description='GeoKD-SR 原始数据合并脚本')
    parser.add_argument(
        '--input', '-i',
        default='C:/Users/60207/Documents/hibiki works/',
        help='输入目录路径（包含generated_*.jsonl文件）'
    )
    parser.add_argument(
        '--output', '-o',
        default='D:/30_keyan/GeoKD-SR/data/geosr_chain/raw_merged.jsonl',
        help='输出文件路径'
    )
    parser.add_argument(
        '--report',
        default='D:/30_keyan/GeoKD-SR/outputs/merge_report.json',
        help='统计报告输出路径'
    )

    args = parser.parse_args()

    print("="*60)
    print("GeoKD-SR 原始数据合并脚本")
    print("="*60)
    print(f"输入目录: {args.input}")
    print(f"输出文件: {args.output}")

    # 执行合并
    stats = merge_raw_data(args.input, args.output)

    if stats:
        # 打印统计
        print_stats(stats)

        # 保存统计报告
        os.makedirs(os.path.dirname(args.report), exist_ok=True)
        with open(args.report, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        print(f"\n统计报告已保存: {args.report}")

    print("\n合并完成!")
    return 0


if __name__ == '__main__':
    exit(main())
