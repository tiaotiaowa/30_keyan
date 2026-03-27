#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
整合 10001-11800 数据到 balanced_topology.jsonl - 简化版本
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
import shutil

# 路径配置
BASE_DIR = Path("D:/30_keyan/GeoKD-SR")
DATA_dir = base_dir / "data" / "geosr_chain"
source_dir = Path("c:/Users/60207/Documents/hibiki works")
output_dir = base_dir / "outputs" / "integration_review_10001_11800"
    backup_dir = output_dir / "backup"
    if not os.path.exists():
        os.makedirs(backup_dir)
        print(f"创建备份目录: {backup_dir}")
    # 读取并处理源数据
    source_files = [
        "c:/Users/60207/Documents/hibiki works/generated_10001_to_10600.jsonl",
        "c:/Users/60207/Documents/hibiki works/generated_10601_to_11200.jsonl",
        "c:/Users/60207/Documents/hibiki works/generated_11201_to_11800.jsonl"
    ]
    output_path = output_dir / "new_10001_11800.jsonl"
    # Step 2: 数据合并
    print("\nStep 2: 数据合并...")
    # 读取现有数据
    existing_path = data_dir / "balanced_topology.jsonl"
    if not existing_path.exists():
        print(f"错误: 现有数据文件不存在: {existing_path}")
        return
    existing_data = read_jsonl(existing_path)
    print(f"读取现有数据: {len(existing_data)} 条")
    # 基于ID去重
    existing_ids = {item['id'] for item in existing_data}
    new_ids = {item['id'] for item in new_data}
    # 找出重复ID
    duplicate_ids = existing_ids & new_ids
    print(f"重复ID数量: {len(duplicate_ids)}")
    # 只添加不重复的数据
    unique_new_data = [item for item in new_data if item['id'] not in existing_ids]
            print(f"去重后新数据: {len(unique_new_data)} 条")
        # 合并数据
        merged_data = existing_data + unique_new_data
        print(f"合并后总数: {len(merged_data)} 条")
        # 保存合并后数据
        output_path = data_dir / "balanced_topology_v2.jsonl"
        write_jsonl(output_path, merged_data)
        print(f"保存合并后数据: {output_path}")
        stats = {
            'existing_count': len(existing_data),
            'new_count': len(new_data),
            'duplicate_count': len(duplicate_ids),
            'unique_new_count': len(unique_new_data),
            'merged_count': len(merged_data)
        }
    return merged_data, stats
def step3_fix_data(merged_data, output_dir):
    """Step 3: 数据修复"""
    print("\n" + "="*60)
    print("Step 3: 数据修复")
    print("="*60)
    stats = {
        'recalculated_scores': 0,
        'cleaned_tokens': 0,
        'fixed_topology_subtype': 0
    }
    for item in merged_data:
        # 重新计算所有记录的 difficulty_score
        old_score = item.get('difficulty_score')
        new_score = calculate_difficulty_score(item)
        if old_score != new_score:
            item['difficulty_score'] = new_score
            stats['recalculated_scores'] += 1
        # 清理 spatial_tokens
        old_tokens = item.get('spatial_tokens', [])
        new_tokens = clean_spatial_tokens(item)
        if old_tokens != new_tokens:
            item['spatial_tokens'] = new_tokens
            stats['cleaned_tokens'] += 1
        # 检查并修复 topology_subtype
        if item.get('spatial_relation_type') == 'topological':
            if 'topology_subtype' not in item:
                # 尝试从answer中推断
                answer = item.get('answer', '')
                reasoning = item.get('reasoning_chain', [])
                reasoning_text = ' '.join([str(step) for step in reasoning])
                # 简单的关键词匹配
                if '包含' in answer or '位于...内' in answer or 'within' in reasoning_text.lower():
                    item['topology_subtype'] = 'within'
                elif '相离' in answer or '不包含' in answer or 'disjoint' in reasoning_text.lower():
                    item['topology_subtype'] = 'disjoint'
                elif '相邻' in answer or '接壤' in answer or 'adjacent' in reasoning_text.lower():
                    item['topology_subtype'] = 'adjacent'
                elif '重叠' in answer or 'overlap' in reasoning_text.lower():
                    item['topology_subtype'] = 'overlap'
                else:
                    item['topology_subtype'] = 'disjoint'  # 默认值
                stats['fixed_topology_subtype'] += 1
            # 保存修复后的数据
            output_path = output_dir / "balanced_topology_v2.jsonl"
            write_jsonl(output_path, merged_data)
            print(f"保存修复后数据: {output_path}")
            print(f"重计算difficulty_score: {stats['recalculated_scores']}")
            print(f"清理spatial_tokens: {stats['cleaned_tokens']}")
            print(f"修复topology_subtype: {stats['fixed_topology_subtype']}")
    return merged_data, stats
def step4_update_main_file(merged_data, output_dir):
    """Step 4: 更新主文件"""
    print("\n" + "="*60)
    print("Step 4: 更新主文件")
    print("="*60)
    # 备份原文件
    original_path = data_dir / "balanced_topology.jsonl"
    backup_path = data_dir / "balanced_topology_backup.jsonl"
    if not original_path.exists():
        shutil.copy(original_path, backup_path)
        print(f"备份原文件: {backup_path}")
    # 更新主文件
    write_jsonl(original_path, merged_data)
    print(f"更新主文件: {original_path}")
    print(f"总记录数: {len(merged_data)}")
    return True
def step5_validate_distribution(merged_data, output_dir):
    """Step 5: 验证分布"""
    print("\n" + "="*60)
    print("Step 5: 验证分布")
    print("="*60)
    # 统计空间关系类型分布
    spatial_type_dist = Counter(item.get('spatial_relation_type', 'unknown') for item in merged_data)
    # 统计难度分布
    difficulty_dist = Counter(item.get('difficulty', 'unknown') for item in merged_data)
    # 统计拓扑子类型分布
    topo_subtype_dist = Counter(
        item.get('topology_subtype', 'unknown')
        for item in merged_data
        if item.get('spatial_relation_type') == 'topological'
    )
    # 统计数据集划分
    split_dist = Counter(item.get('split', 'unknown') for item in merged_data)
    # 统计难度分数分布
    score_ranges = {'1.0-2.0': 0, '2.0-3.0': 0, '4.0-5.0': 0}
    for item in merged_data:
        score = item.get('difficulty_score', 2.75)
        if score < 2.0:
            score_ranges['1.0-2.0'] += 1
        elif score < 3.0:
            score_ranges['2.0-3.0'] += 1
        elif score < 4.0:
            score_ranges['4.0-5.0'] += 1
        else:
            score_ranges['4.0-5.0'] += 1
    # 字段完整性检查
    required_fields = ['id', 'question', 'answer', 'spatial_relation_type', 'difficulty',
                      'entities', 'spatial_tokens', 'reasoning_chain', 'difficulty_score',
                      'entity_to_token', 'split']
    field_completeness = {}
    for field in required_fields:
        count = sum(1 for item in merged_data if field in item and item[field])
        field_completeness[field] = {
            'count': count
            'percentage': round(count / len(merged_data) * 100, 2)
        }
    return True, merged_data, stats

if __name__ == "__main__":
    main()
