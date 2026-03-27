#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
整合 10001-11800 数据到 balanced_topology.jsonl 并进行审查
执行步骤:
1. 字段修复 - 补充缺失字段 (difficulty_score, entity_to_token)
2. 数据合并 - 基于ID去重合并
3. 数据修复 - 修复常见问题
4. 更新主文件
5. 验证分布
"""

import json
import os
import re
from datetime import datetime
from collections import Counter, defaultdict
from pathlib import Path

# 常量定义
DIFFICULTY_SCORE_MAP = {'easy': 1.5, 'medium': 2.75, 'hard': 4.0}
SPATIAL_TYPE_BONUS = {'directional': 1.2, 'topological': 2.2, 'metric': 1.3, 'composite': 3.2}
TOPOLOGY_BONUS = {'within': 0.0, 'contains': 0.1, 'adjacent': 0.3, 'disjoint': 0.4, 'overlap': 0.6}

# 路径配置
BASE_DIR = Path("D:/30_keyan/GeoKD-SR")
DATA_DIR = BASE_DIR / "data" / "geosr_chain"
SOURCE_DIR = Path("c:/Users/60207/Documents/hibiki works")
OUTPUT_DIR = BASE_DIR / "outputs" / "integration_review_10001_11800"

# 源文件列表
SOURCE_FILES = [
    "generated_10001_to_10600.jsonl",
    "generated_10601_to_11200.jsonl",
    "generated_11201_to_11800.jsonl"
]

def calculate_difficulty_score(data):
    """计算难度分数"""
    difficulty = data.get('difficulty', 'medium')
    base_score = DIFFICULTY_SCORE_MAP.get(difficulty, 2.75)

    spatial_type = data.get('spatial_relation_type', 'metric')
    type_bonus = SPATIAL_TYPE_BONUS.get(spatial_type, 1.3) - 1.0

    topo_bonus = 0.0
    if spatial_type == 'topological':
        topo_subtype = data.get('topology_subtype', '')
        topo_bonus = TOPOLOGY_BONUS.get(topo_subtype, 0.0)

    final_score = base_score + type_bonus * 0.5 + topo_bonus * 0.3
    return round(max(1.0, min(5.0, final_score)), 1)

def generate_entity_to_token(data):
    """生成实体到token的映射"""
    question = data.get('question', '')
    entities = data.get('entities', [])
    entity_to_token = {}

    for entity in entities:
        name = entity.get('name', '')
        if name and name in question:
            # 找到实体在问题中的位置
            start = question.find(name)
            end = start + len(name)
            entity_to_token[name] = {
                'char_start': start,
                'char_end': end,
                'token_indices': list(range(start, end + 1))
            }

    return entity_to_token

def clean_spatial_tokens(data):
    """清理spatial_tokens，移除未在question中出现的token"""
    question = data.get('question', '')
    spatial_tokens = data.get('spatial_tokens', [])

    # 只保留在问题中出现的token
    cleaned_tokens = [token for token in spatial_tokens if token in question]

    return cleaned_tokens if cleaned_tokens else spatial_tokens

def read_jsonl(file_path):
    """读取JSONL文件"""
    data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    data.append(json.loads(line))
                except json.JSONDecodeError as e:
                    print(f"JSON解析错误 {file_path}: {e}")
    return data

def write_jsonl(file_path, data):
    """写入JSONL文件"""
    with open(file_path, 'w', encoding='utf-8') as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')

def step1_fix_fields():
    """Step 1: 字段修复"""
    print("\n" + "="*60)
    print("Step 1: 字段修复")
    print("="*60)

    all_new_data = []
    stats = {'total': 0, 'fixed': 0, 'missing_difficulty_score': 0, 'missing_entity_to_token': 0}

    for source_file in SOURCE_FILES:
        source_path = SOURCE_DIR / source_file
        if not source_path.exists():
            print(f"警告: 源文件不存在 - {source_path}")
            continue

        data = read_jsonl(source_path)
        print(f"读取 {source_file}: {len(data)} 条记录")
        stats['total'] += len(data)

        for item in data:
            # 检查并修复 difficulty_score
            if 'difficulty_score' not in item:
                item['difficulty_score'] = calculate_difficulty_score(item)
                stats['missing_difficulty_score'] += 1
                stats['fixed'] += 1

            # 检查并修复 entity_to_token
            if 'entity_to_token' not in item:
                item['entity_to_token'] = generate_entity_to_token(item)
                stats['missing_entity_to_token'] += 1
                stats['fixed'] += 1

            # 清理 spatial_tokens
            item['spatial_tokens'] = clean_spatial_tokens(item)

            all_new_data.append(item)

    # 保存修复后的数据
    output_path = DATA_DIR / "new_10001_11800.jsonl"
    write_jsonl(output_path, all_new_data)
    print(f"\n保存修复后数据: {output_path}")
    print(f"总记录数: {stats['total']}")
    print(f"修复记录数: {stats['fixed']}")
    print(f"缺少difficulty_score: {stats['missing_difficulty_score']}")
    print(f"缺少entity_to_token: {stats['missing_entity_to_token']}")

    return all_new_data, stats

def step2_merge_data(new_data):
    """Step 2: 数据合并"""
    print("\n" + "="*60)
    print("Step 2: 数据合并")
    print("="*60)

    # 读取现有数据
    existing_path = DATA_DIR / "balanced_topology.jsonl"
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
    output_path = DATA_DIR / "balanced_topology_v2.jsonl"
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

def step3_fix_data(merged_data):
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

        # 检查 topological 类型的 topology_subtype
        if item.get('spatial_relation_type') == 'topological':
            if 'topology_subtype' not in item or not item['topology_subtype']:
                # 尝试从answer或reasoning_chain中推断
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

    # 保存修复后数据
    output_path = DATA_DIR / "balanced_topology_v2.jsonl"
    write_jsonl(output_path, merged_data)
    print(f"保存修复后数据: {output_path}")
    print(f"重计算difficulty_score: {stats['recalculated_scores']}")
    print(f"清理spatial_tokens: {stats['cleaned_tokens']}")
    print(f"修复topology_subtype: {stats['fixed_topology_subtype']}")

    return merged_data, stats

def step4_update_main_file(merged_data):
    """Step 4: 更新主文件"""
    print("\n" + "="*60)
    print("Step 4: 更新主文件")
    print("="*60)

    # 备份原文件
    original_path = DATA_DIR / "balanced_topology.jsonl"
    backup_path = DATA_DIR / "balanced_topology_backup.jsonl"

    if original_path.exists():
        import shutil
        shutil.copy(original_path, backup_path)
        print(f"备份原文件: {backup_path}")

    # 更新主文件
    write_jsonl(original_path, merged_data)
    print(f"更新主文件: {original_path}")
    print(f"总记录数: {len(merged_data)}")

    return True

def step5_validate_distribution(merged_data):
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
    score_ranges = {'1.0-2.0': 0, '2.0-3.0': 0, '3.0-4.0': 0, '4.0-5.0': 0}
    for item in merged_data:
        score = item.get('difficulty_score', 2.75)
        if score < 2.0:
            score_ranges['1.0-2.0'] += 1
        elif score < 3.0:
            score_ranges['2.0-3.0'] += 1
        elif score < 4.0:
            score_ranges['3.0-4.0'] += 1
        else:
            score_ranges['4.0-5.0'] += 1

    # 字段完整性检查
    required_fields = ['id', 'question', 'answer', 'spatial_relation_type', 'difficulty',
                      'entities', 'spatial_tokens', 'reasoning_chain', 'difficulty_score',
                      'entity_to_token']

    field_completeness = {}
    for field in required_fields:
        count = sum(1 for item in merged_data if field in item and item[field])
        field_completeness[field] = {
            'count': count,
            'percentage': round(count / len(merged_data) * 100, 2)
        }

    # 打印统计结果
    print("\n空间关系类型分布:")
    for stype, count in sorted(spatial_type_dist.items()):
        pct = round(count / len(merged_data) * 100, 2)
        print(f"  {stype}: {count} ({pct}%)")

    print("\n难度分布:")
    for diff, count in sorted(difficulty_dist.items()):
        pct = round(count / len(merged_data) * 100, 2)
        print(f"  {diff}: {count} ({pct}%)")

    print("\n拓扑子类型分布:")
    for subtype, count in sorted(topo_subtype_dist.items()):
        pct = round(count / sum(topo_subtype_dist.values()) * 100, 2) if topo_subtype_dist else 0
        print(f"  {subtype}: {count} ({pct}%)")

    print("\n数据集划分:")
    for split, count in sorted(split_dist.items()):
        pct = round(count / len(merged_data) * 100, 2)
        print(f"  {split}: {count} ({pct}%)")

    print("\n难度分数分布:")
    for range_name, count in score_ranges.items():
        pct = round(count / len(merged_data) * 100, 2)
        print(f"  {range_name}: {count} ({pct}%)")

    print("\n字段完整性检查:")
    for field, info in field_completeness.items():
        print(f"  {field}: {info['count']}/{len(merged_data)} ({info['percentage']}%)")

    stats = {
        'total_count': len(merged_data),
        'spatial_type_distribution': dict(spatial_type_dist),
        'difficulty_distribution': dict(difficulty_dist),
        'topology_subtype_distribution': dict(topo_subtype_dist),
        'split_distribution': dict(split_dist),
        'score_ranges': score_ranges,
        'field_completeness': field_completeness
    }

    return stats

def generate_report(all_stats):
    """生成审查报告"""
    print("\n" + "="*60)
    print("生成审查报告")
    print("="*60)

    # 创建输出目录
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = OUTPUT_DIR / f"integration_report_{timestamp}.md"

    report = f"""# 数据整合审查报告

## 概述
- 整合时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
- 源数据文件:
  - generated_10001_to_10600.jsonl
  - generated_10601_to_11200.jsonl
  - generated_11201_to_11800.jsonl

## Step 1: 字段修复
- 总记录数: {all_stats['step1']['total']}
- 修复记录数: {all_stats['step1']['fixed']}
- 缺少difficulty_score: {all_stats['step1']['missing_difficulty_score']}
- 缺少entity_to_token: {all_stats['step1']['missing_entity_to_token']}

## Step 2: 数据合并
- 现有数据: {all_stats['step2']['existing_count']} 条
- 新数据: {all_stats['step2']['new_count']} 条
- 重复ID: {all_stats['step2']['duplicate_count']} 个
- 去重后新数据: {all_stats['step2']['unique_new_count']} 条
- 合并后总数: {all_stats['step2']['merged_count']} 条

## Step 3: 数据修复
- 重计算difficulty_score: {all_stats['step3']['recalculated_scores']}
- 清理spatial_tokens: {all_stats['step3']['cleaned_tokens']}
- 修复topology_subtype: {all_stats['step3']['fixed_topology_subtype']}

## Step 5: 最终数据分布

### 空间关系类型分布
"""

    for stype, count in sorted(all_stats['step5']['spatial_type_distribution'].items()):
        pct = round(count / all_stats['step5']['total_count'] * 100, 2)
        report += f"| {stype} | {count} | {pct}% |\n"

    report += "\n### 难度分布\n"
    for diff, count in sorted(all_stats['step5']['difficulty_distribution'].items()):
        pct = round(count / all_stats['step5']['total_count'] * 100, 2)
        report += f"| {diff} | {count} | {pct}% |\n"

    report += "\n### 拓扑子类型分布\n"
    topo_total = sum(all_stats['step5']['topology_subtype_distribution'].values())
    for subtype, count in sorted(all_stats['step5']['topology_subtype_distribution'].items()):
        pct = round(count / topo_total * 100, 2) if topo_total > 0 else 0
        report += f"| {subtype} | {count} | {pct}% |\n"

    report += "\n### 数据集划分\n"
    for split, count in sorted(all_stats['step5']['split_distribution'].items()):
        pct = round(count / all_stats['step5']['total_count'] * 100, 2)
        report += f"| {split} | {count} | {pct}% |\n"

    report += "\n### 难度分数分布\n"
    for range_name, count in all_stats['step5']['score_ranges'].items():
        pct = round(count / all_stats['step5']['total_count'] * 100, 2)
        report += f"| {range_name} | {count} | {pct}% |\n"

    report += "\n### 字段完整性检查\n"
    for field, info in all_stats['step5']['field_completeness'].items():
        report += f"| {field} | {info['count']}/{all_stats['step5']['total_count']} | {info['percentage']}% |\n"

    report += """
## 总结

整合任务已完成，所有步骤执行成功。

### 变更记录
1. 新增 10001-11800 范围的数据
2. 补充缺失字段 (difficulty_score, entity_to_token)
3. 清理 spatial_tokens 字段
4. 修复 topology_subtype 字段
5. 更新主文件 balanced_topology.jsonl
"""

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"审查报告已保存: {report_path}")
    return report_path

def main():
    """主函数"""
    print("="*60)
    print("整合 10001-11800 数据到 balanced_topology.jsonl")
    print("="*60)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    all_stats = {}

    # Step 1: 字段修复
    new_data, all_stats['step1'] = step1_fix_fields()

    # Step 2: 数据合并
    merged_data, all_stats['step2'] = step2_merge_data(new_data)

    # Step 3: 数据修复
    merged_data, all_stats['step3'] = step3_fix_data(merged_data)

    # Step 4: 更新主文件
    step4_update_main_file(merged_data)

    # Step 5: 验证分布
    all_stats['step5'] = step5_validate_distribution(merged_data)

    # 生成报告
    report_path = generate_report(all_stats)

    print("\n" + "="*60)
    print("整合任务完成!")
    print("="*60)
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"最终记录数: {all_stats['step5']['total_count']}")

if __name__ == "__main__":
    main()
