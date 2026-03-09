#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GeoKD-SR 数据集字段修复脚本 (直接处理train/dev/test文件)
修复已分割的数据集中的缺失字段
"""

import json
import argparse
from pathlib import Path
from typing import Dict, List
from datetime import datetime

# 难度到分数的映射
DIFFICULTY_TO_SCORE = {
    "easy": 1.5,
    "medium": 2.75,
    "hard": 4.0
}


def fix_record_fields(record: Dict) -> Dict:
    """修复单条记录的缺失字段"""

    # 1. 修复difficulty_score
    if "difficulty_score" not in record:
        difficulty = record.get("difficulty", "medium")
        score = DIFFICULTY_TO_SCORE.get(difficulty, 2.75)
        record["difficulty_score"] = score

    # 2. 修复entity_to_token
    if "entity_to_token" not in record or not record["entity_to_token"]:
        question = record.get("question", "")
        entities = record.get("entities", [])
        entity_to_token = {}

        for entity in entities:
            if not isinstance(entity, dict):
                continue

            name = entity.get("name", "")
            if not name:
                continue

            # 查找实体在问题中的位置
            char_start = question.find(name)
            if char_start == -1:
                # 尝试在answer中查找
                answer = record.get("answer", "")
                char_start = answer.find(name)
                if char_start == -1:
                    # 无法找到位置，使用默认值
                    char_start = 0
                    char_end = min(len(name), len(question))
                else:
                    char_end = char_start + len(name)
            else:
                char_end = char_start + len(name)

            # 简单的token索引：使用字符位置作为近似
            token_indices = list(range(char_start, min(char_end, len(question))))

            entity_to_token[name] = {
                "char_start": char_start,
                "char_end": char_end,
                "token_indices": token_indices
            }

        record["entity_to_token"] = entity_to_token

    return record


def process_file(input_file: Path, output_file: Path = None) -> dict:
    """处理单个文件"""
    if output_file is None:
        output_file = input_file

    print(f"\n处理文件: {input_file.name}")

    records = []
    stats = {
        "total": 0,
        "fixed_difficulty_score": 0,
        "fixed_entity_to_token": 0
    }

    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue

            record = json.loads(line)
            stats["total"] += 1

            # 记录修复前的状态
            needs_difficulty_score = "difficulty_score" not in record
            needs_entity_to_token = "entity_to_token" not in record or not record["entity_to_token"]

            # 修复字段
            fixed_record = fix_record_fields(record)
            records.append(fixed_record)

            # 统计
            if needs_difficulty_score:
                stats["fixed_difficulty_score"] += 1
            if needs_entity_to_token:
                stats["fixed_entity_to_token"] += 1

            if stats["total"] % 500 == 0:
                print(f"  进度: {stats['total']} 条记录")

    # 写入文件
    with open(output_file, 'w', encoding='utf-8') as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')

    print(f"  完成: {stats['total']} 条记录")
    print(f"  修复difficulty_score: {stats['fixed_difficulty_score']} 条")
    print(f"  修复entity_to_token: {stats['fixed_entity_to_token']} 条")

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="GeoKD-SR 数据集字段修复脚本 (直接处理train/dev/test文件)"
    )

    parser.add_argument(
        "--input-dir", "-i",
        default="D:/30_keyan/GeoKD-SR/data/geosr_chain",
        help="数据集目录"
    )
    parser.add_argument(
        "--files", "-f",
        nargs="+",
        default=["train.jsonl", "dev.jsonl", "test.jsonl"],
        help="要处理的文件列表"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("GeoKD-SR 数据集字段修复脚本")
    print("=" * 60)
    print(f"\n输入目录: {args.input_dir}")
    print(f"处理文件: {args.files}")

    input_dir = Path(args.input_dir)

    total_stats = {
        "total": 0,
        "fixed_difficulty_score": 0,
        "fixed_entity_to_token": 0
    }

    for file_name in args.files:
        input_file = input_dir / file_name
        if input_file.exists():
            stats = process_file(input_file)
            for key in total_stats:
                total_stats[key] += stats[key]
        else:
            print(f"  文件不存在: {file_name}")

    print("\n" + "=" * 60)
    print("修复完成!")
    print("=" * 60)
    print(f"\n总计:")
    print(f"  处理记录: {total_stats['total']} 条")
    print(f"  修复difficulty_score: {total_stats['fixed_difficulty_score']} 条")
    print(f"  修复entity_to_token: {total_stats['fixed_entity_to_token']} 条")

    print(f"\n处理完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    return 0


if __name__ == "__main__":
    exit(main())
