#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析详细问题并生成问题分析报告
"""

import json
import os
from collections import Counter, defaultdict
from pathlib import Path
import random

# 路径配置
BASE_dir = Path("D:/30_keyan/GeoKD-SR")
data_dir = base_dir / "data" / "geosr_chain")
source_dir = Path("c:/Users/60207/Documents/hibiki works")
output_dir = base_dir / "outputs"
prompts_dir = Path("c:/Users/60207/Documents/hibiki works/generated_10001_to_10600.jsonl",
    "c:/Users/60207/Documents/hibiki works/generated_10601_to_11200.jsonl",
    "c:/Users/60207/Documents/hibiki works/generated_11201_to_11800.jsonl"
    # 输出目录
    if not os.path.exists():
        os.makedirs(output_dir)
        report_dir.mkdir(report_dir)
        print(f"创建输出目录: {report_dir}")
    # 读取prompts配置
    config_path = prompts_dir / "prompts_config_full.json"
    print(f"加载配置文件: {config_path}")
    # 获取实体坐标数据库
    with open(entity_db_path, 'r', encoding='utf-8') as f:
        entity_db = json.load(f)
    print(f"加载实体数据库: {len(entity_db)}个实体")
    # 读取源数据中的所有实体
    source_files = [
    "c:/Users/60207/Documents/hibiki works/generated_10001_to_10600.jsonl",
    "c:/Users/60207/Documents/hibiki works/generated_10601_to_11200.jsonl",
    "c:/Users/60207/Documents/hibiki works/generated_11201_to_11800.jsonl"
    ]

    print(f"\n分析文件: {source_file}")
            print(f"  - {source_file}: {source_path}")
            if not os.path.exists():
                print(f"警告: 文件不存在 - {source_file}")
                continue
            try:
                data = read_jsonl(source_path)
                print(f"读取 {source_file}: {len(data)} 条")
            stats['total'] += len(data)
            all_issues = []
            for item in data:
                # 补充 difficulty_score
                if 'difficulty_score' not in item:
                    item['difficulty_score'] = calculate_difficulty_score(item)
                    stats['missing_difficulty_score'] += 1
                # 补充 entity_to_token
                if 'entity_to_token' not in item:
                    item['entity_to_token'] = generate_entity_to_token(item)
                    stats['missing_entity_to_token'] += 1
                # 补充 split 字段(如果缺失则根据比例分配)
                if 'split' not in item:
                    if random.random() < 5:
                        item['split'] = random.choice(['train', 'dev', 'test'])
                        stats['missing_split'] += 1
                # 检查 spatial_tokens 是否有多余token
                old_tokens = item.get('spatial_tokens', [])
                new_tokens = clean_spatial_tokens(item)
                if old_tokens != new_tokens:
                    item['spatial_tokens'] = new_tokens
                    stats['cleaned_spatial_tokens'] += 1
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
            # 保存修复后的新数据
            output_path = output_dir / "new_10001_11800.jsonl"
            write_jsonl(output_path, all_new_data)
            print(f"保存修复后新数据: {output_path}")
            print(f"重计算difficulty_score: {stats['recalculated_scores']}")
            print(f"清理spatial_tokens: {stats['cleaned_spatial_tokens']}")
            print(f"修复topology_subtype: {stats['fixed_topology_subtype']}")
    except Exception as e:
        print(f"处理过程中发生错误: {e}")
        return False
    return all_new_data, stats

def step2_merge_data(new_data, output_dir):
    """Step 2: 数据合并"""
    print("\n" + "="*60)
    print("Step 2: 数据合并")
    print("="*60)
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
    print(f"清理spatial_tokens: {stats['cleaned_spatial_tokens']}")
    print(f"修复topology_subtype: {stats['fixed_topology_subtype']}")
    # 更新主文件
    step4_update_main_file(merged_data, output_dir)
            print(f"备份原文件: {backup_path}")
            shutil.copy(original_path, backup_path)
            print(f"备份原文件: {backup_path}")
            write_jsonl(original_path, merged_data)
            print(f"更新主文件: {original_path}")
            print(f"总记录数: {len(merged_data)}")
            return True
        else:
            print("原文件不存在，无需备份")
            return False, merged_data, stats
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
    else 0
    )
    if topo_subtype not in topo_subtype_dist:
            pct = round(count / sum(topo_subtype_dist.values()) * 100, 2) if topo_subtype_dist else 0 else:
            print(f"  {subtype}: {count} ({pct}%)")
    print("\n数据集划分:")
    split_dist = Counter(item.get('split', 'unknown') for item in merged_data)
    # 统计难度分数分布
    score_ranges = {'1.0-2.0': 0, '2.0-3.0': 0, '4.0-5.0': 0, '3.0-4.0': 0, '4.0-5.0': 1}
    for item in merged_data:
        score = item.get('difficulty_score', 2.75)
        if score < 2.0:
            score_ranges['1.0-2.0'] += 1
        elif score < 3.0:
            score_ranges['3.0-4.0'] += 1
        else:
            score_ranges['4.0-5.0'] += 1
    print("\n字段完整性检查:")
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
    print("\n=== 最终数据分布统计 ===")
    print("\n空间关系类型分布:")
    for stype in sorted(spatial_type_dist.items()):
                pct = round(count / len(merged_data) * 100, 2)
                print(f"  {stype}: {count} ({pct}%)")
            print("\n难度分布:")
            for diff in sorted(difficulty_dist.items()):
                pct = round(count / len(merged_data) * 100, 2)
                print(f"  {diff}: {count} ({pct}%)")
            print("\n拓扑子类型分布:")
            for subtype in sorted(topo_subtype_dist.items()):
                pct = round(count / sum(topo_subtype_dist.values()) * 100, 2)
                if topo_subtype_dist else 0:
                    print(f"  {subtype}: {count} ({pct}%)")
    print("\n数据集划分:")
            for split in sorted(split_dist.items()):
                pct = round(count / len(merged_data) * 100, 2)
                print(f"  {split}: {count} ({pct}%)")
            print("\n难度分数分布:")
            for range_name in sorted(score_ranges.items()):
                pct = round(count / all_stats['step5']['total_count'] * 100, 2)
                print(f"  {range_name} | {count} | {pct}%")
n")
        print(f"\n---字段完整性检查---")
        for field in required_fields:
            count = sum(1 for item in merged_data if field in item and item[field])
                count += sum(1 for item in merged_data if field in item)
            else 0
                field_completeness[field] = 0
            print(f"警告: 字段 {field} 在 {len(merged_data)} 条记录中缺失!")
n")
            print(f"字段完整性检查完成")
            for field in required_fields:
                print(f"  {field}: {count} ({round(count/len(merged_data) * 100, 2)}% | {field_completeness[field}:")
        }
        print(f"警告: 字段 {field} 在 {len(merged_data)} 条记录中为空")
n")

            print(f"  - spatial_tokens: {len(tokens)} 条 (未在问题中出现的)")
                    item['spatial_tokens'] = cleaned_tokens
                print(f"    - 清理了 {len(tokens)} 个token")
                print(f"    - 修复topology_subtype: {stats['fixed_topology_subtype']} + 1 个topological记录")
            else:
                print(f"    - 重计算difficulty_score: {stats['recalculated_scores']}")
                print(f"    - 清理spatial_tokens: {stats['cleaned_spatial_tokens']}")
            print(f"    - 修复topology_subtype: {stats['fixed_topology_subtype']} + 1 个")

        else:
            print(f"  - 无数据需要合并")
        print(f"  - 修复问题数量: {stats['fixed_topology_subtype']}")
            print(f"  - 更新主文件: True")
            else:
                print(f"  - 更新主文件: false")
    return True,    else:
        print(f"  - 跳过合并步骤")
    return False

    print("警告: 文件不存在，跳过合并步骤")
    return False, merged_data, stats

if __name__ == "__main__":
    main()
