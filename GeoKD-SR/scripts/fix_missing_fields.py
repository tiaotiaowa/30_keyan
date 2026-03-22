#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
修复 final_1.jsonl 中缺失的 entity_to_token 和 difficulty_score 字段

根据 GeoKD-SR V2.1 数据生成规范：
1. entity_to_token: 从 question 中定位实体位置，生成字符和token映射
2. difficulty_score: 根据 spatial_type, topology_subtype, entity_types 计算
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def calculate_entity_to_token(question: str, entities: List[Dict]) -> Dict:
    """
    从 question 中定位实体位置，生成 entity_to_token 映射

    Args:
        question: 问题文本
        entities: 实体列表 [{"name": "北京", "type": "city", "coords": [...]}, ...]

    Returns:
        entity_to_token 映射 {"实体名": {"char_start": int, "char_end": int, "token_indices": [int, ...]}}
    """
    entity_to_token = {}

    for entity in entities:
        entity_name = entity.get("name", "")
        if not entity_name:
            continue

        # 在 question 中查找实体位置
        char_start = question.find(entity_name)
        if char_start == -1:
            # 尝试模糊匹配（可能实体名有微小差异）
            # 例如："北京市" vs "北京"
            for i in range(len(entity_name), 0, -1):
                partial = entity_name[:i]
                if partial in question:
                    char_start = question.find(partial)
                    char_end = char_start + len(partial)
                    break
            else:
                # 如果还是找不到，跳过该实体
                continue
        else:
            char_end = char_start + len(entity_name)

        # 生成 token_indices (简单实现：每个字符对应一个 token index)
        # 实际 tokenizer 可能不同，这里使用简化版本
        token_indices = list(range(char_start, char_end))

        entity_to_token[entity_name] = {
            "char_start": char_start,
            "char_end": char_end,
            "token_indices": token_indices
        }

    return entity_to_token


def calculate_difficulty_score(
    spatial_type: str,
    topology_subtype: Optional[str] = None,
    entity_types: Optional[List[str]] = None,
    entity_count: int = 2
) -> float:
    """
    根据规范 V2.0 计算难度分数

    Args:
        spatial_type: 空间关系类型 (directional/topological/metric/composite)
        topology_subtype: 拓扑子类型 (仅 topological 需要)
        entity_types: 实体类型列表
        entity_count: 实体数量

    Returns:
        难度分数 (1.0-5.0)
    """
    # 基础分 (V2.0)
    base_scores = {
        "directional": 1.2,
        "topological": 2.2,
        "metric": 1.3,
        "composite": 3.2
    }

    # 拓扑子类型加成
    topology_bonus = {
        "within": 0.0,
        "contains": 0.1,
        "adjacent": 0.3,
        "disjoint": 0.4,
        "overlap": 0.6
    }

    # 实体类型对加成
    entity_bonus = {
        ("city", "city"): 0.0,
        ("city", "landmark"): 0.2,
        ("province", "city"): 0.4,
        ("river", "city"): 0.7,
        ("mountain", "city"): 0.7,
        ("region", "city"): 0.9
    }

    # 获取基础分
    score = base_scores.get(spatial_type, 2.0)

    # 拓扑子类型加成
    if topology_subtype and topology_subtype in topology_bonus:
        score += topology_bonus[topology_subtype]

    # 实体类型加成
    if entity_types and len(entity_types) >= 2:
        # 排序后匹配
        sorted_types = tuple(sorted(entity_types[:2]))
        score += entity_bonus.get(sorted_types, 0.5)
    elif entity_types:
        score += 0.5

    # 实体数量加成
    entity_count_bonus = max(0, (entity_count - 2) * 0.3)
    score += entity_count_bonus

    # 限制在 1.0-5.0 范围内
    return round(min(max(score, 1.0), 5.0), 2)


def fix_record(record: Dict) -> Dict:
    """
    修复单条记录的缺失字段

    Args:
        record: 原始记录

    Returns:
        修复后的记录
    """
    fixed = record.copy()

    # 1. 修复 entity_to_token
    if "entity_to_token" not in fixed or not fixed.get("entity_to_token"):
        question = fixed.get("question", "")
        entities = fixed.get("entities", [])

        if question and entities:
            fixed["entity_to_token"] = calculate_entity_to_token(question, entities)

    # 2. 修复 difficulty_score
    if "difficulty_score" not in fixed or fixed.get("difficulty_score") is None:
        spatial_type = fixed.get("spatial_relation_type", "")
        topology_subtype = fixed.get("topology_subtype")
        entities = fixed.get("entities", [])
        entity_types = [e.get("type", "") for e in entities if e.get("type")]
        entity_count = len(entities)

        fixed["difficulty_score"] = calculate_difficulty_score(
            spatial_type=spatial_type,
            topology_subtype=topology_subtype,
            entity_types=entity_types,
            entity_count=entity_count
        )

    return fixed


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="修复数据集中的缺失字段")
    parser.add_argument("--input", "-i", required=True, help="输入文件路径")
    parser.add_argument("--output", "-o", required=True, help="输出文件路径")
    parser.add_argument("--dry-run", action="store_true", help="仅统计，不输出文件")

    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"错误: 输入文件不存在: {input_path}")
        return

    # 读取数据
    records = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    total = len(records)
    print(f"总记录数: {total}")

    # 统计缺失情况
    missing_entity_to_token = 0
    missing_difficulty_score = 0

    for record in records:
        if "entity_to_token" not in record or not record.get("entity_to_token"):
            missing_entity_to_token += 1
        if "difficulty_score" not in record or record.get("difficulty_score") is None:
            missing_difficulty_score += 1

    print(f"缺失 entity_to_token: {missing_entity_to_token} ({missing_entity_to_token/total*100:.2f}%)")
    print(f"缺失 difficulty_score: {missing_difficulty_score} ({missing_difficulty_score/total*100:.2f}%)")

    if args.dry_run:
        print("\n[dry-run 模式] 不输出文件")
        return

    # 修复记录
    fixed_records = []
    for record in records:
        fixed_records.append(fix_record(record))

    # 确保输出目录存在
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 写入输出文件
    with open(output_path, "w", encoding="utf-8") as f:
        for record in fixed_records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"\n修复完成，输出文件: {output_path}")

    # 验证修复结果
    fixed_missing_entity_to_token = 0
    fixed_missing_difficulty_score = 0

    for record in fixed_records:
        if "entity_to_token" not in record or not record.get("entity_to_token"):
            fixed_missing_entity_to_token += 1
        if "difficulty_score" not in record or record.get("difficulty_score") is None:
            fixed_missing_difficulty_score += 1

    print(f"\n修复后统计:")
    print(f"  缺失 entity_to_token: {fixed_missing_entity_to_token}")
    print(f"  缺失 difficulty_score: {fixed_missing_difficulty_score}")


if __name__ == "__main__":
    main()
