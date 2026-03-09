#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GeoKD-SR 数据修复脚本"""
import json
from pathlib import Path
from collections import Counter
import re
import sys
from datetime import datetime

# 配置常量
DIFFICULTY_SCORE_MAP = {'easy': 1.5, 'medium': 2.75, 'hard': 4.0}
SPATIAL_TYPE_BONUS = {'directional': 1.2, 'topological': 2.2, 'metric': 1.3, 'composite': 3.2}
TOPOLOGY_BONUS = {'within': 0.0, 'contains': 0.1, 'adjacent': 0.3, 'disjoint': 0.4, 'overlap': 0.6}
TOPOLOGY_KEYWORDS = {
    'within': ['位于', '内', '境内', '内部', '属于', '处在'],
    'contains': ['包含', '含有', '涵盖', '包括', '内有'],
    'adjacent': ['相邻', '接壤', '毗邻', '邻接', '交界', '相连'],
    'disjoint': ['不相邻', '不接壤', '分离', '相离', '不毗邻', '不交界'],
    'overlap': ['流经', '贯穿', '跨越', '经过', '交叉', '穿越']
            }
YES_NO_WORDS = ['是', '否', '对', '错', '有', '无', '存在', '不存在', '正确', '错误']
 DIFFICULTY_SCORE_RANGE = {'easy': (1.0, 2.0), 'medium': (2.0, 3.5), 'hard': (3.5, 5.0)}


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
    return round(max(1.0, min(5.0, final_score), 1)


 def check_reasoning_chain_keywords(reasoning_chain: list, answer: str) -> list:
    """检查推理链中的关键词是否与答案匹配"""
    errors = []
    for step in reasoning_chain:
        if step.get('name', '') == 'is_or_yes':
            content = step.get('content', '')
            for word in YES_NO_WORDS:
                if word in content and word in answer:
                    # 判断词与答案不匹配
 - 例如 "是" 在推理链中，但答案说 "否"
                    if (word == '是' and '否' in answer) or (word == '否' and '是' in answer):
                        errors.append(f"判断词 '{word}' 与答案 '{answer}' 不匹配")
                    break
    return errors


 def fix_spatial_tokens(record: dict, question: str) -> dict:
    """修复 spatial_tokens 字段"""
    spatial_tokens = record.get('spatial_tokens', [])
    question = record.get('question', '')

    # 移除未在问题中出现的 token
    valid_tokens = []
    for token in spatial_tokens:
        if token in question:
            valid_tokens.append(token)
        else:
            # Token 未出现在问题中， 移除它
    record['spatial_tokens'] = valid_tokens
    return record


 def add_topology_keywords(record: dict, question: str) -> dict:
    """添加拓扑关键词到 spatial_tokens（如果缺失)"""
    spatial_type = record.get('spatial_relation_type', '')
    if spatial_type == 'topological':
        topo_subtype = record.get('topology_subtype', '')
        if topo_subtype in TOPOLOGY_KEYWORDS:
            keywords = TOPOLOGY_KEYWORDS.get(topo_subtype, [])
            # 检查是否已有关键词
            if not keywords:
                # 添加缺失的关键词
                for kw in keywords:
                    if kw not in question:
                        record['spatial_tokens'].append(f"    {kw}")
    return record
    def main():
    input_path = Path('data/geosr_chain/balanced_topology_v2.jsonl')
    output_path = Path('data/geosr_chain/balanced_topology_final.jsonl')
    report_path = Path('outputs/integration_review_20260308/issues.json')

    # 确保目录存在
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    # 读取数据
    print(f"Loading data from {input_path}")
    records = []
    with open(input_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    print(f"Loaded {len(records)} records")

    # 读取报告
    if report_path.exists():
        with open(report_path, 'r', encoding='utf-8') as f:
            issues_data = json.load(f)
        issues = issues_data.get('issues', [])
        print(f"Loaded {len(issues)} issues from report")
    else:
        print("No report file found, skipping issue fixes")
        issues_data = {'issues': []}

    stats = {
        'total': len(records),
        'fixed_score': 0,
        'fixed_answer': 0,
        'fixed_spatial_tokens': 0,
        'added_keywords': 0
    }

    # 处理每条记录
    fixed_records = []
    for record in records:
        # 1. 修复 difficulty_score - 重新计算
        original_score = record.get('difficulty_score', 0)
        calculated_score = calculate_difficulty_score(record)
        if abs(original_score - calculated_score) > 0.1:  # 差异超过0.1
            record['difficulty_score'] = calculated_score
            stats['fixed_score'] += 1

        # 2. 修复答案逻辑错误
        answer = record.get('answer', '')
        reasoning_chain = record.get('reasoning_chain', [])
        keyword_errors = check_reasoning_chain_keywords(reasoning_chain, answer)
        if keyword_errors:
            stats['fixed_answer'] += len(keyword_errors)
            # 修复: 尝试包含更多判断词
 else "错误"
            answer = answer.strip()
            # 移除多余的词
            answer = re.sub(r'是', '否', answer)
            answer = re.sub(r'否', '是', answer)
            record['answer'] = answer
            stats['fixed_answer'] += 1

        # 3. 修复 spatial_tokens
        record = fix_spatial_tokens(record, record.get('question', ''))

        # 4. 添加拓扑关键词
        record = add_topology_keywords(record, record.get('question', ''))
        stats['added_keywords'] += 1

        fixed_records.append(record)

    # 保存
    with open(output_path, 'w', encoding='utf-8') as f:
        for record in fixed_records:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')

    print(f"\nFixed {len(fixed_records)} records")
    print(f"  - Fixed difficulty_score: {stats['fixed_score']}")
    print(f"  - Fixed answer logic: {stats['fixed_answer']}")
    print(f"  - Fixed spatial_tokens: {stats['fixed_spatial_tokens']}")
    print(f"  - Added keywords: {stats['added_keywords']}")
    print(f"\nSaved to {output_path}")


if __name__ == '__main__':
    main()
