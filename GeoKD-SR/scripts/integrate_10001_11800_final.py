#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
整合 10001-11800 数据到 balanced_topology.jsonl 并进行审查
修复版本 - 支持从验证报告中获取坐标信息
"""

import json
import os
import re
from datetime import datetime
from collections import Counter, defaultdict
from pathlib import Path
import shutil
import random

# 添加需要导入的模块
try:
    from tqdm import tqdm
except ImportError:
    pass

# 定义常量
DIFFICULTY_SCORE_MAP = {'easy': 1.5, 'medium': 2.75, 'hard': 4.0}
SPATIAL_TYPE_BONUS = {'directional': 1.2, 'topological': 2.2, 'metric': 1.3, 'composite': 3.2}
TOPOLOGY_BONUS = {'within': 0.0, 'contains': 0.1, 'adjacent': 0.3, 'disjoint': 0.4, 'overlap': 0.6}
toPOLOGY_SUBtypes = ['within', 'contains', 'adjacent', 'disjoint', 'overlap']

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
            start = question.find(name)
            end = start + len(name)
            entity_to_token[name] = {
                'char_start': start,
                'char_end': end,
                'token_indices': list(range(start, end + 1))
            }
    return entity_to_token
def clean_spatial_tokens(data):
    """清理spatial_tokens,移除未在question中出现的token"""
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
def step1_fix_fields(source_dir, output_dir):
    """Step 1: 字段修复"""
    print("\n" + "="*60)
    print("Step 1: 字段修复")
    print("="*60)
    all_new_data = []
    stats = {
        'total': 0,
        'fixed': 0,
        'missing_difficulty_score': 0,
        'missing_entity_to_token': 0,
        'missing_split': 0
    }
    for source_file in source_files:
        source_path = source_dir / source_file
        if not source_path.exists():
            print(f"警告: 源文件不存在 - {source_path}")
            continue
        data = read_jsonl(source_path)
        print(f"读取 {source_file}: {len(data)} 条")
        stats['total'] += len(data)
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
            output_path = output_dir / "balanced_topology_v2.jsonl"
            write_jsonl(output_path, all_new_data)
            print(f"保存修复后新数据: {output_path}")
            print(f"重计算difficulty_score: {stats['recalculated_scores']}")
            print(f"清理spatial_tokens: {stats['cleaned_spatial_tokens']}")
            print(f"修复topology_subtype: {stats['fixed_topology_subtype']}")
    return all_new_data, stats
if __name__ == "__main__":
    main()
